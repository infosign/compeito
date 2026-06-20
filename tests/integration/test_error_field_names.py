"""imsx_codeMinorFieldName carries the offending parameter name (backlog C11).

For sort / orderBy / filter / fields / limit / offset errors the field name is
meaningful instead of the default "sourcedId".
"""

import pytest
from httpx import AsyncClient

from src.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


def _field_name(body: dict) -> str:
    return body["imsx_codeMinor"]["imsx_codeMinorField"][0]["imsx_codeMinorFieldName"]


class TestErrorFieldNames:
    async def test_negative_limit_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?limit=-1")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "limit"

    async def test_negative_offset_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?offset=-1")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "offset"

    async def test_invalid_sort_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?sort=bogus")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "sort"

    async def test_invalid_order_by_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?sort=title&orderBy=bogus")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "orderBy"

    async def test_invalid_filter_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?filter=bogus%3Dx")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "filter"

    async def test_invalid_fields_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments?fields=bogus")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "fields"

    async def test_missing_required_param_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        # CFRubrics requires `doc`; the RequestValidationError surfaces "doc".
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFRubrics")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "doc"

    async def test_uuid_error_keeps_default_field_name(self, db_client: AsyncClient, tenant: Tenant) -> None:
        # A bad path UUID keeps the imsx default "sourcedId".
        resp = await db_client.get(f"/{tenant.id}/ims/case/v1p1/CFDocuments/not-a-uuid")
        assert resp.status_code == 400
        assert _field_name(resp.json()) == "sourcedId"
