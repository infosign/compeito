"""Web UI router — tenant list, framework list, tree view."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.services import tenant_service
from src.services import tree_service
from src.services import uri_service

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

CACHE_CONTROL = "public, max-age=3600"
CACHE_CONTROL_FRAGMENT = "public, max-age=86400"


def _parse_uuid(value: str) -> uuid.UUID | None:
    """Parse a UUID string, returning None if invalid."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def _error_response(
    request: Request, status_code: int, message: str, detail: str = "",
) -> HTMLResponse:
    """Render an error page."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "message": message,
            "detail": detail,
        },
        status_code=status_code,
    )


def _error_fragment(status_code: int, message: str) -> HTMLResponse:
    """Return a plain HTML fragment for HTMX error responses."""
    return HTMLResponse(
        f'<p class="text-red-600 p-4">{message}</p>',
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Public tenant list."""
    tenants = await tenant_service.list_public_tenants(session)
    response = templates.TemplateResponse(
        request, "index.html", {"tenants": tenants},
    )
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


@router.get("/{tenant}/", response_class=HTMLResponse)
async def tenant_page(
    tenant: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Framework list for a tenant."""
    tenant_uuid = _parse_uuid(tenant)
    if tenant_uuid is None:
        return _error_response(
            request, 400, "リクエストが不正です",
            f"Invalid UUID format: '{tenant}'",
        )

    tenant_obj = await tenant_service.get_tenant(session, tenant_uuid)
    if tenant_obj is None:
        return _error_response(request, 404, "ページが見つかりません")

    documents = await tenant_service.list_documents_with_item_count(
        session, tenant_obj.id,
    )
    response = templates.TemplateResponse(
        request, "tenant.html",
        {"tenant": tenant_obj, "documents": documents},
    )
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


@router.get("/{tenant}/cftree/doc/{doc_id}", response_class=HTMLResponse)
async def tree_view(
    tenant: str,
    doc_id: str,
    request: Request,
    item: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Tree view page (SSR depth 0-1 + HTMX lazy load)."""
    # Validate tenant
    tenant_uuid = _parse_uuid(tenant)
    if tenant_uuid is None:
        return _error_response(
            request, 400, "リクエストが不正です",
            f"Invalid UUID format: '{tenant}'",
        )
    tenant_obj = await tenant_service.get_tenant(session, tenant_uuid)
    if tenant_obj is None:
        return _error_response(request, 404, "ページが見つかりません")

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_response(
            request, 400, "リクエストが不正です",
            f"Invalid UUID format: '{doc_id}'",
        )
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_response(request, 404, "ページが見つかりません")

    # Parse optional ?item= parameter (ignore if invalid)
    selected_ident = _parse_uuid(item) if item else None

    root_nodes, orphan_nodes, selected_item = await tree_service.build_ssr_tree(
        session, doc, selected_ident,
    )

    response = templates.TemplateResponse(
        request, "cftree.html",
        {
            "tenant": tenant_obj,
            "doc": doc,
            "root_nodes": root_nodes,
            "orphan_nodes": orphan_nodes,
            "selected_item": selected_item,
            "tenant_id": str(tenant_obj.id),
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


@router.get("/{tenant}/uri/{resource_id}", response_class=HTMLResponse)
async def uri_detail(
    tenant: str,
    resource_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Resource detail page (/uri/{uuid})."""
    # Validate tenant
    tenant_uuid = _parse_uuid(tenant)
    if tenant_uuid is None:
        return _error_response(
            request, 400, "リクエストが不正です",
            f"Invalid UUID format: '{tenant}'",
        )
    tenant_obj = await tenant_service.get_tenant(session, tenant_uuid)
    if tenant_obj is None:
        return _error_response(request, 404, "ページが見つかりません")

    # Validate resource UUID
    res_uuid = _parse_uuid(resource_id)
    if res_uuid is None:
        return _error_response(
            request, 400, "リクエストが不正です",
            f"Invalid UUID format: '{resource_id}'",
        )

    result = await uri_service.find_resource_by_identifier(
        session, tenant_obj.id, res_uuid,
    )
    if result is None:
        return _error_response(request, 404, "ページが見つかりません")

    # Build page title per spec
    if result.resource_type == "CFItem":
        stmt = result.resource.full_statement
        page_title = stmt[:50] if len(stmt) > 50 else stmt
    elif result.resource_type == "CFDocument":
        page_title = result.resource.title
    else:
        page_title = getattr(result.resource, "title", None) or str(result.resource.identifier)

    response = templates.TemplateResponse(
        request, "uri.html",
        {
            "tenant": tenant_obj,
            "resource_type": result.resource_type,
            "resource": result.resource,
            "doc": result.doc,
            "page_title": page_title,
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


# ---------------------------------------------------------------------------
# HTMX fragment routes
# ---------------------------------------------------------------------------

@router.get(
    "/{tenant}/cftree/doc/{doc_id}/children/{item_id}",
    response_class=HTMLResponse,
)
async def children_fragment(
    tenant: str,
    doc_id: str,
    item_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """HTMX fragment: child items of {item_id}."""
    # Validate tenant
    tenant_uuid = _parse_uuid(tenant)
    if tenant_uuid is None:
        return _error_fragment(400, "リクエストが不正です")
    tenant_obj = await tenant_service.get_tenant(session, tenant_uuid)
    if tenant_obj is None:
        return _error_fragment(404, "テナントが見つかりません")

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_fragment(400, "リクエストが不正です")
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_fragment(404, "ドキュメントが見つかりません")

    # Validate item UUID format
    item_uuid = _parse_uuid(item_id)
    if item_uuid is None:
        return HTMLResponse("", status_code=400)

    # Get children (empty if item doesn't exist or belongs to another doc)
    nodes = await tree_service.get_children(session, doc.id, str(item_uuid))
    response = templates.TemplateResponse(
        request, "fragments/children.html",
        {
            "nodes": nodes,
            "tenant_id": str(tenant_obj.id),
            "doc_identifier": str(doc.identifier),
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL_FRAGMENT
    return response


@router.get(
    "/{tenant}/cftree/doc/{doc_id}/detail/{item_id}",
    response_class=HTMLResponse,
)
async def detail_fragment(
    tenant: str,
    doc_id: str,
    item_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """HTMX fragment: item detail for the right pane."""
    # Validate tenant
    tenant_uuid = _parse_uuid(tenant)
    if tenant_uuid is None:
        return _error_fragment(400, "リクエストが不正です")
    tenant_obj = await tenant_service.get_tenant(session, tenant_uuid)
    if tenant_obj is None:
        return _error_fragment(404, "テナントが見つかりません")

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_fragment(400, "リクエストが不正です")
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_fragment(404, "ドキュメントが見つかりません")

    # Validate item
    item_uuid = _parse_uuid(item_id)
    if item_uuid is None:
        return HTMLResponse("", status_code=400)

    selected_item = await tree_service.get_item_for_detail(session, doc.id, item_uuid)
    if selected_item is None:
        return _error_fragment(404, "アイテムが見つかりません")

    response = templates.TemplateResponse(
        request, "fragments/detail.html",
        {
            "selected_item": selected_item,
            "tenant_id": str(tenant_obj.id),
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL_FRAGMENT
    return response
