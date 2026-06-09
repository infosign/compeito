"""Tree view query service for the Web UI."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import natsort
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class TreeNode:
    """A node in the tree view."""

    item: CFItem
    seq: int | None  # sequence_number from isChildOf association
    has_children: bool = False
    children: list[TreeNode] = field(default_factory=list)
    is_expanded: bool = False  # True = ▼, False = ▶


# ---------------------------------------------------------------------------
# Sort helper (same rule as csv_export / children endpoint spec)
# ---------------------------------------------------------------------------

_natsort_key = natsort.natsort_keygen()


def _child_sort_key(node: TreeNode) -> tuple:
    """seq ASC (NULL last) -> hcs natsort (NULL last) -> identifier."""
    seq = node.seq
    hcs = node.item.human_coding_scheme
    ident = str(node.item.identifier)
    return (
        (0, seq) if seq is not None else (1, 0),
        (0, _natsort_key(hcs)) if hcs else (1, ()),
        ident,
    )


def _strs_to_uuids(idents: list[str]) -> list[uuid.UUID]:
    """Convert string identifiers to UUIDs, skipping invalid ones."""
    result = []
    for s in idents:
        try:
            result.append(uuid.UUID(s))
        except (ValueError, AttributeError):
            pass
    return result


# ---------------------------------------------------------------------------
# Core queries
# ---------------------------------------------------------------------------


async def get_document_for_tree(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc_identifier: uuid.UUID,
) -> CFDocument | None:
    """Load a document by identifier with license joinedload."""
    result = await session.execute(
        select(CFDocument)
        .options(joinedload(CFDocument.license))
        .where(
            CFDocument.tenant_id == tenant_id,
            CFDocument.identifier == doc_identifier,
        )
    )
    return result.scalar_one_or_none()


async def get_children(
    session: AsyncSession,
    doc_id: uuid.UUID,
    parent_identifier: str,
) -> list[TreeNode]:
    """Get child items of a parent via isChildOf associations within a document.

    Returns sorted TreeNodes with has_children populated.
    """
    # Find isChildOf associations where destination = parent
    assoc_result = await session.execute(
        select(CFAssociation).where(
            CFAssociation.cf_document_id == doc_id,
            CFAssociation.association_type == "isChildOf",
            CFAssociation.destination_node_identifier == parent_identifier,
        )
    )
    assocs = assoc_result.scalars().all()
    if not assocs:
        return []

    # origin isChildOf destination = origin is child of destination
    # Collect child identifiers with best sequence_number
    child_info: dict[str, int | None] = {}
    for a in assocs:
        ident = a.origin_node_identifier
        new_seq = a.sequence_number
        if ident not in child_info:
            child_info[ident] = new_seq
        else:
            old_seq = child_info[ident]
            # Pick min seq; NULL last
            if new_seq is not None:
                if old_seq is None or new_seq < old_seq:
                    child_info[ident] = new_seq

    # Load child items by UUID
    child_uuids = _strs_to_uuids(list(child_info.keys()))
    if not child_uuids:
        return []

    item_result = await session.execute(
        select(CFItem)
        .options(joinedload(CFItem.item_type))
        .where(
            CFItem.cf_document_id == doc_id,
            CFItem.identifier.in_(child_uuids),
        )
    )
    items_by_ident = {str(i.identifier): i for i in item_result.scalars().unique().all()}

    # Build nodes
    nodes = []
    for ident, seq in child_info.items():
        item = items_by_ident.get(ident)
        if item is not None:
            nodes.append(TreeNode(item=item, seq=seq))

    # Batch check which children have their own children
    if nodes:
        has_children_set = await _get_idents_with_children(
            session,
            doc_id,
            [str(n.item.identifier) for n in nodes],
        )
        for n in nodes:
            n.has_children = str(n.item.identifier) in has_children_set

    nodes.sort(key=_child_sort_key)
    return nodes


async def get_orphan_items(
    session: AsyncSession,
    doc_id: uuid.UUID,
) -> list[TreeNode]:
    """Get items with no isChildOf association within the same document.

    depth=0 items whose identifier is NOT an origin in any isChildOf
    association within this document.
    """
    # All origin identifiers from isChildOf in this document
    origin_result = await session.execute(
        select(CFAssociation.origin_node_identifier)
        .where(
            CFAssociation.cf_document_id == doc_id,
            CFAssociation.association_type == "isChildOf",
        )
        .distinct()
    )
    origin_idents = {row[0] for row in origin_result.all()}

    # All depth=0 items
    item_result = await session.execute(
        select(CFItem).options(joinedload(CFItem.item_type)).where(CFItem.cf_document_id == doc_id, CFItem.depth == 0)
    )
    depth0_items = item_result.scalars().unique().all()

    orphans = [i for i in depth0_items if str(i.identifier) not in origin_idents]
    nodes = [TreeNode(item=i, seq=None) for i in orphans]

    if nodes:
        has_children_set = await _get_idents_with_children(
            session,
            doc_id,
            [str(n.item.identifier) for n in nodes],
        )
        for n in nodes:
            n.has_children = str(n.item.identifier) in has_children_set

    nodes.sort(key=_child_sort_key)
    return nodes


async def build_full_tree(
    session: AsyncSession,
    doc: CFDocument,
    selected_item_ident: uuid.UUID | None = None,
) -> tuple[list[TreeNode], list[TreeNode], CFItem | None]:
    """Build the COMPLETE tree (all descendants) in one pass for full SSR.

    Fetches every isChildOf association and item for the document once (no
    N+1), assembles the nested tree in memory, and marks `is_expanded` so the
    template renders `<details open>` for top-level nodes and the ancestor path
    of a deep-linked `selected_item`. All nodes are present in the DOM, so the
    `<details>` expand/collapse needs no JavaScript or server round-trip.

    Returns (root_nodes, orphan_nodes, selected_item_or_None). Multi-parent
    items appear under each parent (same as the lazy renderer); a per-path
    visited set prevents infinite recursion on cyclic isChildOf data.
    """
    doc_id = doc.id
    doc_ident = str(doc.identifier)

    # All isChildOf edges in the document (origin = child, destination = parent).
    assoc_rows = (
        await session.execute(
            select(
                CFAssociation.origin_node_identifier,
                CFAssociation.destination_node_identifier,
                CFAssociation.sequence_number,
            ).where(
                CFAssociation.cf_document_id == doc_id,
                CFAssociation.association_type == "isChildOf",
            )
        )
    ).all()

    children_by_parent: dict[str, dict[str, int | None]] = {}
    origin_idents: set[str] = set()
    for origin, dest, seq in assoc_rows:
        origin_idents.add(origin)
        kids = children_by_parent.setdefault(dest, {})
        if origin not in kids:
            kids[origin] = seq
        elif seq is not None and (kids[origin] is None or seq < kids[origin]):
            kids[origin] = seq  # keep min seq (NULL last)

    # All items, mapped by identifier (item_type eager-loaded for the badge).
    item_rows = (
        (
            await session.execute(
                select(CFItem).options(joinedload(CFItem.item_type)).where(CFItem.cf_document_id == doc_id)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items_by_ident = {str(i.identifier): i for i in item_rows}

    # Ancestor path of the deep-linked item → which <details> to open.
    selected_item = None
    expand_set: set[str] = set()
    if selected_item_ident is not None:
        selected_item = await _resolve_selected_item(session, doc_id, selected_item_ident)
        if selected_item is not None:
            sid = str(selected_item.identifier)
            expand_set = set(await _get_ancestor_path(session, doc, sid))
            expand_set.add(sid)

    def build(parent_ident: str, depth: int, ancestry: frozenset[str]) -> list[TreeNode]:
        kids = children_by_parent.get(parent_ident)
        if not kids:
            return []
        nodes: list[TreeNode] = []
        for child_ident, seq in kids.items():
            if child_ident in ancestry:  # cycle guard (per path)
                continue
            item = items_by_ident.get(child_ident)
            if item is None:
                continue
            node = TreeNode(item=item, seq=seq)
            node.children = build(child_ident, depth + 1, ancestry | {child_ident})
            node.has_children = bool(node.children)
            # Open top level by default + the deep-linked ancestor path.
            node.is_expanded = depth == 0 or child_ident in expand_set
            nodes.append(node)
        nodes.sort(key=_child_sort_key)
        return nodes

    root_nodes = build(doc_ident, 0, frozenset({doc_ident}))

    # Orphans: depth-0 items that are a child of nothing (no isChildOf origin).
    orphan_nodes: list[TreeNode] = []
    for ident, item in items_by_ident.items():
        if item.depth == 0 and ident not in origin_idents:
            node = TreeNode(item=item, seq=None)
            node.children = build(ident, 1, frozenset({doc_ident, ident}))
            node.has_children = bool(node.children)
            node.is_expanded = ident in expand_set
            orphan_nodes.append(node)
    orphan_nodes.sort(key=_child_sort_key)

    return root_nodes, orphan_nodes, selected_item


async def build_ssr_tree(
    session: AsyncSession,
    doc: CFDocument,
    selected_item_ident: uuid.UUID | None = None,
) -> tuple[list[TreeNode], list[TreeNode], CFItem | None]:
    """Build the initial SSR tree (depth 0-1).

    Returns (root_nodes, orphan_nodes, selected_item_or_None).
    """
    doc_id = doc.id
    doc_ident = str(doc.identifier)

    # Root children (children of the document)
    root_nodes = await get_children(session, doc_id, doc_ident)

    # Expand depth 0 nodes to show depth 1
    for node in root_nodes:
        if node.has_children:
            node.children = await get_children(
                session,
                doc_id,
                str(node.item.identifier),
            )
            node.is_expanded = True

    # Orphan items
    orphan_nodes = await get_orphan_items(session, doc_id)

    # Handle ?item= deep link
    selected_item = None
    if selected_item_ident is not None:
        selected_item = await _resolve_selected_item(
            session,
            doc.id,
            selected_item_ident,
        )
        if selected_item is not None:
            await _expand_ancestor_path(
                session,
                doc,
                root_nodes,
                orphan_nodes,
                selected_item,
            )

    return root_nodes, orphan_nodes, selected_item


async def get_item_for_detail(
    session: AsyncSession,
    doc_id: uuid.UUID,
    item_identifier: uuid.UUID,
) -> CFItem | None:
    """Load a single item with joinedloads for the detail pane."""
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
        )
        .where(
            CFItem.cf_document_id == doc_id,
            CFItem.identifier == item_identifier,
        )
    )
    return result.scalars().unique().one_or_none()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_idents_with_children(
    session: AsyncSession,
    doc_id: uuid.UUID,
    idents: list[str],
) -> set[str]:
    """Return subset of idents that are a destination in isChildOf (= have children)."""
    if not idents:
        return set()
    result = await session.execute(
        select(CFAssociation.destination_node_identifier)
        .where(
            CFAssociation.cf_document_id == doc_id,
            CFAssociation.association_type == "isChildOf",
            CFAssociation.destination_node_identifier.in_(idents),
        )
        .distinct()
    )
    return {row[0] for row in result.all()}


async def sort_related_by_tree_order(session: AsyncSession, doc_id: uuid.UUID, groups: list[dict]) -> set[str]:
    """Sort each related group's items to match the tree's ordering and return
    the set of destination identifiers that are CFItems in this document.

    Same-document destinations are ordered by the same key the tree uses
    (`human_coding_scheme` natural sort, NULL last → title → identifier) and
    come first; cross-document / external destinations (no local item) fall
    back to title/identifier and sort after. Used so the pane's "Related" list
    reads in the same order as the tree, and to gate in-pane navigation
    (same-doc → navigate in tree; else link out).
    """
    dests = {a.destination_node_identifier for g in groups for a in g["items"]}
    uuids = _strs_to_uuids(list(dests))
    hcs_by_ident: dict[str, str | None] = {}
    if uuids:
        rows = (
            await session.execute(
                select(CFItem.identifier, CFItem.human_coding_scheme).where(
                    CFItem.cf_document_id == doc_id, CFItem.identifier.in_(uuids)
                )
            )
        ).all()
        hcs_by_ident = {str(i): h for i, h in rows}

    def _key(a) -> tuple:
        ident = a.destination_node_identifier
        in_doc = ident in hcs_by_ident
        hcs = hcs_by_ident.get(ident)
        return (
            (0,) if in_doc else (1,),  # same-doc items first
            (0, _natsort_key(hcs)) if hcs else (1, ()),  # hcs natsort, NULL last
            a.destination_node_title or "",
            ident,
        )

    for g in groups:
        g["items"].sort(key=_key)
    return set(hcs_by_ident.keys())


async def _resolve_selected_item(
    session: AsyncSession,
    doc_id: uuid.UUID,
    item_ident: uuid.UUID,
) -> CFItem | None:
    """Load selected item, returning None if not in this document."""
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
        )
        .where(
            CFItem.cf_document_id == doc_id,
            CFItem.identifier == item_ident,
        )
    )
    return result.scalars().unique().one_or_none()


async def _get_ancestor_path(
    session: AsyncSession,
    doc: CFDocument,
    item_ident: str,
) -> list[str]:
    """Walk isChildOf upward to build ancestor path (root-first order).

    Parent selection: min seq (NULL last) -> dest_ident ASC.
    """
    doc_ident = str(doc.identifier)
    path: list[str] = []
    current = item_ident
    visited = {current}

    for _ in range(100):  # safety limit
        result = await session.execute(
            select(CFAssociation).where(
                CFAssociation.cf_document_id == doc.id,
                CFAssociation.association_type == "isChildOf",
                CFAssociation.origin_node_identifier == current,
            )
        )
        assocs = list(result.scalars().all())
        if not assocs:
            break

        # Pick best parent
        assocs.sort(
            key=lambda a: (
                (0, a.sequence_number) if a.sequence_number is not None else (1, 0),
                a.destination_node_identifier,
            )
        )
        parent_ident = assocs[0].destination_node_identifier

        if parent_ident == doc_ident or parent_ident in visited:
            break
        visited.add(parent_ident)
        path.append(parent_ident)
        current = parent_ident

    path.reverse()
    return path


async def _expand_ancestor_path(
    session: AsyncSession,
    doc: CFDocument,
    root_nodes: list[TreeNode],
    orphan_nodes: list[TreeNode],
    selected_item: CFItem,
) -> None:
    """Expand tree nodes along the ancestor path to the selected item."""
    item_ident = str(selected_item.identifier)
    ancestors = await _get_ancestor_path(session, doc, item_ident)

    # All identifiers that need expansion (ancestors + selected item itself)
    expand_set = set(ancestors)
    expand_set.add(item_ident)

    async def _expand_nodes(nodes: list[TreeNode]) -> None:
        for node in nodes:
            nid = str(node.item.identifier)
            if nid in expand_set and node.has_children and not node.is_expanded:
                node.children = await get_children(
                    session,
                    doc.id,
                    nid,
                )
                node.is_expanded = True
            if node.children:
                await _expand_nodes(node.children)

    await _expand_nodes(root_nodes)
    await _expand_nodes(orphan_nodes)
