"""Tests for Web UI: tenant list and framework list (Issue #36)."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.tenant import Tenant
from src.services import tenant_service


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestListPublicTenants:
    async def test_returns_public_only(self, db_session: AsyncSession):
        """Private tenants are excluded from the list."""
        pub = Tenant(name="Public", is_private=False)
        priv = Tenant(name="Private", is_private=True)
        db_session.add_all([pub, priv])
        await db_session.flush()

        result = await tenant_service.list_public_tenants(db_session)
        names = [t.name for t in result]
        assert "Public" in names
        assert "Private" not in names

    async def test_sorted_by_name_then_id(self, db_session: AsyncSession):
        """Tenants are sorted by name ASC, then id ASC."""
        t1 = Tenant(id=uuid.UUID("00000000-0000-0000-0000-000000000002"), name="Banana", is_private=False)
        t2 = Tenant(id=uuid.UUID("00000000-0000-0000-0000-000000000001"), name="Apple", is_private=False)
        t3 = Tenant(id=uuid.UUID("00000000-0000-0000-0000-000000000003"), name="Apple", is_private=False)
        db_session.add_all([t1, t2, t3])
        await db_session.flush()

        result = await tenant_service.list_public_tenants(db_session)
        names_ids = [(t.name, str(t.id)) for t in result]
        assert names_ids[0] == ("Apple", "00000000-0000-0000-0000-000000000001")
        assert names_ids[1] == ("Apple", "00000000-0000-0000-0000-000000000003")
        assert names_ids[2] == ("Banana", "00000000-0000-0000-0000-000000000002")

    async def test_empty_when_no_public(self, db_session: AsyncSession):
        """Returns empty list when no public tenants exist."""
        priv = Tenant(name="Private Only", is_private=True)
        db_session.add(priv)
        await db_session.flush()

        result = await tenant_service.list_public_tenants(db_session)
        assert result == []


class TestGetTenant:
    async def test_returns_tenant(self, db_session: AsyncSession, tenant: Tenant):
        result = await tenant_service.get_tenant(db_session, tenant.id)
        assert result is not None
        assert result.id == tenant.id

    async def test_returns_none_for_missing(self, db_session: AsyncSession):
        result = await tenant_service.get_tenant(
            db_session, uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert result is None


class TestListDocumentsWithItemCount:
    async def test_returns_documents_with_count(
        self, db_session: AsyncSession, tenant: Tenant,
    ):
        doc = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/uri/1",
            title="Doc A",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(doc)
        await db_session.flush()

        # Add 3 items
        for i in range(3):
            item = CFItem(
                tenant_id=tenant.id,
                cf_document_id=doc.id,
                identifier=uuid.uuid4(),
                uri=f"https://example.com/uri/item-{i}",
                full_statement=f"Item {i}",
                last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            db_session.add(item)
        await db_session.flush()

        result = await tenant_service.list_documents_with_item_count(
            db_session, tenant.id,
        )
        assert len(result) == 1
        assert result[0]["doc"].title == "Doc A"
        assert result[0]["item_count"] == 3

    async def test_zero_items(self, db_session: AsyncSession, tenant: Tenant):
        """Document with no items shows count 0."""
        doc = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/uri/empty",
            title="Empty Doc",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(doc)
        await db_session.flush()

        result = await tenant_service.list_documents_with_item_count(
            db_session, tenant.id,
        )
        assert len(result) == 1
        assert result[0]["item_count"] == 0

    async def test_sorted_by_title_then_identifier(
        self, db_session: AsyncSession, tenant: Tenant,
    ):
        id1 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        id2 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        id3 = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        doc1 = CFDocument(
            tenant_id=tenant.id, identifier=id1,
            uri="u1", title="Zebra",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        doc2 = CFDocument(
            tenant_id=tenant.id, identifier=id2,
            uri="u2", title="Alpha",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        doc3 = CFDocument(
            tenant_id=tenant.id, identifier=id3,
            uri="u3", title="Alpha",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([doc1, doc2, doc3])
        await db_session.flush()

        result = await tenant_service.list_documents_with_item_count(
            db_session, tenant.id,
        )
        titles_ids = [(r["doc"].title, str(r["doc"].identifier)) for r in result]
        assert titles_ids[0] == ("Alpha", str(id2))
        assert titles_ids[1] == ("Alpha", str(id3))
        assert titles_ids[2] == ("Zebra", str(id1))

    async def test_empty(self, db_session: AsyncSession, tenant: Tenant):
        result = await tenant_service.list_documents_with_item_count(
            db_session, tenant.id,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Router / integration tests
# ---------------------------------------------------------------------------


class TestIndexPage:
    async def test_returns_html(self, db_client):
        resp = await db_client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_cache_control(self, db_client):
        resp = await db_client.get("/")
        assert resp.headers["cache-control"] == "public, max-age=3600"

    async def test_shows_public_tenants(self, db_session, db_client):
        t = Tenant(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            name="Visible Tenant",
            is_private=False,
        )
        db_session.add(t)
        await db_session.flush()

        resp = await db_client.get("/")
        assert "Visible Tenant" in resp.text
        assert "/22222222-2222-2222-2222-222222222222/" in resp.text

    async def test_hides_private_tenants(self, db_session, db_client):
        t = Tenant(name="Secret Tenant", is_private=True)
        db_session.add(t)
        await db_session.flush()

        resp = await db_client.get("/")
        assert "Secret Tenant" not in resp.text

    async def test_empty_message(self, db_client):
        resp = await db_client.get("/")
        assert "公開テナントはありません" in resp.text

    async def test_html_title(self, db_client):
        resp = await db_client.get("/")
        assert "<title>COMPEITO</title>" in resp.text

    async def test_html_lang_ja(self, db_client):
        resp = await db_client.get("/")
        assert 'lang="ja"' in resp.text


class TestTenantPage:
    async def test_returns_html(self, db_session, db_client, tenant):
        resp = await db_client.get(f"/{tenant.id}/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_cache_control(self, db_session, db_client, tenant):
        resp = await db_client.get(f"/{tenant.id}/")
        assert resp.headers["cache-control"] == "public, max-age=3600"

    async def test_shows_documents(self, db_session, db_client, tenant, sample_document):
        resp = await db_client.get(f"/{tenant.id}/")
        assert "Test Document" in resp.text
        assert f"/cftree/doc/{sample_document.identifier}" in resp.text

    async def test_shows_item_count(self, db_session, db_client, tenant, sample_document):
        # Add 2 items
        for i in range(2):
            item = CFItem(
                tenant_id=tenant.id,
                cf_document_id=sample_document.id,
                identifier=uuid.uuid4(),
                uri=f"https://example.com/uri/item-{i}",
                full_statement=f"Item {i}",
                last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/")
        # The count "2" should appear in the response
        assert resp.text.count(">2<") >= 1 or ">2\n" in resp.text or ">\n                    2\n" in resp.text

    async def test_empty_message(self, db_session, db_client, tenant):
        resp = await db_client.get(f"/{tenant.id}/")
        assert "フレームワークはありません" in resp.text

    async def test_breadcrumb(self, db_session, db_client, tenant):
        resp = await db_client.get(f"/{tenant.id}/")
        assert "テナント一覧" in resp.text
        assert 'href="/"' in resp.text

    async def test_html_title(self, db_session, db_client, tenant):
        resp = await db_client.get(f"/{tenant.id}/")
        assert f"<title>{tenant.name} - COMPEITO</title>" in resp.text

    async def test_private_tenant_accessible(self, db_session, db_client):
        """Private tenants are accessible via direct URL."""
        priv = Tenant(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            name="Private Org",
            is_private=True,
        )
        db_session.add(priv)
        await db_session.flush()

        resp = await db_client.get(f"/{priv.id}/")
        assert resp.status_code == 200
        assert "Private Org" in resp.text


class TestTenantPageErrors:
    async def test_invalid_uuid_400(self, db_client):
        resp = await db_client.get("/not-a-uuid/")
        assert resp.status_code == 400
        assert "リクエストが不正です" in resp.text

    async def test_missing_tenant_404(self, db_client):
        resp = await db_client.get("/99999999-9999-9999-9999-999999999999/")
        assert resp.status_code == 404
        assert "ページが見つかりません" in resp.text

    async def test_error_no_cache_control(self, db_client):
        """Error responses should not have Cache-Control."""
        resp = await db_client.get("/not-a-uuid/")
        assert "cache-control" not in resp.headers

    async def test_404_no_cache_control(self, db_client):
        resp = await db_client.get("/99999999-9999-9999-9999-999999999999/")
        assert "cache-control" not in resp.headers
