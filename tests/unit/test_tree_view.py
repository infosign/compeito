"""Tests for Web UI: tree view (Issue #37)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
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

    async def test_build_ssr_tree_depth1_query_count_is_bounded(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Depth 0-1 loads in a bounded number of queries regardless of how many
        roots there are — the bulk loader, not a query per root (#234 review)."""
        from sqlalchemy import event

        n_roots = 8
        for i in range(n_roots):
            root = _make_item(tenant, sample_document, full_statement=f"Root {i}", hcs=f"R{i}")
            child = _make_item(tenant, sample_document, full_statement=f"Child {i}", hcs=f"C{i}")
            db_session.add_all([root, child])
            db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=i))
            db_session.add(_make_is_child_of(sample_document, child.identifier, root.identifier, seq=1))
        await db_session.flush()

        count = 0

        def _before(*args, **kwargs):
            nonlocal count
            count += 1

        sync_engine = db_session.bind.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _before)
        try:
            roots, _orphans, _sel = await tree_service.build_ssr_tree(db_session, sample_document)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _before)

        assert len(roots) == n_roots
        assert all(r.is_expanded and len(r.children) == 1 for r in roots)
        # Bulk depth 0-1 is a small constant. The old per-root path would be
        # 3 + 3*n_roots (= 27 for 8 roots); guard well below that.
        assert count <= 12, f"build_ssr_tree used {count} queries for {n_roots} roots (should be bounded)"

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

    async def test_initial_tree_is_lazy_depth_0_1(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Lazy tree: the initial page SSRs only depth 0-1. A depth-2 grandchild
        is NOT in the page; its parent is a lazy <details> with an hx-get that
        fetches one level from the /children/ route on first open."""
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
        # depth 0 (root) and depth 1 (child) are SSR'd; depth 2 (grand) is not.
        assert "Root R" in resp.text
        assert "Child C" in resp.text
        assert "Grand G deep" not in resp.text
        # Rendered via native <details> (keyboard/SR-friendly expand).
        assert "<details" in resp.text
        # The child (which has the grandchild) is a lazy branch: its container
        # fetches one level from the /children/ route on first open.
        assert f"/cftree/doc/{sample_document.identifier}/children/{child.identifier}" in resp.text
        assert 'hx-trigger="toggle' in resp.text

    async def test_children_fragment_returns_one_level(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The /children/{parent} fragment returns the parent's immediate
        children (one level), each itself a tree node."""
        root = _make_item(tenant, sample_document, full_statement="Root R", hcs="R")
        child = _make_item(tenant, sample_document, full_statement="Child C", hcs="C")
        grand = _make_item(tenant, sample_document, full_statement="Grand G deep", hcs="G")
        db_session.add_all([root, child, grand])
        db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, child.identifier, root.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, grand.identifier, child.identifier, seq=1))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/{child.identifier}")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "public, max-age=86400"
        # the one level of children (the grandchild) is present; its own parent
        # (the child) is not re-rendered.
        assert "Grand G deep" in resp.text
        assert f'/item/{grand.identifier}"' in resp.text

    async def test_children_fragment_rejects_foreign_parent(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A parent_id not in this document → 404 (tree node ⟺ this doc)."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/children/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_deep_link_ssrs_ancestor_path(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Deep-link /item/{grandchild}: the ancestor path is SSR'd (the
        grandchild is in the page, expanded in context) — reload/share-safe even
        though the tree is otherwise lazy."""
        root = _make_item(tenant, sample_document, full_statement="Root R", hcs="R")
        child = _make_item(tenant, sample_document, full_statement="Child C", hcs="C")
        grand = _make_item(tenant, sample_document, full_statement="Grand G deep", hcs="G")
        db_session.add_all([root, child, grand])
        db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, child.identifier, root.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, grand.identifier, child.identifier, seq=1))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{grand.identifier}")
        assert resp.status_code == 200
        assert "Grand G deep" in resp.text  # ancestor path SSR'd to the target

    async def test_tree_accessibility_attributes(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A11y: decorative triangle/bullet icons are aria-hidden; the selected
        node carries aria-current; labels are real <a href> (no-JS reachable)."""
        root = _make_item(tenant, sample_document, full_statement="Root R", hcs="R")
        leaf = _make_item(tenant, sample_document, full_statement="Leaf L", hcs="L")
        db_session.add_all([root, leaf])
        db_session.add(_make_is_child_of(sample_document, root.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, leaf.identifier, root.identifier, seq=1))
        await db_session.flush()

        # Deep-link the leaf so it renders selected.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{leaf.identifier}")
        assert resp.status_code == 200
        assert 'aria-hidden="true"' in resp.text  # decorative icons
        assert 'aria-current="true"' in resp.text  # selected node
        # label remains a real link to the item's full SSR page (no-JS / crawler)
        assert f'href="/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{leaf.identifier}"' in resp.text

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

    async def test_tree_page_ships_sync_script(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The tree page carries the global tree↔pane sync (selectTreeNode +
        the htmx:afterSettle listener that reads the pushed /item/ URL)."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert "function selectTreeNode" in resp.text
        assert "htmx:afterSettle" in resp.text

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

    async def test_fragment_leads_with_name_heading(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The pane fragment leads with the statement as its heading; the
        identifier only appears later (header copy chip / technical section)."""
        item = _make_item(tenant, sample_document, full_statement="Heading target")
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}",
        )
        assert ">Heading target</h2>" in resp.text
        assert resp.text.index("Heading target") < resp.text.index(str(item.identifier))
        assert "技術情報" in resp.text

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
        # Same-doc related item → in-pane navigation (path-form URL + push-url),
        # NOT a full-page link to /uri/. (Tree sync runs from a global
        # htmx:afterSettle listener in base.html, not inline on this link.)
        item_url = f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{dest.identifier}"
        assert f'hx-push-url="{item_url}"' in resp.text
        assert f"/uri/{dest.identifier}" not in resp.text

    async def test_related_link_external_links_out(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A related target that resolves to no CFItem in this tenant is external:
        link out to its stored URI in a new tab with an "external" badge."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        external_dest = uuid.uuid4()  # not a CFItem in this tenant
        external_uri = f"https://other.example.org/uri/{external_dest}"
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
            destination_node_uri=external_uri,
            destination_node_identifier=str(external_dest),
            destination_node_title="External skill",
            cf_association_grouping_id=grouping.id,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert external_uri in resp.text  # links out to the stored URI
        assert 'target="_blank"' in resp.text
        assert "外部" in resp.text  # external badge (ja)
        # Not a tree switch / in-pane nav.
        assert f"/cftree/doc/{sample_document.identifier}/item/{external_dest}" not in resp.text

    async def test_related_link_unsafe_scheme_not_clickable(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """An external destination URI with a non-http(s) scheme (e.g.
        javascript:) is NOT linkified — rendered as plain text instead."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        external_dest = uuid.uuid4()
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="isRelatedTo",
            origin_node_uri=f"https://example.com/uri/{origin.identifier}",
            origin_node_identifier=str(origin.identifier),
            destination_node_uri="javascript:alert(1)",
            destination_node_identifier=str(external_dest),
            destination_node_title="Sketchy ref",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert "Sketchy ref" in resp.text  # shown as plain text
        assert "javascript:" not in resp.text  # never emitted as an href

    async def test_related_link_other_doc_switches_tree(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A related target that is a CFItem in ANOTHER document of the same
        tenant links to that document's tree (switch) with a badge."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        other = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/other-fw",
            title="Other Framework",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(other)
        await db_session.flush()
        dest = _make_item(tenant, other, full_statement="Cross-doc skill")
        db_session.add(dest)
        await db_session.flush()
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
            destination_node_uri=f"https://example.com/uri/{dest.identifier}",
            destination_node_identifier=str(dest.identifier),
            destination_node_title="Cross-doc skill",
            cf_association_grouping_id=grouping.id,
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        # Links to the OTHER document's tree (switch), selecting the dest item.
        assert f"/cftree/doc/{other.identifier}/item/{dest.identifier}" in resp.text
        assert "別フレームワーク" in resp.text  # other-framework badge (ja)

    async def test_related_items_sorted_by_tree_key(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Related items render in the tree's order (hcs natural sort), not by
        association title. SK.2 (< SK.10 naturally) comes before SK.10 even
        though its title sorts later."""
        origin = _make_item(tenant, sample_document, full_statement="Origin")
        # Titles chosen so title-order (Alpha < Beta) is the OPPOSITE of hcs-order.
        late = _make_item(tenant, sample_document, full_statement="Alpha skill", hcs="SK.10")
        early = _make_item(tenant, sample_document, full_statement="Beta skill", hcs="SK.2")
        db_session.add_all([origin, late, early])
        await db_session.flush()
        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/e",
            title="Essential skill",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()
        for dest in (late, early):
            db_session.add(
                CFAssociation(
                    tenant_id=tenant.id,
                    cf_document_id=sample_document.id,
                    identifier=uuid.uuid4(),
                    uri="https://example.com/assoc/" + str(uuid.uuid4()),
                    association_type="isRelatedTo",
                    origin_node_uri=f"https://example.com/uri/{origin.identifier}",
                    origin_node_identifier=str(origin.identifier),
                    destination_node_uri=f"https://example.com/uri/{dest.identifier}",
                    destination_node_identifier=str(dest.identifier),
                    destination_node_title=dest.full_statement,
                    cf_association_grouping_id=grouping.id,
                    last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        # hcs natsort: SK.2 (Beta) before SK.10 (Alpha) — opposite of title order.
        assert resp.text.index("Beta skill") < resp.text.index("Alpha skill")

    async def test_related_items_sequence_number_overrides_hcs(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """When related items are tree children, their isChildOf sequence_number
        is the tree's primary key and must win over hcs (matches the tree order).
        seq: A=1, B=2 but hcs: A=SK.10, B=SK.2 → tree shows A before B."""
        origin = _make_item(tenant, sample_document, full_statement="Origin")
        a = _make_item(tenant, sample_document, full_statement="Skill A", hcs="SK.10")
        b = _make_item(tenant, sample_document, full_statement="Skill B", hcs="SK.2")
        db_session.add_all([origin, a, b])
        await db_session.flush()
        # A and B are tree children of the document with seq 1 and 2.
        db_session.add(_make_is_child_of(sample_document, a.identifier, sample_document.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, b.identifier, sample_document.identifier, seq=2))
        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/e",
            title="Essential skill",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()
        for dest in (b, a):  # add in reverse to prove sorting isn't insertion order
            db_session.add(
                CFAssociation(
                    tenant_id=tenant.id,
                    cf_document_id=sample_document.id,
                    identifier=uuid.uuid4(),
                    uri="https://example.com/assoc/" + str(uuid.uuid4()),
                    association_type="isRelatedTo",
                    origin_node_uri=f"https://example.com/uri/{origin.identifier}",
                    origin_node_identifier=str(origin.identifier),
                    destination_node_uri=f"https://example.com/uri/{dest.identifier}",
                    destination_node_identifier=str(dest.identifier),
                    destination_node_title=dest.full_statement,
                    cf_association_grouping_id=grouping.id,
                    last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        # seq 1 (A) before seq 2 (B), even though hcs SK.2 (B) < SK.10 (A).
        assert resp.text.index("Skill A") < resp.text.index("Skill B")

    async def test_related_items_ordered_by_full_tree_path(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Cross-branch ordering follows the full root→node path, not the item's
        own sibling seq. branchY (root seq=1) > branchX (root seq=2); childA is
        under branchX with its own seq=1, childB under branchY with seq=99. The
        tree shows branchY's subtree first → B before A, even though A's own
        seq (1) < B's own seq (99)."""
        origin = _make_item(tenant, sample_document, full_statement="Origin")
        branch_x = _make_item(tenant, sample_document, full_statement="Branch X")
        branch_y = _make_item(tenant, sample_document, full_statement="Branch Y")
        child_a = _make_item(tenant, sample_document, full_statement="Child A")
        child_b = _make_item(tenant, sample_document, full_statement="Child B")
        db_session.add_all([origin, branch_x, branch_y, child_a, child_b])
        await db_session.flush()
        # Roots under the document: Y first (seq 1), X second (seq 2).
        db_session.add(_make_is_child_of(sample_document, branch_x.identifier, sample_document.identifier, seq=2))
        db_session.add(_make_is_child_of(sample_document, branch_y.identifier, sample_document.identifier, seq=1))
        # A under X (own seq 1); B under Y (own seq 99).
        db_session.add(_make_is_child_of(sample_document, child_a.identifier, branch_x.identifier, seq=1))
        db_session.add(_make_is_child_of(sample_document, child_b.identifier, branch_y.identifier, seq=99))
        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/e",
            title="Essential skill",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()
        for dest in (child_a, child_b):
            db_session.add(
                CFAssociation(
                    tenant_id=tenant.id,
                    cf_document_id=sample_document.id,
                    identifier=uuid.uuid4(),
                    uri="https://example.com/assoc/" + str(uuid.uuid4()),
                    association_type="isRelatedTo",
                    origin_node_uri=f"https://example.com/uri/{origin.identifier}",
                    origin_node_identifier=str(origin.identifier),
                    destination_node_uri=f"https://example.com/uri/{dest.identifier}",
                    destination_node_identifier=str(dest.identifier),
                    destination_node_title=dest.full_statement,
                    cf_association_grouping_id=grouping.id,
                    last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        # Full-path order: branchY (root seq 1) subtree first → Child B before Child A.
        assert resp.text.index("Child B") < resp.text.index("Child A")

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


class TestDefinitionsTree:
    """Stage 4a: definitions referenced by a document appear as navigable tree
    nodes, and are shown in the right pane via the generalized detail fragment."""

    NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

    async def test_definitions_section_lists_referenced_lookups(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/it",
            title="Knowledge Type",
            last_change_date_time=self.NOW,
        )
        db_session.add(it)
        await db_session.flush()
        item = _make_item(tenant, sample_document, full_statement="Item with a type")
        item.cf_item_type_id = it.id
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        assert "定義" in resp.text  # Definitions section heading (ja)
        assert "Knowledge Type" in resp.text  # the item-type node
        # Navigable as a tree item (path-form URL).
        assert f"/cftree/doc/{sample_document.identifier}/item/{it.identifier}" in resp.text

    async def test_definition_rendered_in_pane(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/it2",
            title="Skill Type",
            type_code="ST",
            last_change_date_time=self.NOW,
        )
        db_session.add(it)
        await db_session.flush()
        # Reference it from an item so it belongs to this document's definitions.
        item = _make_item(tenant, sample_document, full_statement="Item with skill type")
        item.cf_item_type_id = it.id
        db_session.add(item)
        await db_session.flush()

        # The generalized detail fragment resolves any resource type.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{it.identifier}")
        assert resp.status_code == 200
        assert "Skill Type" in resp.text
        assert "ST" in resp.text  # type_code shown in the lookup detail

    async def test_unreferenced_lookup_rejected_in_pane(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A lookup the document does NOT reference has no tree node, so the
        detail fragment must 404 it (pane content == tree node invariant)."""
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/it3",
            title="Orphan Type",
            last_change_date_time=self.NOW,
        )
        db_session.add(it)
        await db_session.flush()

        # Fragment route → 404.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{it.identifier}")
        assert resp.status_code == 404
        # Full-page route (reload/share scenario) → 404 too.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{it.identifier}")
        assert resp.status_code == 404

    async def test_selected_definition_section_auto_opens(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Loading /item/{lookup} directly opens the Definitions section and the
        lookup's type subgroup so the highlighted node is visible (not hidden in
        a collapsed <details>)."""
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/it4",
            title="Opened Type",
            last_change_date_time=self.NOW,
        )
        db_session.add(it)
        await db_session.flush()
        item = _make_item(tenant, sample_document, full_statement="Item with opened type")
        item.cf_item_type_id = it.id
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{it.identifier}")
        assert resp.status_code == 200
        # Both the Definitions section and the item-type subgroup carry `open`.
        assert resp.text.count(" open>") >= 2

    async def test_no_definitions_section_when_empty(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A document with no referenced lookups shows no Definitions section."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        assert "定義" not in resp.text

    async def test_item_definition_reference_is_pane_nav(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """An item's definition reference (item type) is a clickable in-pane nav
        link to that definition's tree node (not dead code text)."""
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/it",
            title="Knowledge Type",
            last_change_date_time=self.NOW,
        )
        db_session.add(it)
        await db_session.flush()
        item = _make_item(tenant, sample_document, full_statement="Item with a type")
        item.cf_item_type_id = it.id
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{item.identifier}")
        assert resp.status_code == 200
        # The item-type title links via in-pane HTMX nav to its tree node.
        item_url = f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{it.identifier}"
        assert f'hx-push-url="{item_url}"' in resp.text


class TestRubricsTree:
    """Stage 4b: rubrics appear as nested navigable tree nodes (CFRubric ->
    Criterion -> Level), shown in the right pane via the detail fragment."""

    NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

    async def _make_rubric_tree(self, db_session, tenant, doc):
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=doc.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/r",
            title="Assessment Rubric",
            last_change_date_time=self.NOW,
        )
        db_session.add(rubric)
        await db_session.flush()
        crit = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/c",
            category="Clarity",
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add(crit)
        await db_session.flush()
        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=crit.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/l",
            quality="Excellent",
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add(level)
        await db_session.flush()
        return rubric, crit, level

    async def test_rubrics_section_lists_rubric_criteria_levels(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric, crit, level = await self._make_rubric_tree(db_session, tenant, sample_document)
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        assert "ルーブリック" in resp.text  # Rubrics section heading (ja)
        assert "Assessment Rubric" in resp.text
        assert "Clarity" in resp.text  # criterion category as node label
        assert "Excellent" in resp.text  # level quality as node label
        # Navigable as tree nodes (path-form URLs).
        assert f"/cftree/doc/{sample_document.identifier}/item/{rubric.identifier}" in resp.text
        assert f"/cftree/doc/{sample_document.identifier}/item/{level.identifier}" in resp.text

    async def test_rubric_part_rendered_in_pane(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric, crit, level = await self._make_rubric_tree(db_session, tenant, sample_document)
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{crit.identifier}")
        assert resp.status_code == 200
        assert "Clarity" in resp.text

    async def test_selected_rubric_part_auto_opens_path(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Loading /item/{level} opens the Rubrics section + the ancestor rubric
        and criterion <details> so the selected node isn't hidden."""
        rubric, crit, level = await self._make_rubric_tree(db_session, tenant, sample_document)
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{level.identifier}")
        assert resp.status_code == 200
        # Section + rubric + criterion all carry `open`.
        assert resp.text.count(" open>") >= 3

    async def test_rubric_part_from_other_doc_rejected(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A rubric part belonging to another document has no node in this tree,
        so both the fragment and full-page routes 404 it."""
        other = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/other",
            title="Other Doc",
            last_change_date_time=self.NOW,
        )
        db_session.add(other)
        await db_session.flush()
        rubric, crit, level = await self._make_rubric_tree(db_session, tenant, other)
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{crit.identifier}")
        assert resp.status_code == 404
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/item/{level.identifier}")
        assert resp.status_code == 404

    async def test_no_rubrics_section_when_empty(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A document with no rubrics shows no Rubrics tree section."""
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        assert "ルーブリック" not in resp.text

    async def test_criteria_and_levels_sorted_by_position(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Criteria and levels render in position order (not DB return order),
        matching the detail card's `sort(attribute='position,identifier')`."""
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/r",
            title="Ordered Rubric",
            last_change_date_time=self.NOW,
        )
        db_session.add(rubric)
        await db_session.flush()
        # Insert out of position order so DB order != position order.
        c_beta = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/cb",
            category="Beta",
            position=2,
            last_change_date_time=self.NOW,
        )
        c_alpha = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/ca",
            category="Alpha",
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add_all([c_beta, c_alpha])
        await db_session.flush()
        lv_hi = CFRubricCriterionLevel(
            cf_rubric_criterion_id=c_alpha.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/lh",
            quality="ZZZ-high",
            position=2,
            last_change_date_time=self.NOW,
        )
        lv_lo = CFRubricCriterionLevel(
            cf_rubric_criterion_id=c_alpha.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/ll",
            quality="AAA-low",
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add_all([lv_hi, lv_lo])
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}")
        assert resp.status_code == 200
        # Criteria: position 1 (Alpha) before position 2 (Beta).
        assert resp.text.index("Alpha") < resp.text.index("Beta")
        # Levels: position 1 (AAA-low) before position 2 (ZZZ-high).
        assert resp.text.index("AAA-low") < resp.text.index("ZZZ-high")

    async def test_standalone_show_in_tree_selects_rubric_part(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """The standalone /uri/ page's "Show in tree" link targets the node's
        own /item/{id} so the tree selects it (not just the document root)."""
        rubric, crit, level = await self._make_rubric_tree(db_session, tenant, sample_document)
        for part in (rubric, crit, level):
            resp = await db_client.get(f"/{tenant.id}/uri/{part.identifier}")
            assert resp.status_code == 200
            assert f"/cftree/doc/{sample_document.identifier}/item/{part.identifier}" in resp.text

    async def test_rubric_cross_links_are_pane_nav(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """Stage 5 B/F/G: rubric <-> item cross-links navigate in-pane when the
        target is a node in the current document's tree."""
        item = _make_item(tenant, sample_document, full_statement="Linked competency")
        db_session.add(item)
        await db_session.flush()
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/r",
            title="Assessment Rubric",
            last_change_date_time=self.NOW,
        )
        db_session.add(rubric)
        await db_session.flush()
        crit = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/c",
            category="Clarity",
            cf_item_id=item.id,
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add(crit)
        await db_session.flush()
        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=crit.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/l",
            quality="Good",
            position=1,
            last_change_date_time=self.NOW,
        )
        db_session.add(level)
        await db_session.flush()

        base = f"/{tenant.id}/cftree/doc/{sample_document.identifier}"
        # Criterion pane: linked item (F) and parent rubric (F) are in-pane nav.
        resp = await db_client.get(f"{base}/detail/{crit.identifier}")
        assert resp.status_code == 200
        assert f'hx-push-url="{base}/item/{item.identifier}"' in resp.text
        assert f'hx-push-url="{base}/item/{rubric.identifier}"' in resp.text
        # Level pane: parent criterion (G) is in-pane nav.
        resp = await db_client.get(f"{base}/detail/{level.identifier}")
        assert resp.status_code == 200
        assert f'hx-push-url="{base}/item/{crit.identifier}"' in resp.text
        # Item pane: referring criterion (B) is in-pane nav.
        resp = await db_client.get(f"{base}/detail/{item.identifier}")
        assert resp.status_code == 200
        assert f'hx-push-url="{base}/item/{crit.identifier}"' in resp.text


class TestAssociationNodeLinks:
    """Stage 5 D: CFAssociation origin/destination nodes are classified like the
    related list — in-doc items navigate in-pane, external refs link out."""

    NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

    async def test_association_nodes_classified(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        ext = uuid.uuid4()
        ext_uri = f"https://other.example.org/uri/{ext}"
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="isRelatedTo",
            origin_node_uri=f"https://example.com/uri/{origin.identifier}",
            origin_node_identifier=str(origin.identifier),
            origin_node_title="Origin item",
            destination_node_uri=ext_uri,
            destination_node_identifier=str(ext),
            destination_node_title="External thing",
            last_change_date_time=self.NOW,
        )
        db_session.add(assoc)
        await db_session.flush()

        base = f"/{tenant.id}/cftree/doc/{sample_document.identifier}"
        resp = await db_client.get(f"{base}/detail/{assoc.identifier}")
        assert resp.status_code == 200
        # Origin is an in-doc item → in-pane nav.
        assert f'hx-push-url="{base}/item/{origin.identifier}"' in resp.text
        # Destination is external → link out in a new tab.
        assert ext_uri in resp.text
        assert 'target="_blank"' in resp.text


class TestCrossDocHierarchy:
    """Cross-document isChildOf neighbors surface in the pane's 上位/下位(別FW)
    sections, while same-document hierarchy stays in the tree only."""

    NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def _ischildof(self, tenant, owner_doc, child_ident, parent_ident):
        return CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=owner_doc.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="isChildOf",
            origin_node_uri=f"https://example.com/uri/{child_ident}",
            origin_node_identifier=str(child_ident),
            destination_node_uri=f"https://example.com/uri/{parent_ident}",
            destination_node_identifier=str(parent_ident),
            last_change_date_time=self.NOW,
        )

    async def test_cross_doc_parent_and_child_in_pane(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        parent = _make_item(tenant, sample_document, full_statement="Parent group", hcs="C7")
        db_session.add(parent)
        await db_session.flush()
        other = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/sub-fw",
            title="Sub framework",
            last_change_date_time=self.NOW,
        )
        db_session.add(other)
        await db_session.flush()
        child = _make_item(tenant, other, full_statement="Child node", hcs="C71")
        db_session.add(child)
        await db_session.flush()
        # Cross-document isChildOf: origin=child (in other doc), destination=parent.
        db_session.add(self._ischildof(tenant, sample_document, child.identifier, parent.identifier))
        await db_session.flush()

        # Parent's pane → 下位（別FW） linking to the child's framework.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{parent.identifier}")
        assert resp.status_code == 200
        assert "下位" in resp.text
        assert f"/cftree/doc/{other.identifier}/item/{child.identifier}" in resp.text

        # Child's pane → 上位（別FW） linking back to the parent's framework.
        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{other.identifier}/detail/{child.identifier}")
        assert resp.status_code == 200
        assert "上位" in resp.text
        assert f"/cftree/doc/{sample_document.identifier}/item/{parent.identifier}" in resp.text

    async def test_same_doc_hierarchy_not_in_cross_section(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A same-document isChildOf child is in the tree, not the 下位(別FW) section."""
        parent = _make_item(tenant, sample_document, full_statement="Parent")
        child = _make_item(tenant, sample_document, full_statement="Same-doc child")
        db_session.add_all([parent, child])
        await db_session.flush()
        db_session.add(self._ischildof(tenant, sample_document, child.identifier, parent.identifier))
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{parent.identifier}")
        assert resp.status_code == 200
        assert "下位（別フレームワーク）" not in resp.text


class TestCrossTenantAssociations:
    """A CFAssociation endpoint whose node_uri points at a CFItem in ANOTHER
    tenant on this same compeito instance is resolved when that tenant is
    public: the detail pane shows the target title, a link that switches to the
    other tenant's tree, and an "other institution" badge. Private other tenants
    are fully hidden (no title, no URI). True external hosts link out as before.
    """

    NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

    async def _other_tenant(self, db_session: AsyncSession, *, is_private: bool, slug: str | None = None) -> Tenant:
        t = Tenant(id=uuid.uuid4(), name="Other Inst", is_private=is_private, slug=slug)
        db_session.add(t)
        await db_session.flush()
        return t

    async def _doc(self, db_session: AsyncSession, other_tenant: Tenant) -> CFDocument:
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/other-fw",
            title="Other Framework",
            last_change_date_time=self.NOW,
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    def _internal_uri(self, tenant_id, item_ident) -> str:
        # Must match settings.base_url so the URI is recognized as internal.
        return f"{settings.base_url}/{tenant_id}/uri/{item_ident}"

    async def _related_assoc(self, db_session, tenant, sample_document, origin, dest_ident, dest_uri, *, title) -> None:
        grouping = CFAssociationGrouping(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/grp/" + str(uuid.uuid4()),
            title="Essential",
            last_change_date_time=self.NOW,
        )
        db_session.add(grouping)
        await db_session.flush()
        db_session.add(
            CFAssociation(
                tenant_id=tenant.id,
                cf_document_id=sample_document.id,
                identifier=uuid.uuid4(),
                uri="https://example.com/assoc/" + str(uuid.uuid4()),
                association_type="isRelatedTo",
                origin_node_uri=self._internal_uri(tenant.id, origin.identifier),
                origin_node_identifier=str(origin.identifier),
                destination_node_uri=dest_uri,
                destination_node_identifier=str(dest_ident),
                destination_node_title=title,
                cf_association_grouping_id=grouping.id,
                last_change_date_time=self.NOW,
            )
        )
        await db_session.flush()

    async def test_public_other_tenant_resolved_with_badge(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        other_tenant = await self._other_tenant(db_session, is_private=False)
        other_doc = await self._doc(db_session, other_tenant)
        dest = _make_item(other_tenant, other_doc, full_statement="Cross-tenant skill")
        db_session.add(dest)
        await db_session.flush()
        await self._related_assoc(
            db_session,
            tenant,
            sample_document,
            origin,
            dest.identifier,
            self._internal_uri(other_tenant.id, dest.identifier),
            title="Cross-tenant skill",
        )

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert "Cross-tenant skill" in resp.text
        # Link switches to the OTHER tenant's tree (segment = its UUID, no slug).
        assert f"/{other_tenant.id}/cftree/doc/{other_doc.identifier}/item/{dest.identifier}" in resp.text
        assert "他機関" in resp.text  # other-institution badge (ja)

    async def test_public_other_tenant_uses_slug_segment(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """When the other tenant has a slug, the switch link uses the slug."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        other_tenant = await self._other_tenant(db_session, is_private=False, slug="other-inst")
        other_doc = await self._doc(db_session, other_tenant)
        dest = _make_item(other_tenant, other_doc, full_statement="Slug skill")
        db_session.add(dest)
        await db_session.flush()
        await self._related_assoc(
            db_session,
            tenant,
            sample_document,
            origin,
            dest.identifier,
            self._internal_uri(other_tenant.id, dest.identifier),
            title="Slug skill",
        )

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert f"/other-inst/cftree/doc/{other_doc.identifier}/item/{dest.identifier}" in resp.text

    async def test_private_other_tenant_fully_hidden(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        other_tenant = await self._other_tenant(db_session, is_private=True)
        other_doc = await self._doc(db_session, other_tenant)
        dest = _make_item(other_tenant, other_doc, full_statement="Secret skill")
        db_session.add(dest)
        await db_session.flush()
        dest_uri = self._internal_uri(other_tenant.id, dest.identifier)
        await self._related_assoc(
            db_session,
            tenant,
            sample_document,
            origin,
            dest.identifier,
            dest_uri,
            title="Secret skill title",
        )

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        # Nothing about the private tenant is surfaced: not the title, not the URI,
        # not a link to its tree.
        assert "Secret skill title" not in resp.text
        assert str(dest.identifier) not in resp.text
        assert str(other_tenant.id) not in resp.text
        assert "他機関" not in resp.text

    async def test_assoc_self_detail_hides_private_endpoint_uri(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """CFAssociation の自己詳細 (/uri/{assoc}) で destination が private 別テナントを
        指す場合、raw URI（private permalink）を一切出さない（案A）。public な origin
        テナントの association 経由で private テナントの URL が漏れるのを防ぐ。"""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        private_tenant = await self._other_tenant(db_session, is_private=True)
        priv_doc = await self._doc(db_session, private_tenant)
        dest = _make_item(private_tenant, priv_doc, full_statement="Secret skill")
        db_session.add(dest)
        await db_session.flush()
        private_uri = self._internal_uri(private_tenant.id, dest.identifier)
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/assoc/" + str(uuid.uuid4()),
            association_type="exactMatchOf",
            origin_node_uri=self._internal_uri(tenant.id, origin.identifier),
            origin_node_identifier=str(origin.identifier),
            destination_node_uri=private_uri,
            destination_node_identifier=str(dest.identifier),
            destination_node_title="Secret skill",
            last_change_date_time=self.NOW,
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{assoc.identifier}")
        assert resp.status_code == 200
        # private permalink(URI) も private テナント UUID も出ない → URL 復元不可
        assert private_uri not in resp.text
        assert str(private_tenant.id) not in resp.text

    async def test_true_external_host_links_out(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A destination on a DIFFERENT host is a real external reference: it
        still links out in a new tab (unchanged behavior)."""
        origin = _make_item(tenant, sample_document, full_statement="Origin item")
        db_session.add(origin)
        await db_session.flush()
        external_dest = uuid.uuid4()
        external_uri = f"https://other.example.org/x/uri/{external_dest}"
        await self._related_assoc(
            db_session,
            tenant,
            sample_document,
            origin,
            external_dest,
            external_uri,
            title="External skill",
        )

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{origin.identifier}")
        assert resp.status_code == 200
        assert external_uri in resp.text
        assert 'target="_blank"' in resp.text
        assert "External skill" in resp.text

    async def test_cross_tenant_ischildof_in_hierarchy(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A cross-tenant isChildOf parent (public other tenant) surfaces in the
        上位（別FW）section with a link to the other tenant's tree + badge."""
        child = _make_item(tenant, sample_document, full_statement="Child item", hcs="C1")
        db_session.add(child)
        await db_session.flush()
        other_tenant = await self._other_tenant(db_session, is_private=False)
        other_doc = await self._doc(db_session, other_tenant)
        parent = _make_item(other_tenant, other_doc, full_statement="Parent group", hcs="C0")
        db_session.add(parent)
        await db_session.flush()
        # isChildOf owned by current tenant: origin=child (here), destination=parent (other tenant).
        db_session.add(
            CFAssociation(
                tenant_id=tenant.id,
                cf_document_id=sample_document.id,
                identifier=uuid.uuid4(),
                uri="https://example.com/assoc/" + str(uuid.uuid4()),
                association_type="isChildOf",
                origin_node_uri=self._internal_uri(tenant.id, child.identifier),
                origin_node_identifier=str(child.identifier),
                destination_node_uri=self._internal_uri(other_tenant.id, parent.identifier),
                destination_node_identifier=str(parent.identifier),
                last_change_date_time=self.NOW,
            )
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{child.identifier}")
        assert resp.status_code == 200
        assert "上位" in resp.text
        assert f"/{other_tenant.id}/cftree/doc/{other_doc.identifier}/item/{parent.identifier}" in resp.text
        assert "他機関" in resp.text

    async def test_private_other_tenant_ischildof_hidden(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A cross-tenant isChildOf parent in a PRIVATE tenant is not surfaced at
        all (no 上位 entry, no link)."""
        child = _make_item(tenant, sample_document, full_statement="Child item", hcs="C1")
        db_session.add(child)
        await db_session.flush()
        other_tenant = await self._other_tenant(db_session, is_private=True)
        other_doc = await self._doc(db_session, other_tenant)
        parent = _make_item(other_tenant, other_doc, full_statement="Secret parent", hcs="C0")
        db_session.add(parent)
        await db_session.flush()
        db_session.add(
            CFAssociation(
                tenant_id=tenant.id,
                cf_document_id=sample_document.id,
                identifier=uuid.uuid4(),
                uri="https://example.com/assoc/" + str(uuid.uuid4()),
                association_type="isChildOf",
                origin_node_uri=self._internal_uri(tenant.id, child.identifier),
                origin_node_identifier=str(child.identifier),
                destination_node_uri=self._internal_uri(other_tenant.id, parent.identifier),
                destination_node_identifier=str(parent.identifier),
                last_change_date_time=self.NOW,
            )
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/cftree/doc/{sample_document.identifier}/detail/{child.identifier}")
        assert resp.status_code == 200
        assert "Secret parent" not in resp.text
        assert str(parent.identifier) not in resp.text
        assert str(other_tenant.id) not in resp.text


class TestErrorFragmentEscaping:
    """`_error_fragment` builds raw HTML, so it must HTML-escape its message
    (defense-in-depth: callers pass static translations today, but a future
    caller passing user/import text must not yield reflected XSS)."""

    def test_error_fragment_escapes_message(self):
        from src.routers.web import _error_fragment

        resp = _error_fragment(404, "<script>alert(1)</script>&\"'")
        body = resp.body.decode()
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body
        assert resp.status_code == 404
