"""Tests for Web UI: tenant list and framework list (Issue #36)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.i18n import get_translator
from src.models.cf_association import CFAssociation
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

    async def test_display_order_pins_above_alphabetical(self, db_session: AsyncSession):
        """display_order (smaller = higher, NULLs last) overrides the name sort:
        ordered tenants come first by number, then unset ones alphabetically."""
        a = Tenant(name="Apple", is_private=False)  # unset → falls to the bottom group
        z = Tenant(name="Zebra", is_private=False, display_order=10)
        m = Tenant(name="Mango", is_private=False, display_order=5)
        db_session.add_all([a, z, m])
        await db_session.flush()

        result = await tenant_service.list_public_tenants(db_session)
        names = [t.name for t in result]
        # display_order 5 (Mango) and 10 (Zebra) pin above the unset Apple.
        assert names == ["Mango", "Zebra", "Apple"]

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
            db_session,
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert result is None


class TestListDocumentsWithItemCount:
    async def test_returns_documents_with_count(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
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
            db_session,
            tenant.id,
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
            db_session,
            tenant.id,
        )
        assert len(result) == 1
        assert result[0]["item_count"] == 0

    async def test_sorted_by_title_then_identifier(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        id1 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        id2 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        id3 = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        doc1 = CFDocument(
            tenant_id=tenant.id,
            identifier=id1,
            uri="u1",
            title="Zebra",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        doc2 = CFDocument(
            tenant_id=tenant.id,
            identifier=id2,
            uri="u2",
            title="Alpha",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        doc3 = CFDocument(
            tenant_id=tenant.id,
            identifier=id3,
            uri="u3",
            title="Alpha",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([doc1, doc2, doc3])
        await db_session.flush()

        result = await tenant_service.list_documents_with_item_count(
            db_session,
            tenant.id,
        )
        titles_ids = [(r["doc"].title, str(r["doc"].identifier)) for r in result]
        assert titles_ids[0] == ("Alpha", str(id2))
        assert titles_ids[1] == ("Alpha", str(id3))
        assert titles_ids[2] == ("Zebra", str(id1))

    async def test_display_order_pins_above_alphabetical(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        """display_order (smaller = higher, NULLs last) overrides the title sort."""
        unset = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="u-unset",
            title="Apple",  # unset → bottom group
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        pinned_lo = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="u-lo",
            title="Zebra",
            display_order=1,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        pinned_hi = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="u-hi",
            title="Mango",
            display_order=2,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([unset, pinned_lo, pinned_hi])
        await db_session.flush()

        result = await tenant_service.list_documents_with_item_count(db_session, tenant.id)
        titles = [r["doc"].title for r in result]
        assert titles == ["Zebra", "Mango", "Apple"]

    async def test_empty(self, db_session: AsyncSession, tenant: Tenant):
        result = await tenant_service.list_documents_with_item_count(
            db_session,
            tenant.id,
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

    async def test_html_lang_en_fallback(self, db_client):
        resp = await db_client.get("/", headers={"Accept-Language": "en"})
        assert 'lang="en"' in resp.text
        assert "No public tenants" in resp.text

    async def test_i18n_unsupported_lang_falls_back_to_en(self, db_client):
        resp = await db_client.get("/", headers={"Accept-Language": "fr"})
        assert 'lang="en"' in resp.text


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
    async def test_non_uuid_segment_falls_back_to_slug_404(self, db_client):
        """A non-UUID segment is interpreted as a slug; an unknown slug → 404."""
        resp = await db_client.get("/not-a-uuid/")
        assert resp.status_code == 404
        assert "ページが見つかりません" in resp.text

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


# ---------------------------------------------------------------------------
# Retired items in the UI (B8-3 / B8-4)
# ---------------------------------------------------------------------------


def _retired_item(tenant: Tenant, doc: CFDocument, statement: str, end: date | None) -> CFItem:
    ident = uuid.uuid4()
    return CFItem(
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        full_statement=statement,
        status_end_date=end,
        depth=0,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _is_child_of(doc: CFDocument, child_ident, parent_ident) -> CFAssociation:
    return CFAssociation(
        tenant_id=doc.tenant_id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri=f"https://example.com/assoc/{uuid.uuid4()}",
        association_type="isChildOf",
        origin_node_uri=f"https://example.com/uri/{child_ident}",
        origin_node_identifier=str(child_ident),
        destination_node_uri=f"https://example.com/uri/{parent_ident}",
        destination_node_identifier=str(parent_ident),
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _replaced_by(
    doc: CFDocument, origin: CFItem, dest_ident: str, dest_uri: str, dest_title: str | None = None
) -> CFAssociation:
    return CFAssociation(
        tenant_id=doc.tenant_id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri=f"https://example.com/assoc/{uuid.uuid4()}",
        association_type="replacedBy",
        origin_node_uri=f"https://example.com/uri/{origin.identifier}",
        origin_node_identifier=str(origin.identifier),
        destination_node_uri=dest_uri,
        destination_node_identifier=dest_ident,
        destination_node_title=dest_title,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


class TestRetirementBanner:
    """Dates here are relative (today ± n) rather than fixed: the view compares
    against the UTC date, and a fixed date would flip meaning depending on when
    the suite runs. The ±1 day margins keep that harmless."""

    async def test_banner_on_a_retired_item(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        past = date.today() - timedelta(days=1)
        dead = _retired_item(tenant, sample_document, "Retired statement", past)
        db_session.add(dead)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{dead.identifier}")
        assert resp.status_code == 200, "a retired item must stay resolvable (issued badges point at it)"
        assert str(past) in resp.text
        assert 'role="note"' in resp.text

    async def test_no_banner_for_a_future_end_date(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """A scheduled end date is not a retirement yet."""
        scheduled = _retired_item(tenant, sample_document, "Scheduled", date.today() + timedelta(days=30))
        db_session.add(scheduled)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{scheduled.identifier}")
        assert resp.status_code == 200
        assert 'role="note"' not in resp.text

    async def test_successor_is_linked(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        past = date.today() - timedelta(days=1)
        dead = _retired_item(tenant, sample_document, "Old code", past)
        successor = _retired_item(tenant, sample_document, "New code", None)
        db_session.add_all([dead, successor])
        await db_session.flush()
        db_session.add(
            _replaced_by(
                sample_document,
                dead,
                str(successor.identifier),
                f"{settings.base_url}/{tenant.id}/uri/{successor.identifier}",
            )
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{dead.identifier}")
        # Scope to the banner: the related list renders the same label, so an
        # unscoped assertion would pass even if the banner never rendered.
        assert 'role="note"' in resp.text
        # Scope to the successor block of the banner: the related list renders
        # the same label further down, so an unscoped assertion would pass even
        # if the banner never rendered. Anchored on the "Replaced by" label
        # rather than on markup, which would break as soon as classified_ref
        # emits a different element.
        # The page language follows Accept-Language, so accept either rendering.
        label = next(
            (lbl for lbl in (get_translator(lang)("retired_successor") for lang in ("en", "ja")) if lbl in resp.text),
            None,
        )
        assert label is not None, "the banner's successor label is missing"
        successor_block = resp.text.split(label, 1)[1][:500]
        assert "New code" in successor_block

    async def test_successor_in_a_private_tenant_is_not_surfaced(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """Dropping the row entirely, not just the link: a title alone would
        already reveal that the private tenant holds that item."""
        private = Tenant(name="Private", is_private=True)
        db_session.add(private)
        await db_session.flush()
        private_doc = CFDocument(
            tenant_id=private.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/uri/private-doc",
            title="Private doc",
            creator="t",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(private_doc)
        await db_session.flush()
        secret = _retired_item(private, private_doc, "SECRET SUCCESSOR", None)
        db_session.add(secret)
        await db_session.flush()

        dead = _retired_item(tenant, sample_document, "Old code", date.today() - timedelta(days=1))
        db_session.add(dead)
        await db_session.flush()
        db_session.add(
            _replaced_by(
                sample_document,
                dead,
                str(secret.identifier),
                f"{settings.base_url}/{private.id}/uri/{secret.identifier}",
                # The association carries a snapshot of the title. Without this
                # the test could not fail: the label would fall back to the UUID
                # even with the guard removed.
                dest_title="SECRET SUCCESSOR",
            )
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{dead.identifier}")
        assert resp.status_code == 200
        assert "SECRET SUCCESSOR" not in resp.text


class TestRetiredToggle:
    async def test_tree_hides_retired_and_offers_the_toggle(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        past = date.today() - timedelta(days=1)
        live = _retired_item(tenant, sample_document, "Live item", None)
        dead = _retired_item(tenant, sample_document, "Dead item", past)
        db_session.add_all([live, dead])
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert "Live item" in resp.text
        assert "Dead item" not in resp.text
        assert "includeRetired=1" in resp.text

        shown = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}?includeRetired=1")
        assert "Dead item" in shown.text

    async def test_toggle_offered_for_a_deep_tombstone(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """The initial page only renders depth 0-1, but the judgement is
        document-wide, so a tombstone three levels down still surfaces the
        toggle. (Judging only the rendered levels would make the feature
        unreachable in exactly the frameworks that need it.)"""
        root = _retired_item(tenant, sample_document, "Root", None)
        mid = _retired_item(tenant, sample_document, "Mid", None)
        deep = _retired_item(tenant, sample_document, "Deep dead", date.today() - timedelta(days=1))
        db_session.add_all([root, mid, deep])
        await db_session.flush()
        db_session.add_all(
            [
                _is_child_of(sample_document, root.identifier, sample_document.identifier),
                _is_child_of(sample_document, mid.identifier, root.identifier),
                _is_child_of(sample_document, deep.identifier, mid.identifier),
            ]
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert "Deep dead" not in resp.text  # not rendered at depth 0-1 anyway
        assert "includeRetired=1" in resp.text

    async def test_toggle_keeps_the_selected_item(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """Pressing the toggle must not throw away the open item and branch."""
        live = _retired_item(tenant, sample_document, "Live item", None)
        dead = _retired_item(tenant, sample_document, "Dead item", date.today() - timedelta(days=1))
        db_session.add_all([live, dead])
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{live.identifier}")
        assert f"/item/{live.identifier}?includeRetired=1" in resp.text

    async def test_flag_rides_on_every_link_of_a_node(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """href, hx-push-url and the lazy hx-get all have to carry it; a miss on
        any one of them resets the view on the next click."""
        parent = _retired_item(tenant, sample_document, "Parent", None)
        child = _retired_item(tenant, sample_document, "Child", None)
        grandchild = _retired_item(tenant, sample_document, "Grandchild", None)
        db_session.add_all([parent, child, grandchild])
        await db_session.flush()
        db_session.add_all(
            [
                _is_child_of(sample_document, parent.identifier, sample_document.identifier),
                _is_child_of(sample_document, child.identifier, parent.identifier),
                _is_child_of(sample_document, grandchild.identifier, child.identifier),
            ]
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}?includeRetired=1")
        assert (
            f'href="/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{parent.identifier}?includeRetired=1"'
            in resp.text
        )
        assert (
            f'hx-push-url="/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{parent.identifier}?includeRetired=1"'
            in resp.text
        )
        # The lazy branch (depth 1 -> 2) fetches through /children/.
        assert f"/children/{child.identifier}?includeRetired=1" in resp.text

    async def test_children_fragment_honours_the_flag(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        parent = _retired_item(tenant, sample_document, "Parent", None)
        dead = _retired_item(tenant, sample_document, "Dead child", date.today() - timedelta(days=1))
        db_session.add_all([parent, dead])
        await db_session.flush()
        db_session.add(_is_child_of(sample_document, dead.identifier, parent.identifier))
        await db_session.flush()

        base = f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/{parent.identifier}"
        assert "Dead child" not in (await db_client.get(base)).text
        assert "Dead child" in (await db_client.get(f"{base}?includeRetired=1")).text

    async def test_detail_fragment_shows_the_banner(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        """The HTMX pane renders the same card as the permalink page."""
        past = date.today() - timedelta(days=1)
        dead = _retired_item(tenant, sample_document, "Dead item", past)
        db_session.add(dead)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{dead.identifier}")
        assert resp.status_code == 200
        assert 'role="note"' in resp.text
        assert str(past) in resp.text

    async def test_no_toggle_without_tombstones(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        db_session.add(_retired_item(tenant, sample_document, "Live item", None))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert "includeRetired=1" not in resp.text
