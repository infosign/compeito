import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_item import CFItem


async def get_cf_item_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFItem | None:
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.cf_document),
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
        )
        .where(CFItem.tenant_id == tenant_id, CFItem.identifier == identifier)
    )
    return result.scalar_one_or_none()
