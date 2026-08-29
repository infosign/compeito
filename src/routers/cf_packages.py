from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.dependencies import output_mode, require_tenant, validate_uuid
from src.errors import ResourceNotFoundError
from src.models.tenant import Tenant
from src.services import cf_view_service
from src.services.case_serializer import OutputMode, dump_package

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"


@router.get("/{tenant}/ims/case/v1p1/CFPackages/{id}")
async def get_cf_package(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    mode: OutputMode = Depends(output_mode),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    doc_uuid = validate_uuid(id)
    package = await cf_view_service.get_cf_package(session, tenant_obj.id, doc_uuid)
    if package is None:
        raise ResourceNotFoundError(f"CFPackage not found: '{id}'")
    # CASE v1.1: GET CFPackages/{id} returns a CFPackageDType — CFDocument,
    # CFItems, CFAssociations, CFDefinitions, CFRubrics at the top level. No
    # "CFPackage" wrapper (matches the spec and reference servers like OpenSALT).
    # Strict mode additionally drops nulls and the package-context URIs; see
    # src/services/case_serializer.py.
    content = dump_package(package, mode)

    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
