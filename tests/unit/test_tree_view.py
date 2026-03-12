"""Tests for Web UI: tree view (Issue #37)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.tenant import Tenant
from src.services import tree_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    tenant: Tenant,
    doc: CFDocument,
    *,
    full_statement: str = "stmt",
    hcs: str | None = None,
    depth: int = 0,
    identifier: uuid.UUID | None = None,
) -> CFItem:
    ident = identifier or uuid.uuid4()
    return CFItem(
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        full_statement=full_statement,
        human_coding_scheme=hcs,
        depth=depth,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_is_child_of(
    doc: CFDocument,
    origin_ident: uuid.UUID,
    dest_ident: uuid.UUID | str,
    *,
    seq: int | None = None,
) -> CFAssociation:
    return CFAssociation(
        tenant_id=doc.tenant_id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/assoc/" + str(uuid.uuid4()),
        association_type="isChildOf",
        origin_node_uri=f"https://example.com/uri/{origin_ident}",
        origin_node_identifier=str(origin_ident),
        destination_node_uri=f"https://example.com/uri/{dest_ident}",
        destination_node_identifier=str(dest_ident),
        sequence_number=seq,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestGetChildren:
    async def test_returns_children(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        child = _make_item(tenant, sample_document, full_statement="Child 1")
        db_session.add(child)
        db_session.add(
            _make_is_child_of(
                sample_document,
                child.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        nodes = await tree_service.get_children(
            db_session,
            sample_document.id,
            str(sample_document.identifier),
        )
        assert len(nodes) == 1
        assert nodes[0].item.full_statement == "Child 1"

    async def test_sorted_by_seq_hcs_ident(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        i1 = _make_item(tenant, sample_document, full_statement="A", hcs="B-10")
        i2 = _make_item(tenant, sample_document, full_statement="B", hcs="B-2")
        i3 = _make_item(tenant, sample_document, full_statement="C", hcs=None)
        for i in [i1, i2, i3]:
            db_session.add(i)
            db_session.add(
                _make_is_child_of(
                    sample_document,
                    i.identifier,
                    sample_document.identifier,
                    seq=1,
                )
            )
        await db_session.flush()

        nodes = await tree_service.get_children(
            db_session,
            sample_document.id,
            str(sample_document.identifier),
        )
        # seq all same (1) -> hcs natsort: B-2 < B-10, NULL last
        stmts = [n.item.full_statement for n in nodes]
        assert stmts[0] == "B"  # B-2
        assert stmts[1] == "A"  # B-10
        assert stmts[2] == "C"  # NULL hcs

    async def test_seq_null_last(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        i1 = _make_item(tenant, sample_document, full_statement="seq1", hcs="A")
        i2 = _make_item(tenant, sample_document, full_statement="no_seq", hcs="B")
        db_session.add_all([i1, i2])
        db_session.add(
            _make_is_child_of(
                sample_document,
                i1.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        db_session.add(
            _make_is_child_of(
                sample_document,
                i2.identifier,
                sample_document.identifier,
                seq=None,
            )
        )
        await db_session.flush()

        nodes = await tree_service.get_children(
            db_session,
            sample_document.id,
            str(sample_document.identifier),
        )
        assert nodes[0].item.full_statement == "seq1"
        assert nodes[1].item.full_statement == "no_seq"

    async def test_has_children_flag(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        parent = _make_item(tenant, sample_document, full_statement="Parent")
        child = _make_item(tenant, sample_document, full_statement="Child", depth=1)
        db_session.add_all([parent, child])
        db_session.add(
            _make_is_child_of(
                sample_document,
                parent.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        db_session.add(
            _make_is_child_of(
                sample_document,
                child.identifier,
                parent.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        nodes = await tree_service.get_children(
            db_session,
            sample_document.id,
            str(sample_document.identifier),
        )
        assert len(nodes) == 1
        assert nodes[0].has_children is True

    async def test_empty_for_no_children(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        nodes = await tree_service.get_children(
            db_session,
            sample_document.id,
            str(sample_document.identifier),
        )
        assert nodes == []


class TestGetOrphans:
    async def test_orphan_items(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        # Regular item with isChildOf
        regular = _make_item(tenant, sample_document, full_statement="Regular")
        # Orphan item (no isChildOf)
        orphan = _make_item(tenant, sample_document, full_statement="Orphan")
        db_session.add_all([regular, orphan])
        db_session.add(
            _make_is_child_of(
                sample_document,
                regular.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        nodes = await tree_service.get_orphan_items(db_session, sample_document.id)
        assert len(nodes) == 1
        assert nodes[0].item.full_statement == "Orphan"


class TestBuildSSRTree:
    async def test_depth_0_expanded_depth_1_shown(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Depth 0 items are expanded (▼), depth 1 children visible."""
        root = _make_item(tenant, sample_document, full_statement="Root", depth=0)
        child = _make_item(tenant, sample_document, full_statement="Child", depth=1)
        db_session.add_all([root, child])
        db_session.add(
            _make_is_child_of(
                sample_document,
                root.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        db_session.add(
            _make_is_child_of(
                sample_document,
                child.identifier,
                root.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        roots, orphans, sel = await tree_service.build_ssr_tree(
            db_session,
            sample_document,
        )
        assert len(roots) == 1
        assert roots[0].is_expanded is True
        assert len(roots[0].children) == 1
        assert roots[0].children[0].item.full_statement == "Child"
        assert sel is None

    async def test_selected_item_returned(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Target")
        db_session.add(item)
        db_session.add(
            _make_is_child_of(
                sample_document,
                item.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        _, _, sel = await tree_service.build_ssr_tree(
            db_session,
            sample_document,
            item.identifier,
        )
        assert sel is not None
        assert sel.identifier == item.identifier

    async def test_invalid_item_ignored(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        _, _, sel = await tree_service.build_ssr_tree(
            db_session,
            sample_document,
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert sel is None

    async def test_deep_link_expands_ancestors(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """?item= parameter expands the ancestor path."""
        root = _make_item(tenant, sample_document, full_statement="Root", depth=0)
        mid = _make_item(tenant, sample_document, full_statement="Mid", depth=1)
        deep = _make_item(tenant, sample_document, full_statement="Deep", depth=2)
        db_session.add_all([root, mid, deep])
        db_session.add(
            _make_is_child_of(
                sample_document,
                root.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        db_session.add(
            _make_is_child_of(
                sample_document,
                mid.identifier,
                root.identifier,
                seq=1,
            )
        )
        db_session.add(
            _make_is_child_of(
                sample_document,
                deep.identifier,
                mid.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        roots, _, sel = await tree_service.build_ssr_tree(
            db_session,
            sample_document,
            deep.identifier,
        )
        assert sel is not None
        # Root should be expanded, mid should be expanded
        assert roots[0].is_expanded is True
        assert len(roots[0].children) == 1
        mid_node = roots[0].children[0]
        assert mid_node.is_expanded is True
        assert len(mid_node.children) == 1
        assert mid_node.children[0].item.identifier == deep.identifier


class TestGetItemForDetail:
    async def test_returns_item(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Detail item")
        db_session.add(item)
        await db_session.flush()

        result = await tree_service.get_item_for_detail(
            db_session,
            sample_document.id,
            item.identifier,
        )
        assert result is not None
        assert result.full_statement == "Detail item"

    async def test_returns_none_for_wrong_doc(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        result = await tree_service.get_item_for_detail(
            db_session,
            sample_document.id,
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert result is None


# ---------------------------------------------------------------------------
# Router integration tests
# ---------------------------------------------------------------------------


class TestTreeViewPage:
    async def test_renders_tree(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Root Item")
        db_session.add(item)
        db_session.add(
            _make_is_child_of(
                sample_document,
                item.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert resp.status_code == 200
        assert "Root Item" in resp.text

    async def test_html_title(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert f"<title>{sample_document.title} - {tenant.name} - COMPEITO</title>" in resp.text

    async def test_breadcrumb(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert "テナント一覧" in resp.text
        assert tenant.name in resp.text
        assert sample_document.title in resp.text

    async def test_cache_control(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert resp.headers["cache-control"] == "public, max-age=3600"

    async def test_empty_tree_message(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert "アイテムがありません" in resp.text

    async def test_invalid_tenant_400(self, db_client):
        resp = await db_client.get("/not-uuid/cftree/doc/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert resp.status_code == 400

    async def test_missing_doc_404(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/99999999-9999-9999-9999-999999999999",
        )
        assert resp.status_code == 404

    async def test_invalid_doc_400(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/not-uuid")
        assert resp.status_code == 400

    async def test_item_param_deep_link(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Deep Target")
        db_session.add(item)
        db_session.add(
            _make_is_child_of(
                sample_document,
                item.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}?item={item.identifier}",
        )
        assert resp.status_code == 200
        assert "Deep Target" in resp.text

    async def test_item_param_invalid_ignored(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}?item=not-uuid",
        )
        assert resp.status_code == 200  # page renders normally

    async def test_doc_default_right_pane(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Without ?item=, right pane shows document info."""
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert "lastChangeDateTime" in resp.text


class TestChildrenFragment:
    async def test_returns_children(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        child = _make_item(tenant, sample_document, full_statement="Fragment Child")
        db_session.add(child)
        db_session.add(
            _make_is_child_of(
                sample_document,
                child.identifier,
                sample_document.identifier,
                seq=1,
            )
        )
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/{sample_document.identifier}",
        )
        assert resp.status_code == 200
        assert "Fragment Child" in resp.text

    async def test_cache_control_fragment(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/{sample_document.identifier}",
        )
        assert resp.headers["cache-control"] == "public, max-age=86400"

    async def test_invalid_tenant_400(self, db_client):
        resp = await db_client.get(
            "/bad/cftree/doc/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/children/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        assert resp.status_code == 400
        assert "リクエストが不正です" in resp.text

    async def test_missing_tenant_404(self, db_client):
        resp = await db_client.get(
            "/99999999-9999-9999-9999-999999999999/cftree/doc/"
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/children/"
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        assert resp.status_code == 404
        assert "テナントが見つかりません" in resp.text

    async def test_invalid_doc_400(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/bad/children/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        assert resp.status_code == 400

    async def test_missing_doc_404(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/99999999-9999-9999-9999-999999999999"
            "/children/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        assert resp.status_code == 404

    async def test_invalid_item_400(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/bad",
        )
        assert resp.status_code == 400

    async def test_nonexistent_item_returns_empty(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/99999999-9999-9999-9999-999999999999",
        )
        # Returns 200 with empty content (no children)
        assert resp.status_code == 200


class TestDetailFragment:
    async def test_returns_detail(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Detail Target")
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert resp.status_code == 200
        assert "Detail Target" in resp.text

    async def test_cache_control_fragment(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Cache test")
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert resp.headers["cache-control"] == "public, max-age=86400"

    async def test_detail_link(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = _make_item(tenant, sample_document, full_statement="Link test")
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert f"/uri/{item.identifier}" in resp.text
        assert "詳細" in resp.text

    async def test_missing_item_404(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/99999999-9999-9999-9999-999999999999",
        )
        assert resp.status_code == 404
        assert "アイテムが見つかりません" in resp.text

    async def test_invalid_item_400(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/bad",
        )
        assert resp.status_code == 400

    async def test_shows_optional_fields(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item_type = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/type",
            title="Standard",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(item_type)
        await db_session.flush()

        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            cf_item_type_id=item_type.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/item",
            full_statement="Full stmt",
            human_coding_scheme="A-1",
            education_level=["Elementary", "Middle"],
            language="ja",
            concept_keywords=["math", "science"],
            depth=0,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert "A-1" in resp.text
        assert "Standard" in resp.text
        assert "Elementary" in resp.text
        assert "math" in resp.text
        assert "ja" in resp.text
