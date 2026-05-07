import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_item_type import CFItemType


async def get_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFItemType | None:
    result = await session.execute(
        select(CFItemType).where(CFItemType.tenant_id == tenant_id, CFItemType.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFItemType]:
    result = await session.execute(
        select(CFItemType)
        .where(CFItemType.tenant_id == tenant_id)
        .order_by(CFItemType.identifier)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_descendants_by_hierarchy_code(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    hierarchy_code: str,
) -> list[CFItemType]:
    prefix = hierarchy_code + "."
    result = await session.execute(
        select(CFItemType)
        .where(
            CFItemType.tenant_id == tenant_id,
            CFItemType.hierarchy_code.like(prefix + "%"),
        )
        .order_by(CFItemType.hierarchy_code, CFItemType.identifier)
    )
    return list(result.scalars().all())
