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
