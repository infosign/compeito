"""Tests for the CFItemType reverse lookup: "items of this type".

Mirrors the CFSubject reverse lookup but matches the `cf_item_type_id` FK
(not JSONB). Repository (FK filter, tenant scope, document scope, pagination)
+ Web UI (item-type detail section, "load more" fragment, validation).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.tenant import Tenant
from src.repositories import cf_item_repository
from src.routers.web import _detail_extras

_TS = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _make_item_type(tenant: Tenant, *, title: str = "Knowledge") -> CFItemType:
    ident = uuid.uuid4()
    return CFItemType(
        tenant_id=tenant.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        title=title,
        last_change_date_time=_TS,
    )


def _make_item(
    tenant: Tenant,
    doc: CFDocument,
    *,
    item_type: CFItemType | None = None,
    hcs: str | None = None,
    full_statement: str = "stmt",
) -> CFItem:
    ident = uuid.uuid4()
    return CFItem(
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        cf_item_type_id=item_type.id if item_type is not None else None,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        full_statement=full_statement,
        human_coding_scheme=hcs,
        depth=0,
        last_change_date_time=_TS,
    )


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


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class TestListItemsByItemType:
    async def test_fk_match_and_exclusion(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        it = _make_item_type(tenant)
        other = _make_item_type(tenant, title="Skill")
        db_session.add_all([it, other])
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="of type"))
        db_session.add(_make_item(tenant, sample_document, item_type=other, full_statement="other type"))
        db_session.add(_make_item(tenant, sample_document, item_type=None, full_statement="no type"))
        await db_session.flush()

        rows = await cf_item_repository.list_items_by_item_type(db_session, tenant.id, it.id)
        assert {r["full_statement"] for r in rows} == {"of type"}
        assert await cf_item_repository.count_items_by_item_type(db_session, tenant.id, it.id) == 1

    async def test_document_scope(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        it = _make_item_type(tenant)
        db_session.add(it)
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="in A"))
        doc_b = _make_document(tenant)
        db_session.add(doc_b)
        await db_session.flush()
        db_session.add(_make_item(tenant, doc_b, item_type=it, full_statement="in B"))
        await db_session.flush()

        assert await cf_item_repository.count_items_by_item_type(db_session, tenant.id, it.id) == 2
        scoped = await cf_item_repository.list_items_by_item_type(
            db_session, tenant.id, it.id, document_id=sample_document.id
        )
        assert {r["full_statement"] for r in scoped} == {"in A"}

    async def test_pagination(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        it = _make_item_type(tenant)
        db_session.add(it)
        await db_session.flush()
        for i in range(25):
            db_session.add(
                _make_item(tenant, sample_document, item_type=it, hcs=f"{i:03d}", full_statement=f"i{i:03d}")
            )
        await db_session.flush()
        page1 = await cf_item_repository.list_items_by_item_type(db_session, tenant.id, it.id, offset=0, limit=20)
        page2 = await cf_item_repository.list_items_by_item_type(db_session, tenant.id, it.id, offset=20, limit=20)
        assert len(page1) == 20 and len(page2) == 5
        assert set(r["identifier"] for r in page1).isdisjoint(r["identifier"] for r in page2)


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------


class TestItemTypeDetailAndPane:
    async def test_detail_extras_scopes_by_doc(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        it = _make_item_type(tenant)
        db_session.add(it)
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="A item"))
        doc_b = _make_document(tenant)
        db_session.add(doc_b)
        await db_session.flush()
        db_session.add(_make_item(tenant, doc_b, item_type=it, full_statement="B item"))
        await db_session.flush()

        page = await _detail_extras(db_session, tenant.id, "CFItemType", it)
        assert page["item_type_items"]["total"] == 2
        assert page["item_type_items"]["scope_doc"] is None

        pane = await _detail_extras(db_session, tenant.id, "CFItemType", it, sample_document)
        assert pane["item_type_items"]["total"] == 1
        assert pane["item_type_items"]["scope_doc"] == str(sample_document.identifier)

    async def test_standalone_page_shows_items(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        it = _make_item_type(tenant, title="Knowledge & Skills")
        db_session.add(it)
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="typed item one"))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{it.identifier}")
        assert resp.status_code == 200
        assert "この種別の項目" in resp.text
        assert "typed item one" in resp.text

    async def test_pane_fragment_shows_doc_scoped(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        # An item type used by an item in this doc is a tree node (Definitions),
        # so its detail fragment renders in the pane with the doc-scoped list.
        it = _make_item_type(tenant, title="Pane Type")
        db_session.add(it)
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="typed in pane"))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{it.identifier}")
        assert resp.status_code == 200
        assert "typed in pane" in resp.text

    async def test_load_more_url_uses_item_type_endpoint(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        it = _make_item_type(tenant)
        db_session.add(it)
        await db_session.flush()
        for i in range(25):
            db_session.add(
                _make_item(tenant, sample_document, item_type=it, hcs=f"{i:03d}", full_statement=f"t{i:03d}")
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{it.identifier}")
        assert resp.status_code == 200
        assert f"/{tenant.id}/item-type/{it.identifier}/items?offset=20" in resp.text

    async def test_fragment_filters_and_validates(
        self, db_session: AsyncSession, db_client, tenant: Tenant, sample_document: CFDocument
    ):
        it = _make_item_type(tenant)
        db_session.add(it)
        await db_session.flush()
        db_session.add(_make_item(tenant, sample_document, item_type=it, full_statement="frag item"))
        await db_session.flush()

        ok = await db_client.get(f"/{tenant.id}/item-type/{it.identifier}/items?offset=0&limit=20")
        assert ok.status_code == 200
        assert "frag item" in ok.text

        # A subject/non-itemtype id → 404; bad uuid → 400.
        bad = await db_client.get(f"/{tenant.id}/item-type/{uuid.uuid4()}/items")
        assert bad.status_code == 404
        assert (await db_client.get(f"/{tenant.id}/item-type/not-a-uuid/items")).status_code == 400
