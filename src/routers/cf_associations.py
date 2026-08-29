from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.dependencies import output_mode, require_tenant, validate_uuid
from src.errors import ResourceNotFoundError
from src.models.tenant import Tenant
from src.services import case_query_service
from src.services.case_serializer import OutputMode, dump_single

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"


@router.get("/{tenant}/ims/case/v1p1/CFAssociations/{id}")
async def get_cf_association(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    mode: OutputMode = Depends(output_mode),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    assoc_uuid = validate_uuid(id)
    assoc = await case_query_service.get_cf_association(session, tenant_obj.id, assoc_uuid)
    if assoc is None:
        raise ResourceNotFoundError(f"CFAssociation not found: '{id}'")
    content = dump_single(assoc, mode, compat_wrapper="CFAssociation")
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
