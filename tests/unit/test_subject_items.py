"""Tests for the CFSubject reverse lookup: "items setting this subject".

Repository-level (JSONB containment, tenant scope, pagination) + Web UI
(subject detail section, "load more" fragment, validation, caching, empty state).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant
from src.repositories import cf_item_repository
from src.routers.web import _detail_extras

_TS = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _make_subject(tenant: Tenant, *, identifier: uuid.UUID | None = None, title: str = "Statistics") -> CFSubject:
    ident = identifier or uuid.uuid4()
    return CFSubject(
        tenant_id=tenant.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        title=title,
        last_change_date_time=_TS,
    )


def _make_item_with_subject(
    tenant: Tenant,
    doc: CFDocument,
    subject_identifier: str | None,
    *,
    hcs: str | None = None,
    full_statement: str = "stmt",
    identifier: uuid.UUID | None = None,
) -> CFItem:
    ident = identifier or uuid.uuid4()
    subject_uri = None
    if subject_identifier is not None:
        subject_uri = [
            {"title": "S", "identifier": subject_identifier, "uri": f"https://example.com/uri/{subject_identifier}"}
        ]
    return CFItem(
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        full_statement=full_statement,
        human_coding_scheme=hcs,
        subject_uri=subject_uri,
        depth=0,
        last_change_date_time=_TS,
    )


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestListItemsBySubject:
    async def test_containment_match_and_exclusion(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        other = str(uuid.uuid4())
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="match A"))
        db_session.add(_make_item_with_subject(tenant, sample_document, other, full_statement="other subj"))
        db_session.add(_make_item_with_subject(tenant, sample_document, None, full_statement="no subject"))
        await db_session.flush()

        rows = await cf_item_repository.list_items_by_subject(db_session, tenant.id, sid)
        statements = {r["full_statement"] for r in rows}
        assert statements == {"match A"}
        assert rows[0]["doc_identifier"] == str(sample_document.identifier)

    async def test_tenant_scoped(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        # The SAME subject identifier exists in two tenants → only the queried
        # tenant's items come back (shared frameworks reuse identifiers).
        shared_id = uuid.uuid4()
        db_session.add(_make_subject(tenant, identifier=shared_id))
        db_session.add(_make_item_with_subject(tenant, sample_document, str(shared_id), full_statement="mine"))

        other_tenant = Tenant(id=uuid.uuid4(), name="Other", is_private=False)
        db_session.add(other_tenant)
        await db_session.flush()
        other_doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/uri/otherdoc",
            title="Other Doc",
            creator="x",
            language="ja",
            last_change_date_time=_TS,
        )
        db_session.add(other_doc)
        db_session.add(_make_subject(other_tenant, identifier=shared_id))
        db_session.add(_make_item_with_subject(other_tenant, other_doc, str(shared_id), full_statement="theirs"))
        await db_session.flush()

        rows = await cf_item_repository.list_items_by_subject(db_session, tenant.id, str(shared_id))
        assert {r["full_statement"] for r in rows} == {"mine"}

    async def test_pagination_boundary(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(25):
            db_session.add(
                _make_item_with_subject(tenant, sample_document, sid, hcs=f"{i:03d}", full_statement=f"item {i:03d}")
            )
        await db_session.flush()

        page1 = await cf_item_repository.list_items_by_subject(db_session, tenant.id, sid, offset=0, limit=20)
        page2 = await cf_item_repository.list_items_by_subject(db_session, tenant.id, sid, offset=20, limit=20)
        assert len(page1) == 20
        assert len(page2) == 5
        # No overlap / no skip across the boundary (stable order by hcs).
        ids1 = [r["identifier"] for r in page1]
        ids2 = [r["identifier"] for r in page2]
        assert set(ids1).isdisjoint(ids2)
        assert len(set(ids1) | set(ids2)) == 25

    async def test_count(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(3):
            db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement=f"x{i}"))
        await db_session.flush()
        assert await cf_item_repository.count_items_by_subject(db_session, tenant.id, sid) == 3

    async def test_empty(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        subj = _make_subject(tenant)
        db_session.add(subj)
        await db_session.flush()
        sid = str(subj.identifier)
        assert await cf_item_repository.list_items_by_subject(db_session, tenant.id, sid) == []
        assert await cf_item_repository.count_items_by_subject(db_session, tenant.id, sid) == 0


# ---------------------------------------------------------------------------
# Web UI tests
# ---------------------------------------------------------------------------


class TestSubjectDetailPage:
    async def test_section_shows_topn_and_count(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(25):
            db_session.add(
                _make_item_with_subject(tenant, sample_document, sid, hcs=f"{i:03d}", full_statement=f"stmt {i:03d}")
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{subj.identifier}")
        assert resp.status_code == 200
        # Top-20 SSR'd; the 21st (021) is not on the initial page.
        assert "stmt 000" in resp.text
        assert "stmt 019" in resp.text
        assert "stmt 020" not in resp.text
        # Count + "load more" button + fragment URL.
        assert "25" in resp.text
        assert f"/{tenant.id}/subject/{subj.identifier}/items?offset=20" in resp.text
        assert resp.headers["Cache-Control"] == "public, max-age=3600"

    async def test_no_button_when_within_one_page(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="only one"))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{subj.identifier}")
        assert resp.status_code == 200
        assert "only one" in resp.text
        assert f"/subject/{subj.identifier}/items" not in resp.text

    async def test_empty_section_hidden(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant, title="Lonely Subject")
        db_session.add(subj)
        await db_session.flush()
        resp = await db_client.get(f"/{tenant.id}/uri/{subj.identifier}")
        assert resp.status_code == 200
        assert "Lonely Subject" in resp.text  # the subject itself renders
        # No reverse-lookup section / fragment link when there are no items.
        assert f"/subject/{subj.identifier}/items" not in resp.text


class TestSubjectItemsFragment:
    async def test_next_page_and_self_perpetuating_button(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(45):
            db_session.add(
                _make_item_with_subject(tenant, sample_document, sid, hcs=f"{i:03d}", full_statement=f"row {i:03d}")
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/subject/{subj.identifier}/items?offset=20&limit=20")
        assert resp.status_code == 200
        assert "row 020" in resp.text
        assert "row 039" in resp.text
        # Still more (45 total) → button advances to offset 40.
        assert f"/subject/{subj.identifier}/items?offset=40" in resp.text
        assert resp.headers["Cache-Control"] == "public, max-age=86400"

    async def test_last_page_has_no_button(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(25):
            db_session.add(
                _make_item_with_subject(tenant, sample_document, sid, hcs=f"{i:03d}", full_statement=f"row {i:03d}")
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/subject/{subj.identifier}/items?offset=20&limit=20")
        assert resp.status_code == 200
        assert "row 024" in resp.text
        assert "offset=40" not in resp.text  # exhausted → no further button

    async def test_non_subject_id_404(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        # An item id is not a CFSubject → 404 (don't drive the fragment for arbitrary ids).
        item = _make_item_with_subject(tenant, sample_document, None, full_statement="an item")
        db_session.add(item)
        await db_session.flush()
        resp = await db_client.get(f"/{tenant.id}/subject/{item.identifier}/items")
        assert resp.status_code == 404

    async def test_bad_uuid_400(self, db_client, tenant: Tenant):
        resp = await db_client.get(f"/{tenant.id}/subject/not-a-uuid/items")
        assert resp.status_code == 400

    async def test_unknown_subject_404(self, db_client, tenant: Tenant):
        resp = await db_client.get(f"/{tenant.id}/subject/{uuid.uuid4()}/items")
        assert resp.status_code == 404


def _make_document(tenant: Tenant, *, title: str = "Doc B") -> CFDocument:
    ident = uuid.uuid4()
    return CFDocument(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        title=title,
        creator="x",
        language="ja",
        last_change_date_time=_TS,
    )


class TestDocumentScope:
    """案B: the standalone /uri/ page lists items tenant-wide; the tree right
    pane lists only the CURRENT document's items setting the subject."""

    async def test_repo_document_id_filters(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="in doc A"))
        doc_b = _make_document(tenant)
        db_session.add(doc_b)
        await db_session.flush()
        db_session.add(_make_item_with_subject(tenant, doc_b, sid, full_statement="in doc B"))
        await db_session.flush()

        # Tenant-wide (document_id=None) → both.
        all_rows = await cf_item_repository.list_items_by_subject(db_session, tenant.id, sid)
        assert {r["full_statement"] for r in all_rows} == {"in doc A", "in doc B"}
        assert await cf_item_repository.count_items_by_subject(db_session, tenant.id, sid) == 2

        # Scoped to doc A → only A.
        a_rows = await cf_item_repository.list_items_by_subject(
            db_session, tenant.id, sid, document_id=sample_document.id
        )
        assert {r["full_statement"] for r in a_rows} == {"in doc A"}
        assert (
            await cf_item_repository.count_items_by_subject(db_session, tenant.id, sid, document_id=sample_document.id)
            == 1
        )

    async def test_detail_extras_scopes_by_doc(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="A item"))
        doc_b = _make_document(tenant)
        db_session.add(doc_b)
        await db_session.flush()
        db_session.add(_make_item_with_subject(tenant, doc_b, sid, full_statement="B item"))
        await db_session.flush()

        # Standalone page (doc=None) → tenant-wide, no scope_doc.
        page = await _detail_extras(db_session, tenant.id, "CFSubject", subj)
        assert page["subject_items"]["total"] == 2
        assert page["subject_items"]["scope_doc"] is None

        # Pane (doc=sample_document) → only that doc's item, scope_doc set.
        pane = await _detail_extras(db_session, tenant.id, "CFSubject", subj, sample_document)
        assert pane["subject_items"]["total"] == 1
        assert pane["subject_items"]["rows"][0]["full_statement"] == "A item"
        assert pane["subject_items"]["scope_doc"] == str(sample_document.identifier)

    async def test_pane_fragment_shows_doc_scoped(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        # A subject referenced by an item in this doc is a tree node (Definitions),
        # so its detail fragment renders in the pane — now WITH the doc-scoped list.
        subj = _make_subject(tenant, title="Pane Subject")
        sid = str(subj.identifier)
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="ref in pane"))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{subj.identifier}")
        assert resp.status_code == 200
        assert "Pane Subject" in resp.text
        assert "ref in pane" in resp.text  # the doc's item IS listed in the pane now

    async def test_load_more_url_carries_doc_scope(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        # >20 items in the doc → pane shows "load more"; its URL must keep &doc=.
        subj = _make_subject(tenant, title="Big Subject")
        sid = str(subj.identifier)
        db_session.add(subj)
        for i in range(25):
            db_session.add(
                _make_item_with_subject(tenant, sample_document, sid, hcs=f"{i:03d}", full_statement=f"big {i:03d}")
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{subj.identifier}")
        assert resp.status_code == 200
        assert f"/subject/{subj.identifier}/items?offset=20" in resp.text
        assert f"doc={sample_document.identifier}" in resp.text

    async def test_fragment_doc_scope_filters(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        subj = _make_subject(tenant)
        sid = str(subj.identifier)
        db_session.add(subj)
        db_session.add(_make_item_with_subject(tenant, sample_document, sid, full_statement="A only"))
        doc_b = _make_document(tenant)
        db_session.add(doc_b)
        await db_session.flush()
        db_session.add(_make_item_with_subject(tenant, doc_b, sid, full_statement="B only"))
        await db_session.flush()

        # Fragment scoped to doc A → only A's item.
        scoped = await db_client.get(
            f"/{tenant.id}/subject/{subj.identifier}/items?offset=0&limit=20&doc={sample_document.identifier}"
        )
        assert scoped.status_code == 200
        assert "A only" in scoped.text
        assert "B only" not in scoped.text

        # No doc → tenant-wide.
        wide = await db_client.get(f"/{tenant.id}/subject/{subj.identifier}/items?offset=0&limit=20")
        assert "A only" in wide.text
        assert "B only" in wide.text

    async def test_fragment_bad_doc_400(self, db_session: AsyncSession, db_client, tenant: Tenant):
        subj = _make_subject(tenant)
        db_session.add(subj)
        await db_session.flush()
        resp = await db_client.get(f"/{tenant.id}/subject/{subj.identifier}/items?doc=not-a-uuid")
        assert resp.status_code == 400
