import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_concept import CFConcept


async def get_by_identifier(
    session: AsyncSession, tenant_id: uuid.UUID, identifier: uuid.UUID,
) -> CFConcept | None:
    result = await session.execute(
        select(CFConcept)
        .where(CFConcept.tenant_id == tenant_id, CFConcept.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession, tenant_id: uuid.UUID, limit: int = 100, offset: int = 0,
) -> list[CFConcept]:
    result = await session.execute(
        select(CFConcept)
        .where(CFConcept.tenant_id == tenant_id)
        .order_by(CFConcept.identifier)
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())
