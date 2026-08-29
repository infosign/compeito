"""Retirement (tombstone) rules for the Web UI.

CASE has no delete operation for an item that a source stopped publishing, and
compeito's import is additive only, so a retired item survives in the tenant as a
"tombstone" carrying ``statusEndDate`` (and usually a ``replacedBy`` association).
The CASE API keeps serving them; the Web UI hides them by default so nobody
aligns a badge or a teaching resource to an item that is no longer in use.

See docs/dev/designs/retired-item-ui.md (B8-3 / B8-4) for the full design.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.models.cf_association import CFAssociation
from src.models.cf_item import CFItem


def is_retired(item: CFItem, today: date) -> bool:
    """Whether the item is retired as of ``today``.

    A future ``statusEndDate`` means "scheduled for retirement" and is still in
    force — the framework revision protocol sets an end-of-year date ahead of
    time, and treating that as retired would make items vanish mid-year.
    """
    return item.status_end_date is not None and item.status_end_date <= today


async def hidden_identifiers(
    session: AsyncSession,
    doc_id: uuid.UUID,
    today: date,
) -> set[str]:
    """Identifiers hidden from the default tree view of this document.

    An item is hidden when it is retired AND no descendant of it is live —
    hiding a retired item that still leads to live items would cut the path to
    them.

    The result is a document-wide set, computed once per request and passed to
    every tree builder. That matters for ``_get_idents_with_children``, which
    asks about *grandchildren* of the level being rendered: a set scoped to the
    rendered level would not contain them.

    Cost: one query for the retired set, one for their children. A document with
    no tombstones stops after the first.

    **Invariant (the most fragile premise here): every retired item enters the
    frontier in step 1.** Pruning below (step 3) reduces the traversal, not the
    set of items being judged — a retired item under a live node is still judged,
    because it is a starting point in its own right. Narrowing step 1 to, say,
    "retired items reachable from the tree root" silently breaks has_children.
    """
    # 1. Every retired item in the document. Empty -> nothing to hide, and every
    #    caller's filter degrades to a no-op.
    retired_rows = await session.execute(
        select(CFItem.identifier).where(
            CFItem.cf_document_id == doc_id,
            CFItem.status_end_date.is_not(None),
            CFItem.status_end_date <= today,
        )
    )
    retired = {str(r[0]) for r in retired_rows.all()}
    if not retired:
        return set()

    # 2-3. Children of the retired items, in one query. Only a retired child can
    #      hide anything, so a live child is a leaf for our purposes and its
    #      descendants are never fetched (without that pruning, a single tombstone
    #      below the root would drag in every live item under it).
    #      Two joins do the work: the parent side restricts to retired parents,
    #      the child side proves the child's CFItem row exists — a dangling
    #      isChildOf points at nothing renderable, so counting it as a live child
    #      would keep a dead subtree on screen.
    #      The retired set goes in as a correlated subquery, not as bind
    #      parameters: a fully retired document would otherwise blow past
    #      asyncpg's 32767-parameter limit.
    retired_idents = select(cast(CFItem.identifier, Text)).where(
        CFItem.cf_document_id == doc_id,
        CFItem.status_end_date.is_not(None),
        CFItem.status_end_date <= today,
    )
    child_item = aliased(CFItem)
    rows = await session.execute(
        select(
            CFAssociation.destination_node_identifier,
            CFAssociation.origin_node_identifier,
        )
        .join(
            child_item,
            cast(child_item.identifier, Text) == CFAssociation.origin_node_identifier,
        )
        .where(
            CFAssociation.cf_document_id == doc_id,
            CFAssociation.association_type == "isChildOf",
            CFAssociation.destination_node_identifier.in_(retired_idents),
            child_item.cf_document_id == doc_id,
        )
    )
    children: dict[str, list[str]] = {}
    for parent, child in rows.all():
        kids = children.setdefault(parent, [])
        if child not in kids:
            kids.append(child)

    # 4-6. Fold bottom-up. memo holds settled answers; on_stack is the current
    #      DFS path, and only an edge back into it counts as a cycle (a plain
    #      shared descendant under two parents is NOT a cycle — treating it as one
    #      would leave a fully-retired diamond visible). A value decided by
    #      cutting a cycle is path-dependent, so it is never memoised. The taint
    #      is not propagated to ancestors: cutting always errs toward "visible",
    #      i.e. toward showing something that could have been hidden.
    memo: dict[str, bool] = {}
    on_stack: set[str] = set()

    def fold(ident: str) -> bool:
        if ident not in retired:
            return False  # live item: never hidden, and it stops the recursion
        if ident in memo:
            return memo[ident]
        if ident in on_stack:
            return False  # cycle: fall back to visible, do not memoise
        on_stack.add(ident)
        tainted = False
        hidden = True
        for child in children.get(ident, ()):
            if child in on_stack:
                tainted = True
                hidden = False
                break
            if not fold(child):
                hidden = False
                break
        on_stack.discard(ident)
        if not tainted:
            memo[ident] = hidden
        return hidden

    return {ident for ident in retired if fold(ident)}
