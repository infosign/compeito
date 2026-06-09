"""Tests for Web UI: tree view (Issue #37)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_rubric import CFRubric
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


class TestBuildFullTree:
    async def _three_levels(self, db_session, tenant, doc):
        root = _make_item(tenant, doc, full_statement="Root node", hcs="R")
        child = _make_item(tenant, doc, full_statement="Child node", hcs="C")
        grand = _make_item(tenant, doc, full_statement="Grand node", hcs="G")
        db_session.add_all([root, child, grand])
        db_session.add(_make_is_child_of(doc, root.identifier, doc.identifier, seq=1))
        db_session.add(_make_is_child_of(doc, child.identifier, root.identifier, seq=1))
        db_session.add(_make_is_child_of(doc, grand.identifier, child.identifier, seq=1))
        await db_session.flush()
        return root, child, grand

    async def test_builds_full_depth_in_one_pass(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        root, child, grand = await self._three_levels(db_session, tenant, sample_document)
        roots, orphans, selected = await tree_service.build_full_tree(db_session, sample_document)
        assert selected is None
        assert len(roots) == 1
        rn = roots[0]
        assert rn.item.identifier == root.identifier
        assert rn.is_expanded is True  # depth 0 open by default
        assert rn.has_children
        cn = rn.children[0]
        assert cn.item.identifier == child.identifier
        # The grandchild is present without any expansion query (full SSR).
        assert cn.has_children
        assert cn.children[0].item.identifier == grand.identifier
        # Deeper-than-top levels are collapsed by default.
        assert cn.is_expanded is False

    async def test_deeplink_opens_ancestor_path(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        root, child, grand = await self._three_levels(db_session, tenant, sample_document)
        roots, _, selected = await tree_service.build_full_tree(
            db_session, sample_document, selected_item_ident=grand.identifier
        )
        assert selected is not None and selected.identifier == grand.identifier
        rn = roots[0]
        assert rn.is_expanded is True  # ancestor
        assert rn.children[0].is_expanded is True  # ancestor (child)

    async def test_cycle_does_not_loop(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        a = _make_item(tenant, sample_document, full_statement="A", hcs="A")
        b = _make_item(tenant, sample_document, full_statement="B", hcs="B")
        db_session.add_all([a, b])
        # a is child of doc; a<->b cycle
        db_session.add(_make_is_child_of(sample_document, a.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, b.identifier, a.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, a.identifier, b.identifier, seq=1))
        await db_session.flush()
        # Must terminate (per-path visited set), not recurse infinitely.
        roots, _, _ = await tree_service.build_full_tree(db_session, sample_document)
        assert len(roots) >= 1


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

    async def test_full_tree_ssr_includes_deep_nodes(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Full SSR: a grandchild (depth 2) is present in the page HTML without
        any expansion round-trip, rendered inside nested <details>."""
        root = _make_item(tenant, sample_document, full_statement="Root R", hcs="R")
        child = _make_item(tenant, sample_document, full_statement="Child C", hcs="C")
        grand = _make_item(tenant, sample_document, full_statement="Grand G deep", hcs="G")
        db_session.add_all([root, child, grand])
        db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, child.identifier, root.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, grand.identifier, child.identifier, seq=1))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        # The deepest node is in the SSR HTML (no lazy load needed).
        assert "Grand G deep" in resp.text
        # Rendered via native <details> (JS-free expand/collapse).
        assert "<details" in resp.text

    async def test_tree_node_links_use_path_form_and_push_url(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Tree node links point to the path-form item URL and push it (so the
        URL syncs and is shareable/static-bakeable)."""
        item = _make_item(tenant, sample_document, full_statement="Node X")
        db_session.add(item)
        db_session.add(_make_is_child_of(sample_document, item.identifier, sample_document.identifier, seq=1))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        item_url = f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{item.identifier}"
        assert f'href="{item_url}"' in resp.text
        assert f'hx-push-url="{item_url}"' in resp.text

    async def test_item_path_route_reconstructs_view(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The path-form item URL SSRs the full page: tree + the item's full
        detail in the pane (shareable / reloadable / back-button safe)."""
        root = _make_item(tenant, sample_document, full_statement="Root sibling", hcs="R")
        target = _make_item(tenant, sample_document, full_statement="Target item deep", hcs="T")
        db_session.add_all([root, target])
        db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, target.identifier, root.identifier, seq=1))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{target.identifier}")
        assert resp.status_code == 200
        # Pane shows the target's full detail (permalink + API URL).
        assert f"/ims/case/v1p1/CFItems/{target.identifier}" in resp.text
        # Tree is still present (sibling/root node rendered).
        assert "Root sibling" in resp.text

    async def test_initial_pane_shows_document_detail(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """With no item selected, the right pane shows the document's own full
        detail (shared partial), and the header doc name is a self-link that
        re-selects it (HTMX swap + push-url to the tree root)."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        # Document full-detail card in the pane (CFPackage API URL is part of it).
        assert f"/ims/case/v1p1/CFPackages/{sample_document.identifier}" in resp.text
        # Header doc-name self-link pushes the tree-root URL.
        assert f'hx-push-url="/{tenant.id}/cftree/doc/{sample_document.identifier}"' in resp.text

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

    async def test_non_uuid_tenant_falls_back_to_slug_404(self, db_client):
        """A non-UUID tenant segment is interpreted as a slug; unknown slug → 404."""
        resp = await db_client.get("/not-uuid/cftree/doc/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert resp.status_code == 404

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
        assert str(sample_document.last_change_date_time.isoformat()) in resp.text

    async def test_doc_default_right_pane_shows_rubrics(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Right pane shows rubric list when document has rubrics."""
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="My Rubric",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(rubric)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert resp.status_code == 200
        assert "My Rubric" in resp.text
        assert str(rubric.identifier) in resp.text

    async def test_doc_default_right_pane_hides_rubrics_when_empty(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Right pane does NOT show rubric section when no rubrics exist."""
        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}",
        )
        assert resp.status_code == 200
        assert "ルーブリック" not in resp.text


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

    async def test_non_uuid_tenant_falls_back_to_slug_404(self, db_client):
        """A non-UUID tenant segment is interpreted as a slug; unknown slug → 404."""
        resp = await db_client.get(
            "/bad/cftree/doc/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/children/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        assert resp.status_code == 404
        assert "テナントが見つかりません" in resp.text

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

    async def test_pane_hides_show_in_tree(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The right pane is already inside the tree, so the redundant
        "Show in tree" link is hidden (in_pane). It still appears on the
        standalone /uri/ page."""
        item = _make_item(tenant, sample_document, full_statement="Pane item")
        db_session.add(item)
        await db_session.flush()

        pane = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}")
        assert "ツリーで表示" not in pane.text  # hidden in pane
        standalone = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert "ツリーで表示" in standalone.text  # shown on the standalone page

    async def test_document_fragment_renders_document(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The dedicated /document fragment renders the document's own detail
        (used by the header doc-name self-link)."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/document")
        assert resp.status_code == 200
        assert sample_document.title in resp.text
        assert f"/ims/case/v1p1/CFPackages/{sample_document.identifier}" in resp.text
        assert "ツリーで表示" not in resp.text  # in pane → hidden

    async def test_detail_fragment_item_wins_on_identifier_collision(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """If a CFItem shares the document's identifier (allowed — separate
        tables), /detail/{id} must return the ITEM, not the document
        (matches /uri/ item-before-document resolution)."""
        item = _make_item(
            tenant,
            sample_document,
            full_statement="Item sharing doc identifier",
            identifier=sample_document.identifier,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{sample_document.identifier}"
        )
        assert resp.status_code == 200
        # The item's full statement renders (item detail, not the document card).
        assert "Item sharing doc identifier" in resp.text
        # The CFItems API URL (item-only) is present; document-only fields aren't the focus.
        assert f"/ims/case/v1p1/CFItems/{sample_document.identifier}" in resp.text

    async def test_pane_shows_full_detail(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The right pane now renders the same full-detail card as /uri/ (shared
        partial): it includes the permalink (/uri/{id}) and full-detail-only
        fields like the API URL — not just the lightweight summary."""
        item = _make_item(tenant, sample_document, full_statement="Link test")
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert resp.status_code == 200
        # Permalink to the standalone page is present (full-detail card).
        assert f"/uri/{item.identifier}" in resp.text
        # A field that only the full detail renders (CFItems API URL).
        assert f"/ims/case/v1p1/CFItems/{item.identifier}" in resp.text

    async def test_shows_related_groupings(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The tree detail pane shows outgoing non-isChildOf associations
        grouped by CFAssociationGrouping (same block as the full detail page)."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        dest = _make_item(tenant, sample_document, full_statement="Destination item")
        db_session.add_all([origin, dest])
        await db_session.flush()

        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/essential",
            title="Essential",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()

        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="isRelatedTo",
            origin_node_uri=f"https://example.com/uri/{origin.identifier}",
            origin_node_identifier=str(origin.identifier),
            destination_node_uri=f"https://example.com/uri/{dest.identifier}",
            destination_node_identifier=str(dest.identifier),
            destination_node_title="Destination item",
            cf_association_grouping_id=grouping.id,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}",
        )
        assert resp.status_code == 200
        assert "Essential" in resp.text  # grouping heading
        assert "Destination item" in resp.text  # related target title
        # Same-doc related item → in-pane navigation (path-form URL + push-url +
        # tree sync), NOT a full-page link to /uri/.
        item_url = f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{dest.identifier}"
        assert f'hx-push-url="{item_url}"' in resp.text
        assert f"selectTreeNode('{dest.identifier}')" in resp.text
        assert f"/uri/{dest.identifier}" not in resp.text

    async def test_related_link_cross_doc_links_out(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A related target that is NOT a CFItem in this document (cross-doc /
        external) keeps the full-page /uri/ link (Stage 5 will switch trees)."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        external_dest = uuid.uuid4()  # not a CFItem in this doc
        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/x",
            title="Essential",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="isRelatedTo",
            origin_node_uri=f"https://example.com/uri/{origin.identifier}",
            origin_node_identifier=str(origin.identifier),
            destination_node_uri=f"https://example.com/uri/{external_dest}",
            destination_node_identifier=str(external_dest),
            destination_node_title="External skill",
            cf_association_grouping_id=grouping.id,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert f"/uri/{external_dest}" in resp.text  # links out (full page)
        assert f"selectTreeNode('{external_dest}')" not in resp.text

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
