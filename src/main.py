from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from mangum import Mangum

from src.errors import InvalidUUIDError, ResourceNotFoundError, imsx_error_response
from src.routers.case_api import router as case_api_router

app = FastAPI(
    title="CASE Server",
    description="1EdTech CASE v1.1 compliant web service",
)


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(case_api_router)


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
    if "/ims/case/v1p1/" in request.url.path and request.method != "GET":
        response = imsx_error_response(
            405, "Method not allowed", "invalid_selection_field"
        )
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


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        content={"status": "ok"},
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Mangum handler (AWS Lambda)
# ---------------------------------------------------------------------------

handler = Mangum(app)
