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
    limit: int = Query(default=100),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    item_uuid = validate_uuid(id)
    item = await case_query_service.get_cf_item(session, tenant_obj.id, item_uuid)
    if item is None:
        raise ResourceNotFoundError(f"CFItem not found: '{id}'")

    if limit < 0:
        return imsx_error_response(400, "Invalid limit: must be a non-negative integer", "invalid_selection_field")
    if offset < 0:
        return imsx_error_response(400, "Invalid offset: must be a non-negative integer", "invalid_selection_field")

    limit = min(limit, 500)
    offset = min(offset, 100000)

    assocs = await case_query_service.list_item_associations(
        session, tenant_obj.id, str(item_uuid), limit, offset
    )
    content = {
        "CFItem": item.model_dump(by_alias=True),
        "CFAssociations": [a.model_dump(by_alias=True) for a in assocs],
    }
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
