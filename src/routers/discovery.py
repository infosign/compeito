"""CASE v1.1 Service Discovery endpoint (FR-2.12).

Serves the official 1EdTech OpenAPI 3 schema as static JSON at the endpoint the
CASE v1.1 REST/JSON Binding prescribes. Because the document is served as
published rather than localized, CASE clients (and the 1EdTech conformance
tester) cannot yet discover compeito's own API URLs from it — see C18 in
docs/dev/case-v1p1-conformance-backlog.md.

The schema file is shipped at `docs/reference/imscasev1p1_openapi3_v1p0.json`,
an unmodified copy of the official 1EdTech OpenAPI definition (see
`THIRD_PARTY_NOTICES.md`). We resolve the
path from `__file__` so it works under the Docker deployment (`COPY . .`
includes docs/) and editable installs (`pip install -e .`). A future PyPI
distribution would need package-data inclusion, which is out of scope here.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "reference" / "imscasev1p1_openapi3_v1p0.json"
# Loaded once at module import — ~163 KB, release-pinned, never mutated.
_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

# Schema is stable per release; long TTL is safe and reduces edge traffic.
CACHE_CONTROL = "public, max-age=86400"


@router.get("/ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json")
async def discovery() -> JSONResponse:
    return JSONResponse(content=_SCHEMA, headers={"Cache-Control": CACHE_CONTROL})
