from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.dependencies import require_tenant, validate_uuid
from src.errors import ResourceNotFoundError
from src.models.tenant import Tenant
from src.services import case_query_service

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"


@router.get("/{tenant}/ims/case/v1p1/CFRubrics/{id}")
async def get_cf_rubric(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    obj_uuid = validate_uuid(id)
    obj = await case_query_service.get_cf_rubric(session, tenant_obj.id, obj_uuid)
    if obj is None:
        raise ResourceNotFoundError(f"CFRubric not found: '{id}'")
    content = {"CFRubric": obj.model_dump(by_alias=True)}
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
