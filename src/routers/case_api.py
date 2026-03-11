"""CASE v1.1 API router stub.

Provides tenant-scoped routing with UUID validation. Individual resource
endpoints (CFDocuments, CFItems, etc.) will be added in subsequent issues.
"""

from fastapi import APIRouter, Depends

from src.dependencies import require_tenant
from src.models.tenant import Tenant

router = APIRouter(
    prefix="/{tenant}/ims/case/v1p1",
)


@router.get("/CFDocuments")
async def list_cf_documents(
    tenant_obj: Tenant = Depends(require_tenant),
) -> dict:
    # Stub — will be implemented in Issue #27
    return {"CFDocuments": []}
