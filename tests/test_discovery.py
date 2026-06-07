"""Tests for the CASE v1.1 Service Discovery endpoint (FR-2.12)."""

from httpx import AsyncClient

DISCOVERY_PATH = "/ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json"


class TestDiscovery:
    async def test_returns_200(self, client: AsyncClient) -> None:
        response = await client.get(DISCOVERY_PATH)
        assert response.status_code == 200

    async def test_returns_json(self, client: AsyncClient) -> None:
        response = await client.get(DISCOVERY_PATH)
        assert response.headers["content-type"].startswith("application/json")

    async def test_returns_openapi_3_schema(self, client: AsyncClient) -> None:
        """Response body is the official 1EdTech CASE v1.1 OpenAPI 3 schema."""
        response = await client.get(DISCOVERY_PATH)
        body = response.json()
        assert body["openapi"].startswith("3.")
        assert body["info"]["version"] == "1.1"
        assert "Competencies and Academic Standards Exchange" in body["info"]["title"]

    async def test_cache_control_long_ttl(self, client: AsyncClient) -> None:
        """Schema is release-pinned; 1-day TTL keeps edge traffic low."""
        response = await client.get(DISCOVERY_PATH)
        assert response.headers["cache-control"] == "public, max-age=86400"

    async def test_v1p0_path_redirects_to_v1p1(self, client: AsyncClient) -> None:
        """The v1p0 → v1p1 middleware also covers the discovery path."""
        response = await client.get(
            "/ims/case/v1p0/discovery/imscasev1p1_openapi3_v1p0.json",
            follow_redirects=False,
        )
        assert response.status_code == 301
        assert response.headers["location"].endswith("/ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json")

    async def test_non_get_returns_405(self, client: AsyncClient) -> None:
        """Discovery sits under /ims/case/v1p1/, so the global 405 rule applies."""
        response = await client.post(DISCOVERY_PATH)
        assert response.status_code == 405
