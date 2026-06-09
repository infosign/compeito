"""Web UI router — tenant list, framework list, tree view."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.i18n import get_translator, parse_accept_language
from src.repositories import cf_association_repository, cf_rubric_repository
from src.services import tenant_service, tree_service, uri_service

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Tailwind is built into a local stylesheet at image-build time (no external CDN
# in production). When that built file is absent — e.g. native local dev without
# a build step — base.html falls back to the Tailwind Play CDN so styling still
# works with zero setup. Evaluated once at startup.
_TAILWIND_CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
templates.env.globals["tailwind_local"] = _TAILWIND_CSS.is_file()

CACHE_CONTROL = "public, max-age=3600"
CACHE_CONTROL_FRAGMENT = "public, max-age=86400"

# Map UriResult.resource_type to the CASE v1.1 API path segment.
# Resource types without an individual API endpoint (CFRubricCriterion,
# CFRubricCriterionLevel — nested only inside CFRubrics) are absent.
_RESOURCE_TYPE_TO_API_PATH: dict[str, str] = {
    "CFDocument": "CFDocuments",
    "CFItem": "CFItems",
    "CFAssociation": "CFAssociations",
    "CFAssociationGrouping": "CFAssociationGroupings",
    "CFConcept": "CFConcepts",
    "CFItemType": "CFItemTypes",
    "CFLicense": "CFLicenses",
    "CFSubject": "CFSubjects",
    "CFRubric": "CFRubrics",
}


def _prefers_json(accept_header: str) -> bool:
    """Return True if the Accept header signals a JSON API consumer.

    Heuristic tuned for CASE clients (e.g., Open Badge Factory):
    - Accept contains application/json or application/ld+json AND does NOT
      include text/html → treat as JSON consumer.
    - Browsers (text/html present) and unspecified Accept fall through to HTML.
    """
    if not accept_header:
        return False
    accept = accept_header.lower()
    has_json = "application/json" in accept or "application/ld+json" in accept
    has_html = "text/html" in accept
    return has_json and not has_html


def _get_lang(request: Request) -> str:
    """Extract language from Accept-Language header."""
    return parse_accept_language(request.headers.get("accept-language", ""))


def _parse_uuid(value: str) -> uuid.UUID | None:
    """Parse a UUID string, returning None if invalid."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def _tenant_url_segment(request_segment: str, tenant_obj) -> str:
    """Return the URL segment form to use for nav links in the response.

    Preserves the form the user requested ("sticky" navigation): if they came
    in via UUID, every nav href in the rendered page stays UUID; if they came
    in via slug, every nav href stays slug. The URL bar form therefore does
    not drift mid-session. Display fields (permalink / API URL strings) ignore
    this and always emit the canonical UUID — see templates.
    """
    try:
        uuid.UUID(request_segment)
        return str(tenant_obj.id)
    except (ValueError, AttributeError):
        # Slug request — emit the canonical slug as stored (defensive fallback
        # to UUID if the tenant unexpectedly lacks a slug).
        return tenant_obj.slug or str(tenant_obj.id)


def _error_response(
    request: Request,
    status_code: int,
    message: str,
    detail: str = "",
) -> HTMLResponse:
    """Render an error page."""
    lang = _get_lang(request)
    t = get_translator(lang)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "message": message,
            "detail": detail,
            "t": t,
            "lang": lang,
        },
        status_code=status_code,
    )


def _error_fragment(status_code: int, message: str) -> HTMLResponse:
    """Return a plain HTML fragment for HTMX error responses."""
    return HTMLResponse(
        f'<p class="text-red-600 p-4">{message}</p>',
        status_code=status_code,
    )


