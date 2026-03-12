import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.tenant import Tenant

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ITEM_IDENTIFIER = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"


@pytest.fixture
async def sample_item(db_session: AsyncSession, sample_document: CFDocument) -> CFItem:
    """Create a sample CFItem for testing."""
    item = CFItem(
        id=uuid.uuid4(),
        tenant_id=sample_document.tenant_id,
        cf_document_id=sample_document.id,
        identifier=uuid.UUID(ITEM_IDENTIFIER),
        uri=f"https://example.com/uri/{ITEM_IDENTIFIER}",
        full_statement="Test Item Statement",
        human_coding_scheme="1.1",
        language="ja",
        last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.fixture
async def sample_associations(
    db_session: AsyncSession,
    sample_document: CFDocument,
    sample_item: CFItem,
) -> list[CFAssociation]:
    """Create sample CFAssociations for testing."""
    assocs = []
    for i in range(3):
        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=sample_document.tenant_id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID(f"cccccccc-cccc-cccc-cccc-ccccccccc{i:03d}"),
            uri=f"https://example.com/uri/assoc-{i}",
            association_type="isChildOf",
            origin_node_identifier=str(sample_item.identifier),
            origin_node_uri=sample_item.uri,
            origin_node_title="Test Item Statement",
            destination_node_identifier=str(sample_document.identifier),
            destination_node_uri=sample_document.uri,
            destination_node_title=sample_document.title,
            last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        assocs.append(assoc)
    await db_session.flush()
    return assocs


class TestGetCFItem:
    async def test_get_existing_item(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItems/{ITEM_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        assert "CFItem" in body
        item = body["CFItem"]
        assert item["identifier"] == ITEM_IDENTIFIER
        assert item["fullStatement"] == "Test Item Statement"
        assert item["humanCodingScheme"] == "1.1"
        assert item["language"] == "ja"
        assert item["lastChangeDateTime"] == "2025-10-08T12:00:00Z"
        # CFDocumentURI present (standalone schema)
        assert "CFDocumentURI" in item
        doc_uri = item["CFDocumentURI"]
        assert doc_uri["title"] == "Test Document"
        assert doc_uri["identifier"] == DOC_IDENTIFIER
        # null fields included
        assert "abbreviatedStatement" in item
        assert item["abbreviatedStatement"] is None
        # Cache-Control header
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_get_nonexistent_item_returns_404(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFItems/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_get_invalid_uuid_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItems/not-a-uuid")
        assert response.status_code == 400
        assert "invalid_uuid" in str(response.json()["imsx_codeMinor"])


class TestGetCFItemAssociations:
    async def test_returns_item_and_associations(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
        sample_associations: list[CFAssociation],
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        # CFItem present
        assert "CFItem" in body
        assert body["CFItem"]["identifier"] == ITEM_IDENTIFIER
        assert body["CFItem"]["fullStatement"] == "Test Item Statement"
        # CFDocumentURI in CFItem (standalone schema)
        assert "CFDocumentURI" in body["CFItem"]
        # CFAssociations present
        assert "CFAssociations" in body
        assert len(body["CFAssociations"]) == 3
        # CFAssociations use CFPckgAssociationDType (no CFDocumentURI)
        for assoc in body["CFAssociations"]:
            assert "CFDocumentURI" not in assoc
            assert "associationType" in assoc
            assert "originNodeURI" in assoc
            assert "destinationNodeURI" in assoc
        # Cache-Control header
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_returns_empty_associations_array(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
    ) -> None:
        """Item exists but has no associations → empty array, not 404."""
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        assert body["CFItem"]["identifier"] == ITEM_IDENTIFIER
        assert body["CFAssociations"] == []

    async def test_nonexistent_item_returns_404(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        """Item does not exist → 404, not empty array (FR-3.6)."""
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_invalid_uuid_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/not-a-uuid")
        assert response.status_code == 400
        assert "invalid_uuid" in str(response.json()["imsx_codeMinor"])

    async def test_pagination_limit(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
        sample_associations: list[CFAssociation],
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}?limit=2")
        assert response.status_code == 200
        assert len(response.json()["CFAssociations"]) == 2

    async def test_pagination_offset(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
        sample_associations: list[CFAssociation],
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}?offset=2")
        assert response.status_code == 200
        assert len(response.json()["CFAssociations"]) == 1

    async def test_pagination_limit_zero_returns_empty(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
        sample_associations: list[CFAssociation],
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}?limit=0")
        assert response.status_code == 200
        assert response.json()["CFAssociations"] == []

    async def test_pagination_negative_limit_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}?limit=-1")
        assert response.status_code == 400
        assert "invalid_selection_field" in str(response.json()["imsx_codeMinor"])

    async def test_pagination_negative_offset_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item: CFItem,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}?offset=-1")
        assert response.status_code == 400
        assert "invalid_selection_field" in str(response.json()["imsx_codeMinor"])

    async def test_finds_associations_by_destination(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
        sample_item: CFItem,
    ) -> None:
        """Association where item is the destination node should also be found."""
        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            uri="https://example.com/uri/assoc-dest",
            association_type="isRelatedTo",
            origin_node_identifier=str(sample_document.identifier),
            origin_node_uri=sample_document.uri,
            origin_node_title=sample_document.title,
            destination_node_identifier=str(sample_item.identifier),
            destination_node_uri=sample_item.uri,
            destination_node_title="Test Item Statement",
            last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}")
        assert response.status_code == 200
        assert len(response.json()["CFAssociations"]) == 1

    async def test_searches_across_documents(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
        sample_item: CFItem,
    ) -> None:
        """Associations from other documents should also be found (tenant-wide search)."""
        other_doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            uri="https://example.com/uri/other-doc",
            title="Other Document",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(other_doc)
        await db_session.flush()

        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=other_doc.id,
            identifier=uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            uri="https://example.com/uri/cross-doc-assoc",
            association_type="isRelatedTo",
            origin_node_identifier=str(sample_item.identifier),
            origin_node_uri=sample_item.uri,
            origin_node_title="Test Item Statement",
            destination_node_identifier="99999999-9999-9999-9999-999999999999",
            destination_node_uri="https://example.com/uri/external",
            destination_node_title="External Item",
            last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_IDENTIFIER}")
        assert response.status_code == 200
        assert len(response.json()["CFAssociations"]) == 1


class TestTenantIsolation:
    async def test_item_not_visible_across_tenants(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_item: CFItem,
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        response = await db_client.get(f"/{other_tenant_id}/ims/case/v1p1/CFItems/{ITEM_IDENTIFIER}")
        assert response.status_code == 404

    async def test_item_associations_not_visible_across_tenants(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_item: CFItem,
        sample_associations: list[CFAssociation],
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        response = await db_client.get(f"/{other_tenant_id}/ims/case/v1p1/CFItemAssociations/{ITEM_IDENTIFIER}")
        assert response.status_code == 404
