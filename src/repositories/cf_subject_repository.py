import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_subject import CFSubject


async def get_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFSubject | None:
    result = await session.execute(
        select(CFSubject).where(CFSubject.tenant_id == tenant_id, CFSubject.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFSubject]:
    result = await session.execute(
        select(CFSubject)
        .where(CFSubject.tenant_id == tenant_id)
        .order_by(CFSubject.identifier)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_descendants_by_hierarchy_code(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    hierarchy_code: str,
) -> list[CFSubject]:
    prefix = hierarchy_code + "."
    result = await session.execute(
        select(CFSubject)
        .where(
            CFSubject.tenant_id == tenant_id,
            CFSubject.hierarchy_code.like(prefix + "%"),
        )
        .order_by(CFSubject.hierarchy_code, CFSubject.identifier)
    )
    return list(result.scalars().all())
