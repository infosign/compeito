"""Tenant and document query services for the Web UI."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.tenant import Tenant


async def list_public_tenants(session: AsyncSession) -> list[Tenant]:
    """Return public tenants sorted by name ASC, id ASC."""
    result = await session.execute(
        select(Tenant).where(Tenant.is_private.is_(False)).order_by(Tenant.name.asc(), Tenant.id.asc())
    )
    return list(result.scalars().all())


async def get_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    """Return a tenant by ID, or None."""
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def list_documents_with_item_count(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return documents with item counts for a tenant.

    Each dict has keys: doc (CFDocument), item_count (int).
    Sorted by title ASC, identifier ASC.
    """
    stmt = (
        select(
            CFDocument,
            func.count(CFItem.id).label("item_count"),
        )
        .outerjoin(CFItem, CFItem.cf_document_id == CFDocument.id)
        .where(CFDocument.tenant_id == tenant_id)
        .group_by(CFDocument.id)
        .order_by(CFDocument.title.asc(), CFDocument.identifier.asc())
    )
    result = await session.execute(stmt)
    return [{"doc": row[0], "item_count": row[1]} for row in result.all()]
