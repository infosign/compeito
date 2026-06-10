from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.dependencies import require_tenant, validate_uuid
from src.errors import ResourceNotFoundError, imsx_error_response
from src.models.tenant import Tenant
from src.services import case_query_service

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"


@router.get("/{tenant}/ims/case/v1p1/CFItems/{id}")
async def get_cf_item(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    item_uuid = validate_uuid(id)
    item = await case_query_service.get_cf_item(session, tenant_obj.id, item_uuid)
    if item is None:
        raise ResourceNotFoundError(f"CFItem not found: '{id}'")
    content = {"CFItem": item.model_dump(by_alias=True)}
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})


@router.get("/{tenant}/ims/case/v1p1/CFItemAssociations/{id}")
async def get_cf_item_associations(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    limit: int | None = Query(default=None),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """All associations where the item is origin or destination (tenant-wide).

    The official CASE v1.1 contract defines NO pagination on this endpoint —
    a conformant client expects the FULL association set. `limit` / `offset`
    are a compeito extension and apply only when explicitly given; the default
    (no params) returns everything. (A previous default of limit=100 silently
    truncated large sets.)
    """
    item_uuid = validate_uuid(id)
    item = await case_query_service.get_cf_item(session, tenant_obj.id, item_uuid)
    if item is None:
        raise ResourceNotFoundError(f"CFItem not found: '{id}'")

    if limit is not None and limit < 0:
        return imsx_error_response(400, "Invalid limit: must be a non-negative integer", "invalid_selection_field")
    if offset < 0:
        return imsx_error_response(400, "Invalid offset: must be a non-negative integer", "invalid_selection_field")

    assocs = await case_query_service.list_item_associations(session, tenant_obj.id, str(item_uuid), limit, offset)
    content = {
        "CFItem": item.model_dump(by_alias=True),
        "CFAssociations": [a.model_dump(by_alias=True) for a in assocs],
    }
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
