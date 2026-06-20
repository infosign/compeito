import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_association import CFAssociation


async def get_cf_association_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFAssociation | None:
    result = await session.execute(
        select(CFAssociation)
        .options(
            joinedload(CFAssociation.cf_document),
            joinedload(CFAssociation.association_grouping),
        )
        .where(CFAssociation.tenant_id == tenant_id, CFAssociation.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_outgoing_related(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    origin_identifier: str,
) -> list[CFAssociation]:
    """Outgoing non-isChildOf associations from an item, for the detail page.

    isChildOf is the tree hierarchy (shown in the tree view), so it is excluded
    here. The CFAssociationGrouping is eager-loaded so the detail page can group
    related links by it (e.g. Essential / Optional). Ordered by sequence number
    then destination title for a stable display.
    """
    result = await session.execute(
        select(CFAssociation)
        .options(joinedload(CFAssociation.association_grouping))
        .where(
            CFAssociation.tenant_id == tenant_id,
            CFAssociation.origin_node_identifier == origin_identifier,
            CFAssociation.association_type != "isChildOf",
        )
        .order_by(
            CFAssociation.sequence_number.nulls_last(),
            CFAssociation.destination_node_title,
        )
    )
    return list(result.scalars().unique().all())


async def list_ischildof_parents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
) -> list[CFAssociation]:
    """isChildOf where this item is the ORIGIN (child) → destinations are its
    parents. Tenant-wide (indexed on origin_node_identifier), so it surfaces
    cross-document parents that the in-document tree can't show."""
    result = await session.execute(
        select(CFAssociation)
        .where(
            CFAssociation.tenant_id == tenant_id,
            CFAssociation.origin_node_identifier == item_identifier,
            CFAssociation.association_type == "isChildOf",
        )
        .order_by(CFAssociation.sequence_number.nulls_last(), CFAssociation.destination_node_title)
    )
    return list(result.scalars().unique().all())


async def list_ischildof_children(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
) -> list[CFAssociation]:
    """isChildOf where this item is the DESTINATION (parent) → origins are its
    children. Tenant-wide (indexed on destination_node_identifier), so it
    surfaces cross-document children that the in-document tree can't show."""
    result = await session.execute(
        select(CFAssociation)
        .where(
            CFAssociation.tenant_id == tenant_id,
            CFAssociation.destination_node_identifier == item_identifier,
            CFAssociation.association_type == "isChildOf",
        )
        .order_by(CFAssociation.sequence_number.nulls_last(), CFAssociation.origin_node_title)
    )
    return list(result.scalars().unique().all())


async def list_incoming_by_destination_uri(
    session: AsyncSession,
    dest_uri: str,
) -> list[CFAssociation]:
    """Incoming references: associations (in ANY tenant) whose
    `destination_node_uri` equals `dest_uri` — i.e. someone points AT this item.

    This is the inverse of the outgoing cross-tenant resolution: given a CFItem's
    own node_uri (``{base_url}/{tenant}/uri/{item}``), it finds every association
    across all tenants that adopts/references it, so the item's detail pane can
    show "referenced by (other institutions)". isChildOf is excluded — pure tree
    hierarchy isn't an adoption/reference for this purpose, and cross-doc/-tenant
    isChildOf already surfaces in the 上位/下位 sections.

    Deliberately tenant-unscoped (no `tenant_id` filter): the whole point is to
    sweep other tenants. The CALLER must apply the private-tenant visibility gate
    (only origins in a public tenant are shown) — this repository returns the raw
    matches. The origin tenant_id / cf_document_id / node fields are on each row.

    PERFORMANCE: this filters on `destination_node_uri`, a free-text String column
    with NO index (existing indexes cover origin/destination *_node_identifier).
    Fine at demo / single-instance scale, but on a large multi-tenant corpus this
    becomes a sequential scan. If incoming refs grow hot, add an index on
    `cf_associations.destination_node_uri` (see docs/spec/db-schema.md). Kept
    index-free for now to avoid a migration for a feature with tiny cardinality.
    """
    result = await session.execute(
        select(CFAssociation)
        .where(
            CFAssociation.destination_node_uri == dest_uri,
            CFAssociation.association_type != "isChildOf",
        )
        .order_by(CFAssociation.origin_node_title, CFAssociation.identifier)
    )
    return list(result.scalars().unique().all())


async def list_associations_for_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
    limit: int | None = None,
    offset: int = 0,
) -> list[CFAssociation]:
    """Find all associations where the item is origin or destination (tenant-wide).

    `limit=None` (the default) returns the full set — the official CASE v1.1
    CFItemAssociations contract has no pagination, so truncation must only
    happen when a caller explicitly opts in.
    """
    query = (
        select(CFAssociation)
        .options(joinedload(CFAssociation.association_grouping))
        .where(
            CFAssociation.tenant_id == tenant_id,
            or_(
                CFAssociation.origin_node_identifier == item_identifier,
                CFAssociation.destination_node_identifier == item_identifier,
            ),
        )
        .order_by(CFAssociation.identifier)
        .offset(offset)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().unique().all())
