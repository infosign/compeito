"""Error-envelope completeness for the CASE API (conformance backlog C14 / C15).

- Undefined sub-paths under /{tenant}/ims/case/v1p1/ return an imsx 404.
- Uncaught errors on the CASE API return an imsx 500.
- Non-CASE paths keep FastAPI/Starlette's default error handling.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.main import app
from src.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


class TestCaseApi404Envelope:
    async def test_undefined_case_subpath_returns_imsx_404(self, client: AsyncClient) -> None:
        # No route matches "Bogus" → Starlette 404 → converted to imsx (C14).
        resp = await client.get(f"/{uuid.uuid4()}/ims/case/v1p1/Bogus")
        assert resp.status_code == 404
        body = resp.json()
        assert body["imsx_codeMajor"] == "failure"
        assert body["imsx_severity"] == "error"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_non_case_404_keeps_default(self, client: AsyncClient) -> None:
        # A missing static file 404s off the CASE API → default shape, not imsx.
        resp = await client.get("/static/does-not-exist.xyz")
        assert resp.status_code == 404
        assert "imsx_codeMajor" not in resp.json()

    async def test_non_case_405_keeps_default(self, client: AsyncClient) -> None:
        # 405 off the CASE API is delegated to the default handler unchanged.
        resp = await client.post("/health")
        assert resp.status_code == 405
        assert "imsx_codeMajor" not in resp.json()


class TestCaseApi500Envelope:
    async def test_500_on_case_api_returns_imsx(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.services import case_query_service

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        # Force an uncaught error after tenant resolution succeeds.
        monkeypatch.setattr(case_query_service, "count_cf_documents", boom)

        async def _override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = _override_get_session
        # raise_app_exceptions=False so the handled 500 response is observable
        # (ServerErrorMiddleware re-raises the original for logging otherwise).
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 500
        body = resp.json()
        assert body["imsx_codeMajor"] == "failure"
        assert body["imsx_severity"] == "error"
        assert "internal_server_error" in str(body["imsx_codeMinor"])
