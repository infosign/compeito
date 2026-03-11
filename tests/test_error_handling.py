import uuid

import pytest
from httpx import AsyncClient


CASE_PATH = "/ims/case/v1p1"
VALID_UUID = str(uuid.uuid4())
INVALID_UUID = "not-a-uuid"


class TestTenantValidation:
    """Test tenant UUID validation and existence checks."""

    async def test_invalid_tenant_uuid_returns_400(self, client: AsyncClient) -> None:
        response = await client.get(f"/{INVALID_UUID}{CASE_PATH}/CFDocuments")
        assert response.status_code == 400
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert body["imsx_severity"] == "error"
        assert "invalid_uuid" in str(body["imsx_codeMinor"])
        assert INVALID_UUID in body["imsx_description"]

    async def test_nonexistent_tenant_returns_404(self, client: AsyncClient) -> None:
        response = await client.get(f"/{VALID_UUID}{CASE_PATH}/CFDocuments")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert body["imsx_severity"] == "error"
        assert "unknownobject" in str(body["imsx_codeMinor"])
        assert VALID_UUID in body["imsx_description"]


class TestMethodNotAllowed:
    """Test that non-GET methods on CASE API return 405."""

    @pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
    async def test_non_get_returns_405(self, client: AsyncClient, method: str) -> None:
        url = f"/{VALID_UUID}{CASE_PATH}/CFDocuments"
        response = await getattr(client, method)(url)
        assert response.status_code == 405
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert body["imsx_severity"] == "error"
        assert "invalid_selection_field" in str(body["imsx_codeMinor"])
        assert response.headers["allow"] == "GET"


class TestV1p0Redirect:
    """Test v1p0 -> v1p1 redirect."""

    async def test_v1p0_redirects_to_v1p1(self, client: AsyncClient) -> None:
        response = await client.get(
            f"/{VALID_UUID}/ims/case/v1p0/CFDocuments",
            follow_redirects=False,
        )
        assert response.status_code == 301
        location = response.headers["location"]
        assert "/ims/case/v1p1/CFDocuments" in location
        assert "/ims/case/v1p0/" not in location

    async def test_v1p0_preserves_query_params(self, client: AsyncClient) -> None:
        response = await client.get(
            f"/{VALID_UUID}/ims/case/v1p0/CFDocuments?limit=10&offset=5",
            follow_redirects=False,
        )
        assert response.status_code == 301
        location = response.headers["location"]
        assert "limit=10" in location
        assert "offset=5" in location
