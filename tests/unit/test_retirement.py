"""Tests for the retirement (tombstone) rules — B8-3 / B8-4.

See docs/dev/designs/retired-item-ui.md. The fold in `hidden_identifiers` is the
delicate part: it has to hide a fully-retired subtree while keeping any retired
item that still leads to a live one, over a graph that legitimately has
multi-parent items (and, in broken data, cycles).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.tenant import Tenant
from src.services import retirement

TODAY = date(2026, 8, 29)


def _item(
    tenant: Tenant,
    doc: CFDocument,
    label: str,
    *,
    end: date | None = None,
) -> CFItem:
    ident = uuid.uuid4()
    return CFItem(
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=ident,
        uri=f"https://example.com/uri/{ident}",
        full_statement=label,
        status_end_date=end,
        depth=0,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _child_of(doc: CFDocument, child, parent) -> CFAssociation:
    child_ident = child if isinstance(child, str) else str(child.identifier)
    parent_ident = parent if isinstance(parent, str) else str(parent.identifier)
    return CFAssociation(
        tenant_id=doc.tenant_id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri=f"https://example.com/assoc/{uuid.uuid4()}",
        association_type="isChildOf",
        origin_node_uri=f"https://example.com/uri/{child_ident}",
        origin_node_identifier=child_ident,
        destination_node_uri=f"https://example.com/uri/{parent_ident}",
        destination_node_identifier=parent_ident,
        last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


class TestIsRetired:
    def test_past_date_is_retired(self, tenant: Tenant, sample_document: CFDocument):
        assert retirement.is_retired(_item(tenant, sample_document, "x", end=date(2026, 8, 28)), TODAY)

    def test_today_is_retired(self, tenant: Tenant, sample_document: CFDocument):
        """statusEndDate is "the day retirement took effect", so it counts from that day."""
        assert retirement.is_retired(_item(tenant, sample_document, "x", end=TODAY), TODAY)

    def test_future_date_is_still_live(self, tenant: Tenant, sample_document: CFDocument):
        """A revision protocol sets an end-of-year date ahead of time; the item
        must not vanish mid-year."""
        assert not retirement.is_retired(_item(tenant, sample_document, "x", end=date(2026, 8, 30)), TODAY)

    def test_no_date_is_live(self, tenant: Tenant, sample_document: CFDocument):
        assert not retirement.is_retired(_item(tenant, sample_document, "x"), TODAY)


class TestHiddenIdentifiers:
    async def test_no_tombstones_returns_empty(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        db_session.add(_item(tenant, sample_document, "live"))
        await db_session.flush()

        assert await retirement.hidden_identifiers(db_session, sample_document.id, TODAY) == set()

    async def test_retired_leaf_is_hidden(self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
        dead = _item(tenant, sample_document, "dead", end=date(2022, 3, 14))
        db_session.add(dead)
        db_session.add(_child_of(sample_document, dead, sample_document))
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(dead.identifier)}

    async def test_future_dated_leaf_is_not_hidden(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        scheduled = _item(tenant, sample_document, "scheduled", end=date(2027, 3, 31))
        db_session.add(scheduled)
        await db_session.flush()

        assert await retirement.hidden_identifiers(db_session, sample_document.id, TODAY) == set()

    async def test_retired_parent_with_live_child_stays_visible(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """Hiding it would cut the only path to the live child."""
        parent = _item(tenant, sample_document, "retired parent", end=date(2022, 3, 14))
        live = _item(tenant, sample_document, "live child")
        db_session.add_all([parent, live])
        db_session.add(_child_of(sample_document, live, parent))
        await db_session.flush()

        assert await retirement.hidden_identifiers(db_session, sample_document.id, TODAY) == set()

    async def test_fully_retired_subtree_is_hidden_whole(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        root = _item(tenant, sample_document, "root", end=date(2022, 3, 14))
        mid = _item(tenant, sample_document, "mid", end=date(2022, 3, 14))
        leaf = _item(tenant, sample_document, "leaf", end=date(2022, 3, 14))
        db_session.add_all([root, mid, leaf])
        db_session.add_all([_child_of(sample_document, mid, root), _child_of(sample_document, leaf, mid)])
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(root.identifier), str(mid.identifier), str(leaf.identifier)}

    async def test_fully_retired_diamond_is_hidden_whole(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """Multi-parent items are normal CASE structure, not a cycle.

        X -> A -> C and X -> B -> C: reaching C twice must not be mistaken for a
        cycle, or B (and then X) would be judged visible and a fully retired
        subtree would stay on screen.
        """
        end = date(2022, 3, 14)
        x = _item(tenant, sample_document, "X", end=end)
        a = _item(tenant, sample_document, "A", end=end)
        b = _item(tenant, sample_document, "B", end=end)
        c = _item(tenant, sample_document, "C", end=end)
        db_session.add_all([x, a, b, c])
        db_session.add_all(
            [
                _child_of(sample_document, a, x),
                _child_of(sample_document, b, x),
                _child_of(sample_document, c, a),
                _child_of(sample_document, c, b),
            ]
        )
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(i.identifier) for i in (x, a, b, c)}

    async def test_diamond_with_one_live_leaf_keeps_every_ancestor(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        end = date(2022, 3, 14)
        x = _item(tenant, sample_document, "X", end=end)
        a = _item(tenant, sample_document, "A", end=end)
        b = _item(tenant, sample_document, "B", end=end)
        c = _item(tenant, sample_document, "C")  # live
        db_session.add_all([x, a, b, c])
        db_session.add_all(
            [
                _child_of(sample_document, a, x),
                _child_of(sample_document, b, x),
                _child_of(sample_document, c, a),
                _child_of(sample_document, c, b),
            ]
        )
        await db_session.flush()

        assert await retirement.hidden_identifiers(db_session, sample_document.id, TODAY) == set()

    async def test_cycle_falls_back_to_visible(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """Broken data must not hang or hide arbitrarily; erring toward visible."""
        end = date(2022, 3, 14)
        a = _item(tenant, sample_document, "A", end=end)
        b = _item(tenant, sample_document, "B", end=end)
        db_session.add_all([a, b])
        db_session.add_all([_child_of(sample_document, b, a), _child_of(sample_document, a, b)])
        await db_session.flush()

        assert await retirement.hidden_identifiers(db_session, sample_document.id, TODAY) == set()

    async def test_retired_item_under_a_live_node_is_still_judged(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """The invariant that makes has_children work.

        Pruning stops the *traversal* at a live node, not the *judgement*: the
        retired grandchild is a starting point in its own right.
        """
        live = _item(tenant, sample_document, "live")
        dead = _item(tenant, sample_document, "dead grandchild", end=date(2022, 3, 14))
        db_session.add_all([live, dead])
        db_session.add_all([_child_of(sample_document, live, sample_document), _child_of(sample_document, dead, live)])
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(dead.identifier)}

    async def test_child_without_a_cfitem_row_does_not_keep_the_parent(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """A dangling isChildOf points at nothing renderable, so it must not
        count as a live child."""
        dead = _item(tenant, sample_document, "dead", end=date(2022, 3, 14))
        db_session.add(dead)
        db_session.add(_child_of(sample_document, str(uuid.uuid4()), dead))
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(dead.identifier)}

    async def test_other_documents_are_not_consulted(
        self, db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument
    ):
        """A live child in ANOTHER document does not keep a tombstone visible
        here: this tree is document-scoped (the cross-document child shows up in
        the detail pane's "lower (other framework)" section instead)."""
        other = CFDocument(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/uri/other",
            title="Other",
            creator="t",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(other)
        await db_session.flush()

        dead = _item(tenant, sample_document, "dead", end=date(2022, 3, 14))
        elsewhere = _item(tenant, other, "live elsewhere")
        db_session.add_all([dead, elsewhere])
        db_session.add(_child_of(sample_document, elsewhere, dead))
        await db_session.flush()

        hidden = await retirement.hidden_identifiers(db_session, sample_document.id, TODAY)
        assert hidden == {str(dead.identifier)}
