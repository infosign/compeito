from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session
from src.dependencies import require_tenant, validate_uuid
from src.errors import ResourceNotFoundError, imsx_error_response
from src.models.tenant import Tenant
from src.services import case_query_params, case_query_service

router = APIRouter()

CACHE_CONTROL = "public, max-age=3600"


@router.get("/{tenant}/ims/case/v1p1/CFDocuments")
async def list_cf_documents(
    tenant_obj: Tenant = Depends(require_tenant),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
    sort: str | None = Query(default=None),
    orderBy: str | None = Query(default=None),  # noqa: N803 — CASE spec query param name
    filter: str | None = Query(default=None),  # noqa: A002 — CASE spec query param name (shadows builtin)
    fields: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if limit < 0:
        return imsx_error_response(
            400, "Invalid limit: must be a non-negative integer", "invalid_selection_field", field_name="limit"
        )
    if offset < 0:
        return imsx_error_response(
            400, "Invalid offset: must be a non-negative integer", "invalid_selection_field", field_name="offset"
        )

    # CASE v1.1 sort / orderBy / filter / fields (IMS / OneRoster-style).
    try:
        order_by = case_query_params.parse_sort(sort, orderBy)
        filter_clause = case_query_params.parse_filter(filter)
        field_list = case_query_params.parse_fields(fields)
    except case_query_params.QueryParamError as e:
        return imsx_error_response(400, e.message, e.code_minor, field_name=e.field_name)

    limit = min(limit, case_query_params.LIMIT_CAP)
    offset = min(offset, case_query_params.OFFSET_CAP)

    # X-Total-Count: total matching the (optional) filter, before pagination.
    total = await case_query_service.count_cf_documents(session, tenant_obj.id, filter_clause=filter_clause)

    docs = await case_query_service.list_cf_documents(
        session, tenant_obj.id, limit, offset, filter_clause=filter_clause, order_by=order_by
    )
    content = {
        "CFDocuments": [case_query_params.project_fields(doc.model_dump(by_alias=True), field_list) for doc in docs]
    }
    headers = {"Cache-Control": CACHE_CONTROL, "X-Total-Count": str(total)}

    # RFC 8288 Link header (next/prev/first/last). Tenant segment is always the
    # canonical UUID, matching emitted CASE URIs regardless of slug addressing.
    link = case_query_params.build_link_header(
        f"{settings.base_url}/{tenant_obj.id}/ims/case/v1p1/CFDocuments",
        limit,
        offset,
        total,
        extra_params={"sort": sort, "orderBy": orderBy, "filter": filter, "fields": fields},
    )
    if link is not None:
        headers["Link"] = link

    return JSONResponse(content=content, headers=headers)


@router.get("/{tenant}/ims/case/v1p1/CFDocuments/{id}")
async def get_cf_document(
    id: str,
    tenant_obj: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    doc_uuid = validate_uuid(id)
    doc = await case_query_service.get_cf_document(session, tenant_obj.id, doc_uuid)
    if doc is None:
        raise ResourceNotFoundError(f"CFDocument not found: '{id}'")
    content = {"CFDocument": doc.model_dump(by_alias=True)}
    return JSONResponse(content=content, headers={"Cache-Control": CACHE_CONTROL})
