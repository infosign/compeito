import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_license import CFLicense


async def get_by_identifier(
    session: AsyncSession, tenant_id: uuid.UUID, identifier: uuid.UUID,
) -> CFLicense | None:
    result = await session.execute(
        select(CFLicense)
        .where(CFLicense.tenant_id == tenant_id, CFLicense.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession, tenant_id: uuid.UUID, limit: int = 100, offset: int = 0,
) -> list[CFLicense]:
    result = await session.execute(
        select(CFLicense)
        .where(CFLicense.tenant_id == tenant_id)
        .order_by(CFLicense.identifier)
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())