async def _related_groups(session: AsyncSession, tenant_id, item_identifier) -> list[dict]:
    """Outgoing non-isChildOf associations grouped by CFAssociationGrouping
    (e.g. Essential / Optional). Ungrouped associations fall into a None bucket.
    Shared by the full detail page (`uri_detail`) and the tree detail fragment
    (`detail_fragment`) so both render the same grouped "Related" block.
    """
    assocs = await cf_association_repository.list_outgoing_related(session, tenant_id, str(item_identifier))
    buckets: dict[str | None, dict] = {}
    order: list[str | None] = []
    for a in assocs:
        g = a.association_grouping
        key = str(g.identifier) if g else None
        if key not in buckets:
            buckets[key] = {"title": (g.title if g else None), "items": []}
            order.append(key)
        buckets[key]["items"].append(a)
    return [buckets[k] for k in order]


async def _detail_extras(session: AsyncSession, tenant_id, resource_type: str, resource) -> dict:
    """Extra context the resource-detail card needs beyond the resource itself:
    rubrics (CFDocument), referring criteria + related groupings (CFItem).
    Shared by the standalone /uri/ page and the tree right-pane fragment so both
    render identical full detail.
    """
    rubrics: list = []
    referring_criteria: list = []
    related_groups: list[dict] = []
    if resource_type == "CFDocument":
        rubrics = await cf_rubric_repository.list_by_document(session, resource.id)
    elif resource_type == "CFItem":
        referring_criteria = await cf_rubric_repository.list_criteria_by_item(session, resource.id)
        related_groups = await _related_groups(session, tenant_id, resource.identifier)
    return {"rubrics": rubrics, "referring_criteria": referring_criteria, "related_groups": related_groups}


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Public tenant list."""
    lang = _get_lang(request)
    t = get_translator(lang)
    tenants = await tenant_service.list_public_tenants(session)
    response = templates.TemplateResponse(
        request,
        "index.html",
        {"tenants": tenants, "t": t, "lang": lang},
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
    lang = _get_lang(request)
    t = get_translator(lang)
    tenant_obj = await tenant_service.resolve_tenant(session, tenant)
    if tenant_obj is None:
        return _error_response(request, 404, t("error_not_found"))

    documents = await tenant_service.list_documents_with_item_count(
        session,
        tenant_obj.id,
    )
    response = templates.TemplateResponse(
        request,
        "tenant.html",
        {
            "tenant": tenant_obj,
            "documents": documents,
            "tenant_url": _tenant_url_segment(tenant, tenant_obj),
            "t": t,
            "lang": lang,
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


async def _render_tree_page(
    tenant: str,
    doc_id: str,
    request: Request,
    item: str | None,
    session: AsyncSession,
) -> HTMLResponse:
    """Render the full tree page, optionally with `item` selected (its full
    detail SSR'd into the right pane). Shared by the query-string route
    (`?item=`) and the path route (`/item/{id}`); the path form is what
    in-tree navigation pushes (static-bakeable — one object per item)."""
    lang = _get_lang(request)
    t = get_translator(lang)
    # Resolve tenant (UUID or slug)
    tenant_obj = await tenant_service.resolve_tenant(session, tenant)
    if tenant_obj is None:
        return _error_response(request, 404, t("error_not_found"))

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_response(
            request,
            400,
            t("error_bad_request"),
            t("error_invalid_uuid", value=doc_id),
        )
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_response(request, 404, t("error_not_found"))

    # Parse optional ?item= parameter (ignore if invalid)
    selected_ident = _parse_uuid(item) if item else None

    root_nodes, orphan_nodes, selected_item = await tree_service.build_full_tree(
        session,
        doc,
        selected_ident,
    )

    # Fetch rubrics for this document (shown in right pane default view)
    rubrics = await cf_rubric_repository.list_by_document(session, doc.id)

    # On deep-link (?item=), SSR the right pane with that item's full detail
    # (relationship-loaded), so the pane reconstructs without an HTMX round-trip.
    selected_detail = None
    referring_criteria: list = []
    related_groups: list[dict] = []
    if selected_item is not None:
        selected_detail = await tree_service.get_item_for_detail(session, doc.id, selected_item.identifier)
        if selected_detail is not None:
            extras = await _detail_extras(session, tenant_obj.id, "CFItem", selected_detail)
            referring_criteria = extras["referring_criteria"]
            related_groups = extras["related_groups"]

    response = templates.TemplateResponse(
        request,
        "cftree.html",
        {
            "tenant": tenant_obj,
            "doc": doc,
            "root_nodes": root_nodes,
            "orphan_nodes": orphan_nodes,
            "selected_item": selected_item,
            # Full-detail pane context (used by the shared partial when an item
            # is deep-linked). `resource` is the relationship-loaded item.
            "resource": selected_detail,
            "resource_type": "CFItem" if selected_detail is not None else None,
            "referring_criteria": referring_criteria,
            "related_groups": related_groups,
            # Rendered inside the tree → hide the redundant "Show in tree" link.
            "in_pane": True,
            # Sticky URL segment: preserves the form the user requested (UUID
            # or slug) so nav links don't drift the URL bar mid-session.
            # Permalink / API URL strings rendered in the page use `tenant.id`
            # directly (canonical UUID — stable across slug renames).
            "tenant_url": _tenant_url_segment(tenant, tenant_obj),
            "rubrics": rubrics,
            "t": t,
            "lang": lang,
        },
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
    """Tree view page. `?item=` selects an item (kept for back-compat)."""
    return await _render_tree_page(tenant, doc_id, request, item, session)


@router.get("/{tenant}/cftree/doc/{doc_id}/item/{item_id}", response_class=HTMLResponse)
async def tree_view_item(
    tenant: str,
    doc_id: str,
    item_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Tree view with an item selected via the URL path. This is the canonical,
    shareable, static-bakeable form that in-tree navigation pushes; opening /
    reloading / sharing it reconstructs the tree (expanded to the item) + the
    item's full detail in the pane via SSR."""
    return await _render_tree_page(tenant, doc_id, request, item_id, session)


@router.get("/{tenant}/uri/{resource_id}", response_class=HTMLResponse)
async def uri_detail(
    tenant: str,
    resource_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Resource detail page (/uri/{uuid}).

    Content negotiation:
    - Browsers (Accept includes text/html) → HTML detail page.
    - JSON API consumers (e.g., Open Badge Factory) → 303 See Other to the
      matching CASE v1.1 API endpoint. Resource types without an individual
      API endpoint (CFRubricCriterion / CFRubricCriterionLevel) fall through
      to HTML.
    """
    lang = _get_lang(request)
    t = get_translator(lang)
    # Resolve tenant (UUID or slug)
    tenant_obj = await tenant_service.resolve_tenant(session, tenant)
    if tenant_obj is None:
        return _error_response(request, 404, t("error_not_found"))

    # Validate resource UUID
    res_uuid = _parse_uuid(resource_id)
    if res_uuid is None:
        return _error_response(
            request,
            400,
            t("error_bad_request"),
            t("error_invalid_uuid", value=resource_id),
        )

    result = await uri_service.find_resource_by_identifier(
        session,
        tenant_obj.id,
        res_uuid,
    )
    if result is None:
        return _error_response(request, 404, t("error_not_found"))

    # Content negotiation: redirect JSON consumers to the CASE API endpoint.
    if _prefers_json(request.headers.get("accept", "")):
        api_path = _RESOURCE_TYPE_TO_API_PATH.get(result.resource_type)
        if api_path is not None:
            redirect_url = f"/{tenant}/ims/case/v1p1/{api_path}/{res_uuid}"
            return RedirectResponse(url=redirect_url, status_code=303)

    extras = await _detail_extras(session, tenant_obj.id, result.resource_type, result.resource)

    # Build page title per spec
    if result.resource_type == "CFItem":
        stmt = result.resource.full_statement
        page_title = stmt[:50] if len(stmt) > 50 else stmt
    elif result.resource_type == "CFDocument":
        page_title = result.resource.title
    elif result.resource_type == "CFRubricCriterion":
        page_title = result.resource.category or str(result.resource.identifier)
    elif result.resource_type == "CFRubricCriterionLevel":
        page_title = result.resource.quality or str(result.resource.identifier)
    else:
        page_title = getattr(result.resource, "title", None) or str(result.resource.identifier)

    response = templates.TemplateResponse(
        request,
        "uri.html",
        {
            "tenant": tenant_obj,
            "resource_type": result.resource_type,
            "resource": result.resource,
            "doc": result.doc,
            "page_title": page_title,
            "rubrics": extras["rubrics"],
            "referring_criteria": extras["referring_criteria"],
            "related_groups": extras["related_groups"],
            # Standalone page (not the tree pane): show the "Show in tree" link.
            "in_pane": False,
            "tenant_url": _tenant_url_segment(tenant, tenant_obj),
            "t": t,
            "lang": lang,
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
    lang = _get_lang(request)
    t = get_translator(lang)
    # Resolve tenant (UUID or slug)
    tenant_obj = await tenant_service.resolve_tenant(session, tenant)
    if tenant_obj is None:
        return _error_fragment(404, t("error_tenant_not_found"))

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_fragment(400, t("error_bad_request"))
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_fragment(404, t("error_document_not_found"))

    # Validate item UUID format
    item_uuid = _parse_uuid(item_id)
    if item_uuid is None:
        return HTMLResponse("", status_code=400)

    # Get children (empty if item doesn't exist or belongs to another doc)
    nodes = await tree_service.get_children(session, doc.id, str(item_uuid))
    response = templates.TemplateResponse(
        request,
        "fragments/children.html",
        {
            "nodes": nodes,
            # Sticky URL segment: matches the form the user requested so nav
            # links don't drift the URL bar mid-session.
            "tenant_url": _tenant_url_segment(tenant, tenant_obj),
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
    lang = _get_lang(request)
    t = get_translator(lang)
    # Resolve tenant (UUID or slug)
    tenant_obj = await tenant_service.resolve_tenant(session, tenant)
    if tenant_obj is None:
        return _error_fragment(404, t("error_tenant_not_found"))

    # Validate document
    doc_uuid = _parse_uuid(doc_id)
    if doc_uuid is None:
        return _error_fragment(400, t("error_bad_request"))
    doc = await tree_service.get_document_for_tree(session, tenant_obj.id, doc_uuid)
    if doc is None:
        return _error_fragment(404, t("error_document_not_found"))

    # Validate item
    item_uuid = _parse_uuid(item_id)
    if item_uuid is None:
        return HTMLResponse("", status_code=400)

    selected_item = await tree_service.get_item_for_detail(session, doc.id, item_uuid)
    if selected_item is None:
        return _error_fragment(404, t("error_item_not_found"))

    # The pane renders the SAME full-detail card as the standalone /uri/ page
    # (shared partial), so the right pane is the complete view — no round-trip
    # to /uri/ needed just to see all fields.
    extras = await _detail_extras(session, tenant_obj.id, "CFItem", selected_item)

    response = templates.TemplateResponse(
        request,
        "fragments/detail.html",
        {
            "resource": selected_item,
            "resource_type": "CFItem",
            "doc": doc,
            "tenant": tenant_obj,
            "rubrics": extras["rubrics"],
            "referring_criteria": extras["referring_criteria"],
            "related_groups": extras["related_groups"],
            # Rendered inside the tree → hide the redundant "Show in tree" link.
            "in_pane": True,
            # Sticky URL segment: matches the form the user requested so nav
            # links don't drift the URL bar mid-session.
            "tenant_url": _tenant_url_segment(tenant, tenant_obj),
            "t": t,
            "lang": lang,
        },
    )
    response.headers["Cache-Control"] = CACHE_CONTROL_FRAGMENT
    return response
