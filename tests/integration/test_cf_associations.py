import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_document import CFDocument
from src.models.tenant import Tenant

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ASSOC_IDENTIFIER = "cccccccc-cccc-cccc-cccc-cccccccccccc"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"


@pytest.fixture
async def sample_association(
    db_session: AsyncSession,
    sample_document: CFDocument,
) -> CFAssociation:
    """Create a sample CFAssociation for testing."""
    assoc = CFAssociation(
        id=uuid.uuid4(),
        tenant_id=sample_document.tenant_id,
        cf_document_id=sample_document.id,
        identifier=uuid.UUID(ASSOC_IDENTIFIER),
        uri=f"https://example.com/uri/{ASSOC_IDENTIFIER}",
        association_type="isChildOf",
        origin_node_identifier="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        origin_node_uri="https://example.com/uri/origin",
        origin_node_title="Origin Item",
        origin_node_target_type=None,
        destination_node_identifier=str(sample_document.identifier),
        destination_node_uri=sample_document.uri,
        destination_node_title=sample_document.title,
        destination_node_target_type=None,
        sequence_number=10,
        last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(assoc)
    await db_session.flush()
    return assoc


class TestGetCFAssociation:
    async def test_get_existing_association(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_association: CFAssociation,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFAssociations/{ASSOC_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        assert "CFAssociation" in body
        assoc = body["CFAssociation"]
        assert assoc["identifier"] == ASSOC_IDENTIFIER
        assert assoc["associationType"] == "isChildOf"
        assert assoc["sequenceNumber"] == 10
        assert assoc["lastChangeDateTime"] == "2025-10-08T12:00:00Z"
        # originNodeURI is LinkGenURIDType (with targetType)
        origin = assoc["originNodeURI"]
        assert origin["title"] == "Origin Item"
        assert origin["identifier"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        assert "targetType" in origin
        assert origin["targetType"] is None
        # destinationNodeURI
        dest = assoc["destinationNodeURI"]
        assert dest["title"] == "Test Document"
        assert dest["identifier"] == DOC_IDENTIFIER
        assert "targetType" in dest
        # CFDocumentURI present (standalone schema)
        assert "CFDocumentURI" in assoc
        doc_uri = assoc["CFDocumentURI"]
        assert doc_uri["title"] == "Test Document"
        assert doc_uri["identifier"] == DOC_IDENTIFIER
        # Cache-Control
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_get_nonexistent_association_returns_404(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFAssociations/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_get_invalid_uuid_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFAssociations/not-a-uuid")
        assert response.status_code == 400
        assert "invalid_uuid" in str(response.json()["imsx_codeMinor"])

    async def test_ext_association_type(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """ext: prefixed associationType values should be returned correctly."""
        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            uri="https://example.com/uri/ext-assoc",
            association_type="ext:customRelation",
            origin_node_identifier="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            origin_node_uri="https://example.com/uri/ext-origin",
            origin_node_title="Ext Origin",
            destination_node_identifier="ffffffff-ffff-ffff-ffff-ffffffffffff",
            destination_node_uri="https://example.com/uri/ext-dest",
            destination_node_title="Ext Destination",
            last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFAssociations/dddddddd-dddd-dddd-dddd-dddddddddddd")
        assert response.status_code == 200
        assert response.json()["CFAssociation"]["associationType"] == "ext:customRelation"

    async def test_with_association_grouping(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """CFAssociationGroupingURI should be populated when grouping exists."""
        grouping = CFAssociationGrouping(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("99999999-9999-9999-9999-999999999999"),
            uri="https://example.com/uri/grouping",
            title="Cross-Subject Relations",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(grouping)
        await db_session.flush()

        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("88888888-8888-8888-8888-888888888888"),
            uri="https://example.com/uri/grouped-assoc",
            association_type="isRelatedTo",
            origin_node_identifier="aaaa1111-1111-1111-1111-111111111111",
            origin_node_uri="https://example.com/uri/origin-g",
            origin_node_title="Origin G",
            destination_node_identifier="aaaa2222-2222-2222-2222-222222222222",
            destination_node_uri="https://example.com/uri/dest-g",
            destination_node_title="Dest G",
            cf_association_grouping_id=grouping.id,
            last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(assoc)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFAssociations/88888888-8888-8888-8888-888888888888")
        assert response.status_code == 200
        grouping_uri = response.json()["CFAssociation"]["CFAssociationGroupingURI"]
        assert grouping_uri is not None
        assert grouping_uri["title"] == "Cross-Subject Relations"
        assert grouping_uri["identifier"] == "99999999-9999-9999-9999-999999999999"

    async def test_null_fields_included(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_association: CFAssociation,
    ) -> None:
        """Null fields should be present in response (exclude_none=False)."""
        response = await db_client.get(f"{CASE_PATH}/CFAssociations/{ASSOC_IDENTIFIER}")
        assoc = response.json()["CFAssociation"]
        assert "CFAssociationGroupingURI" in assoc
        assert assoc["CFAssociationGroupingURI"] is None


class TestTenantIsolation:
    async def test_association_not_visible_across_tenants(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_association: CFAssociation,
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        response = await db_client.get(f"/{other_tenant_id}/ims/case/v1p1/CFAssociations/{ASSOC_IDENTIFIER}")
        assert response.status_code == 404
