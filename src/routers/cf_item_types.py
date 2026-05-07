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


@router.get("/{tenant}/ims/case/v1p1/CFItemTypes")
async def list_cf_item_types(
    tenant_obj: Tenant = Depends(require_tenant),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if limit < 0:
        return imsx_error_response(400, "Invalid limit: must be a non-negative integer", "invalid_selection_field")
    if offset < 0:
        return imsx_error_response(400, "Invalid offset: must be a non-negative integer", "invalid_selection_field")
    limit = min(limit, 500)
    offset = min(offset, 100000)
    items = await case_query_service.list_cf_item_types(session, tenant_obj.id, limit, offset)
    content = {"CFItemTypes": [i.model_dump(by_alias=True) for i in items]}
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})


@router.get("/{tenant}/ims/case/v1p1/CFItemTypes/{id}")
async def get_cf_item_type(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    obj_uuid = validate_uuid(id)
    objs = await case_query_service.get_cf_item_type_set(session, tenant_obj.id, obj_uuid)
    if objs is None:
        raise ResourceNotFoundError(f"CFItemType not found: '{id}'")
    # CFItemTypeSetDType: requested item type first, descendants by hierarchyCode follow
    content = {"CFItemTypes": [o.model_dump(by_alias=True) for o in objs]}
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
