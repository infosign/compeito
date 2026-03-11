import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association_grouping import CFAssociationGrouping


async def get_by_identifier(
    session: AsyncSession, tenant_id: uuid.UUID, identifier: uuid.UUID,
) -> CFAssociationGrouping | None:
    result = await session.execute(
        select(CFAssociationGrouping)
        .where(CFAssociationGrouping.tenant_id == tenant_id, CFAssociationGrouping.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession, tenant_id: uuid.UUID, limit: int = 100, offset: int = 0,
) -> list[CFAssociationGrouping]:
    result = await session.execute(
        select(CFAssociationGrouping)
        .where(CFAssociationGrouping.tenant_id == tenant_id)
        .order_by(CFAssociationGrouping.identifier)
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())
