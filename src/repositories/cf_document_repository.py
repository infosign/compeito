import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_document import CFDocument


async def get_cf_document_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFDocument | None:
    result = await session.execute(
        select(CFDocument)
        .options(joinedload(CFDocument.license))
        .where(CFDocument.tenant_id == tenant_id, CFDocument.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_cf_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    *,
    filter_clause=None,
    order_by=None,
) -> list[CFDocument]:
    """List CFDocuments for a tenant.

    Optional ``filter_clause`` (a SQLAlchemy boolean expression) and
    ``order_by`` (a SQLAlchemy ordering) are applied BEFORE limit/offset so
    filtering and sorting are correct across pagination. ``order_by`` defaults
    to identifier ASC for deterministic output.
    """
    stmt = select(CFDocument).options(joinedload(CFDocument.license)).where(CFDocument.tenant_id == tenant_id)
    if filter_clause is not None:
        stmt = stmt.where(filter_clause)
    stmt = stmt.order_by(order_by if order_by is not None else CFDocument.identifier)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().unique().all())


async def count_cf_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    filter_clause=None,
) -> int:
    """Total CFDocuments for a tenant (after `filter_clause`, before pagination).

    Used for the `X-Total-Count` response header on GET /CFDocuments.
    """
    stmt = select(func.count()).select_from(CFDocument).where(CFDocument.tenant_id == tenant_id)
    if filter_clause is not None:
        stmt = stmt.where(filter_clause)
    return int((await session.execute(stmt)).scalar_one())
