"""Web UI router — tenant list and framework list."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.services import tenant_service

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

CACHE_CONTROL = "public, max-age=3600"


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
