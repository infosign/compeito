"""Tenant and document query services for the Web UI."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_rubric import CFRubric
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


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    """Return a tenant by slug, or None."""
    result = await session.execute(select(Tenant).where(Tenant.slug == slug))
    return result.scalar_one_or_none()


async def resolve_tenant(session: AsyncSession, identifier: str) -> Tenant | None:
    """Resolve a URL segment to a Tenant.

    Accepts either a UUID string or a slug. UUID lookup is tried first to keep
    O(1) PK access fast and to preserve the canonical-identifier semantics
    (CASE clients always see UUID-based URIs). Slug lookup is the fallback for
    Web-UI-friendly URLs.
    """
    try:
        tenant_uuid = uuid.UUID(identifier)
    except (ValueError, AttributeError):
        return await get_tenant_by_slug(session, identifier)
    return await get_tenant(session, tenant_uuid)


async def list_documents_with_item_count(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return documents with item and rubric counts for a tenant.

    Each dict has keys: doc (CFDocument), item_count (int), rubric_count (int).
    Sorted by title ASC, identifier ASC.
    """
    item_count_sub = (
        select(
            CFItem.cf_document_id,
            func.count(CFItem.id).label("item_count"),
        )
        .group_by(CFItem.cf_document_id)
        .subquery()
    )
    rubric_count_sub = (
        select(
            CFRubric.cf_document_id,
            func.count(CFRubric.id).label("rubric_count"),
        )
        .group_by(CFRubric.cf_document_id)
        .subquery()
    )
    stmt = (
        select(
            CFDocument,
            func.coalesce(item_count_sub.c.item_count, 0).label("item_count"),
            func.coalesce(rubric_count_sub.c.rubric_count, 0).label("rubric_count"),
        )
        .outerjoin(item_count_sub, item_count_sub.c.cf_document_id == CFDocument.id)
        .outerjoin(rubric_count_sub, rubric_count_sub.c.cf_document_id == CFDocument.id)
        .where(CFDocument.tenant_id == tenant_id)
        .order_by(CFDocument.title.asc(), CFDocument.identifier.asc())
    )
    result = await session.execute(stmt)
    return [{"doc": row[0], "item_count": row[1], "rubric_count": row[2]} for row in result.all()]
