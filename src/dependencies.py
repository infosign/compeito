"""Shared FastAPI dependencies."""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.errors import InvalidUUIDError, ResourceNotFoundError
from src.models.tenant import Tenant


def validate_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise InvalidUUIDError(f"Invalid UUID format: '{value}'")


async def require_tenant(
    tenant: str,
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    """FastAPI dependency that validates tenant UUID and existence."""
    tenant_uuid = validate_uuid(tenant)
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant_obj = result.scalar_one_or_none()
    if tenant_obj is None:
        raise ResourceNotFoundError(f"Tenant not found: '{tenant}'")
    return tenant_obj
