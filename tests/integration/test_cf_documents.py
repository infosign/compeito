import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.tenant import Tenant


TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"


class TestListCFDocuments:
    async def test_empty_list(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments")
        assert response.status_code == 200
        assert response.json() == {"CFDocuments": []}
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_returns_documents(
        self, db_client: AsyncClient, tenant: Tenant, sample_document: CFDocument,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments")
        assert response.status_code == 200
        body = response.json()
        docs = body["CFDocuments"]
        assert len(docs) == 1
        doc = docs[0]
        assert doc["identifier"] == DOC_IDENTIFIER
        assert doc["title"] == "Test Document"
        assert doc["creator"] == "Test Creator"
        assert doc["language"] == "ja"
        assert doc["lastChangeDateTime"] == "2025-10-08T12:00:00Z"
        # null fields included (exclude_none=False)
        assert "publisher" in doc
        assert doc["publisher"] is None
        assert "description" in doc
        assert doc["description"] is None
        # CFPackageURI present
        assert "CFPackageURI" in doc
        pkg_uri = doc["CFPackageURI"]
        assert pkg_uri["title"] == "Test Document"
        assert pkg_uri["identifier"] == DOC_IDENTIFIER
        assert "CFPackages" in pkg_uri["uri"]

    async def test_pagination_limit(
        self, db_client: AsyncClient, db_session: AsyncSession, tenant: Tenant,
    ) -> None:
        # Create 3 documents
        for i in range(3):
            doc = CFDocument(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=uuid.UUID(f"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbb{i:03d}"),
                uri=f"https://example.com/uri/doc-{i}",
                title=f"Doc {i}",
                last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            db_session.add(doc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFDocuments?limit=2")
        assert response.status_code == 200
        assert len(response.json()["CFDocuments"]) == 2

    async def test_pagination_offset(
        self, db_client: AsyncClient, db_session: AsyncSession, tenant: Tenant,
    ) -> None:
        for i in range(3):
            doc = CFDocument(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=uuid.UUID(f"cccccccc-cccc-cccc-cccc-ccccccccc{i:03d}"),
                uri=f"https://example.com/uri/doc-{i}",
                title=f"Doc {i}",
                last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            db_session.add(doc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFDocuments?offset=2")
        assert response.status_code == 200
        assert len(response.json()["CFDocuments"]) == 1

    async def test_pagination_limit_capped_at_500(
        self, db_client: AsyncClient, tenant: Tenant,
    ) -> None:
        # limit > 500 should not error, just be capped
        response = await db_client.get(f"{CASE_PATH}/CFDocuments?limit=999")
        assert response.status_code == 200

    async def test_pagination_limit_zero_returns_empty(
        self, db_client: AsyncClient, tenant: Tenant, sample_document: CFDocument,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments?limit=0")
        assert response.status_code == 200
        assert response.json() == {"CFDocuments": []}

    async def test_pagination_negative_limit_returns_400(
        self, db_client: AsyncClient, tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments?limit=-1")
        assert response.status_code == 400
        assert "invalid_selection_field" in str(response.json()["imsx_codeMinor"])

    async def test_pagination_negative_offset_returns_400(
        self, db_client: AsyncClient, tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments?offset=-1")
        assert response.status_code == 400
        assert "invalid_selection_field" in str(response.json()["imsx_codeMinor"])

    async def test_sorted_by_identifier(
        self, db_client: AsyncClient, db_session: AsyncSession, tenant: Tenant,
    ) -> None:
        ids = [
            "dddddddd-dddd-dddd-dddd-dddddddddd02",
            "dddddddd-dddd-dddd-dddd-dddddddddd00",
            "dddddddd-dddd-dddd-dddd-dddddddddd01",
        ]
        for id_str in ids:
            doc = CFDocument(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=uuid.UUID(id_str),
                uri=f"https://example.com/uri/{id_str}",
                title=f"Doc {id_str}",
                last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            db_session.add(doc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFDocuments")
        docs = response.json()["CFDocuments"]
        identifiers = [d["identifier"] for d in docs]
        assert identifiers == sorted(identifiers)


class TestGetCFDocument:
    async def test_get_existing_document(
        self, db_client: AsyncClient, tenant: Tenant, sample_document: CFDocument,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        assert "CFDocument" in body
        doc = body["CFDocument"]
        assert doc["identifier"] == DOC_IDENTIFIER
        assert doc["title"] == "Test Document"
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_get_nonexistent_document_returns_404(
        self, db_client: AsyncClient, tenant: Tenant,
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFDocuments/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_get_invalid_uuid_returns_400(
        self, db_client: AsyncClient, tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFDocuments/not-a-uuid")
        assert response.status_code == 400
        assert "invalid_uuid" in str(response.json()["imsx_codeMinor"])


class TestTenantIsolation:
    async def test_documents_not_visible_across_tenants(
        self, db_client: AsyncClient, db_session: AsyncSession,
        tenant: Tenant, sample_document: CFDocument,
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        # Other tenant doesn't exist, should get 404
        response = await db_client.get(
            f"/{other_tenant_id}/ims/case/v1p1/CFDocuments"
        )
        assert response.status_code == 404
