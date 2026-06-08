from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.dependencies import require_tenant, validate_uuid
from src.errors import ResourceNotFoundError
from src.models.tenant import Tenant
from src.services import cf_view_service

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"

_TRUTHY = {"1", "true", "yes", "on"}


@router.get("/{tenant}/ims/case/v1p1/CFPackages/{id}")
async def get_cf_package(
    id: str,
    request: Request,
    tenant_obj: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    doc_uuid = validate_uuid(id)
    package = await cf_view_service.get_cf_package(session, tenant_obj.id, doc_uuid)
    if package is None:
        raise ResourceNotFoundError(f"CFPackage not found: '{id}'")
    # CASE v1.1: GET CFPackages/{id} returns a CFPackageDType — CFDocument,
    # CFItems, CFAssociations, CFDefinitions, CFRubrics at the top level. No
    # "CFPackage" wrapper (matches the spec and reference servers like OpenSALT).
    content = package.model_dump(by_alias=True)

    # Strict-conformance mode (?strict=1): the official package schema uses
    # additionalProperties:false and the package-context types (CFPckgDocument /
    # CFPckgItem) do NOT include CFPackageURI / CFDocumentURI. By default compeito
    # echoes them (OpenCASE / OpenSALT emit them too, which keeps the round-trip
    # lossless), but a strict validator would reject the extra keys — so strip
    # them when strict output is requested.
    if request.query_params.get("strict", "").lower() in _TRUTHY:
        content.get("CFDocument", {}).pop("CFPackageURI", None)
        for item in content.get("CFItems", []):
            item.pop("CFDocumentURI", None)

    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
