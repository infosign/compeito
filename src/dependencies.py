"""Shared FastAPI dependencies."""

import uuid

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.errors import InvalidUUIDError, ResourceNotFoundError
from src.models.tenant import Tenant
from src.services.case_serializer import OutputMode, resolve_output_mode
from src.services.tenant_service import resolve_tenant


def output_mode(
    strict: str | None = Query(default=None),
    compat: str | None = Query(default=None),
) -> OutputMode:
    """Resolve the CASE output mode for this request (see case_serializer)."""
    return resolve_output_mode(strict, compat)


def validate_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise InvalidUUIDError(f"Invalid UUID format: '{value}'")


async def require_tenant(
    tenant: str,
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    """FastAPI dependency that resolves a tenant URL segment to a Tenant row.

    The URL segment may be either the tenant's UUID (canonical) or its slug
    (Web-UI alias). The UUID stays the primary identifier — CASE API responses
    keep emitting UUID-based URIs regardless of how the tenant was addressed
    in the request URL.
    """
    tenant_obj = await resolve_tenant(session, tenant)
    if tenant_obj is None:
        raise ResourceNotFoundError(f"Tenant not found: '{tenant}'")
    return tenant_obj
