from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.errors import InvalidUUIDError, ResourceNotFoundError, imsx_error_response
from src.routers.case_api import router as case_api_router
from src.routers.web import router as web_router

# Marker identifying CASE API requests (kept in sync with the middleware below).
_CASE_API_MARKER = "/ims/case/v1p1/"

app = FastAPI(
    title="COMPEITO",
    description="1EdTech CASE v1.1 compatible web service",
)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(case_api_router)
app.include_router(web_router)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def redirect_v1p0(request: Request, call_next):
    if "/ims/case/v1p0/" in request.url.path:
        new_path = request.url.path.replace("/ims/case/v1p0/", "/ims/case/v1p1/")
        new_url = str(request.url).replace(request.url.path, new_path)
        return RedirectResponse(url=new_url, status_code=301)
    return await call_next(request)


@app.middleware("http")
async def method_not_allowed(request: Request, call_next):
    if _CASE_API_MARKER in request.url.path and request.method != "GET":
        response = imsx_error_response(405, "Method not allowed", "invalid_selection_field")
        response.headers["Allow"] = "GET"
        return response
    return await call_next(request)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return imsx_error_response(400, str(exc), "invalid_selection_field")


@app.exception_handler(InvalidUUIDError)
async def invalid_uuid_handler(request: Request, exc: InvalidUUIDError):
    return imsx_error_response(400, exc.message, "invalid_uuid")


@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    return imsx_error_response(404, exc.message, "unknownobject")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Undefined sub-paths under the CASE API get an imsx 404 (unknownobject);
    # everything else keeps FastAPI's default handling (e.g. the Web UI).
    if exc.status_code == 404 and _CASE_API_MARKER in request.url.path:
        return imsx_error_response(404, exc.detail or "Not found", "unknownobject")
    return await default_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse | PlainTextResponse:
    # Uncaught errors on the CASE API return an imsx 500; off the CASE API we
    # mirror Starlette's default plain 500. In both cases Starlette's
    # ServerErrorMiddleware re-raises the original exception afterwards, so the
    # traceback is still logged by the server.
    if _CASE_API_MARKER in request.url.path:
        return imsx_error_response(500, "Internal server error", "internal_server_error")
    return PlainTextResponse("Internal Server Error", status_code=500)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        content={"status": "ok"},
        headers={"Cache-Control": "no-store"},
    )
