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


async def list_associations_for_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
    limit: int = 100,
    offset: int = 0,
) -> list[CFAssociation]:
    """Find all associations where the item is origin or destination (tenant-wide)."""
    result = await session.execute(
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
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().unique().all())
