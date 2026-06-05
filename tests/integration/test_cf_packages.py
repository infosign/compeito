import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_concept import CFConcept
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


class TestGetCFPackageBasic:
    async def test_empty_package(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """Document with no items/associations → empty arrays, no CFDefinitions."""
        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        # CASE v1.1: CFPackageDType returned at top level (no "CFPackage" wrapper)
        pkg = body
        assert "CFPackage" not in pkg
        # CFDocument present (CFPckgDocumentDType — no CFPackageURI)
        assert "CFDocument" in pkg
        assert pkg["CFDocument"]["identifier"] == DOC_IDENTIFIER
        assert pkg["CFDocument"]["title"] == "Test Document"
        assert "CFPackageURI" not in pkg["CFDocument"]
        # CFItems and CFAssociations always present as empty arrays
        assert pkg["CFItems"] == []
        assert pkg["CFAssociations"] == []
        # CFDefinitions absent when no definitions
        assert "CFDefinitions" not in pkg
        # Cache-Control
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_nonexistent_package_returns_404(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFPackages/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"
        assert "unknownobject" in str(body["imsx_codeMinor"])

    async def test_invalid_uuid_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFPackages/not-a-uuid")
        assert response.status_code == 400
        assert "invalid_uuid" in str(response.json()["imsx_codeMinor"])


class TestGetCFPackageFull:
    """Test CFPackage with items, associations, and definitions."""

    @pytest.fixture
    async def full_package_data(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> dict:
        """Create a full set of package data."""
        # License
        lic = CFLicense(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/license",
            title="CC BY 4.0",
            last_change_date_time=LCT,
        )
        db_session.add(lic)

        # ItemType
        item_type = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("22222222-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/item-type",
            title="Knowledge",
            last_change_date_time=LCT,
        )
        db_session.add(item_type)

        # Concept
        concept = CFConcept(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/concept",
            title="Language",
            keywords="words|expression",
            last_change_date_time=LCT,
        )
        db_session.add(concept)

        # Subject
        subject = CFSubject(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("44444444-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/subject",
            title="Japanese",
            last_change_date_time=LCT,
        )
        db_session.add(subject)

        # AssociationGrouping
        grouping = CFAssociationGrouping(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/grouping",
            title="Cross-Subject",
            last_change_date_time=LCT,
        )
        db_session.add(grouping)
        await db_session.flush()

        # Item referencing item_type, concept, license; with subject_uri
        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            cf_item_type_id=item_type.id,
            cf_license_id=lic.id,
            cf_concept_id=concept.id,
            identifier=uuid.UUID("66666666-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/item",
            full_statement="Test Statement",
            subject_uri=[
                {
                    "title": "Japanese",
                    "identifier": "44444444-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "uri": "https://example.com/uri/subject",
                }
            ],
            last_change_date_time=LCT,
        )
        db_session.add(item)

        # Association referencing grouping
        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("77777777-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/assoc",
            association_type="isChildOf",
            origin_node_identifier=str(item.identifier),
            origin_node_uri=item.uri,
            origin_node_title="Test Statement",
            destination_node_identifier=str(sample_document.identifier),
            destination_node_uri=sample_document.uri,
            destination_node_title=sample_document.title,
            cf_association_grouping_id=grouping.id,
            last_change_date_time=LCT,
        )
        db_session.add(assoc)
        await db_session.flush()

        return {
            "license": lic,
            "item_type": item_type,
            "concept": concept,
            "subject": subject,
            "grouping": grouping,
            "item": item,
            "assoc": assoc,
        }

    async def test_full_package(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
        full_package_data: dict,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        assert response.status_code == 200
        pkg = response.json()

        # CFDocument — no CFPackageURI
        doc = pkg["CFDocument"]
        assert doc["identifier"] == DOC_IDENTIFIER
        assert "CFPackageURI" not in doc

        # CFItems — CFPckgItemDType (no CFDocumentURI)
        assert len(pkg["CFItems"]) == 1
        item = pkg["CFItems"][0]
        assert item["identifier"] == "66666666-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert item["fullStatement"] == "Test Statement"
        assert "CFDocumentURI" not in item
        assert item["CFItemType"] == "Knowledge"
        assert item["CFItemTypeURI"]["title"] == "Knowledge"

        # CFAssociations — CFPckgAssociationDType (no CFDocumentURI)
        assert len(pkg["CFAssociations"]) == 1
        assoc = pkg["CFAssociations"][0]
        assert assoc["identifier"] == "77777777-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert "CFDocumentURI" not in assoc
        assert assoc["CFAssociationGroupingURI"]["title"] == "Cross-Subject"

        # CFDefinitions
        assert "CFDefinitions" in pkg
        defs = pkg["CFDefinitions"]
        assert len(defs["CFItemTypes"]) == 1
        assert defs["CFItemTypes"][0]["title"] == "Knowledge"
        assert len(defs["CFConcepts"]) == 1
        assert defs["CFConcepts"][0]["title"] == "Language"
        assert defs["CFConcepts"][0]["keywords"] == "words|expression"
        assert len(defs["CFLicenses"]) == 1
        assert defs["CFLicenses"][0]["title"] == "CC BY 4.0"
        assert len(defs["CFSubjects"]) == 1
        assert defs["CFSubjects"][0]["title"] == "Japanese"
        assert len(defs["CFAssociationGroupings"]) == 1
        assert defs["CFAssociationGroupings"][0]["title"] == "Cross-Subject"

    async def test_definitions_only_referenced(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
        full_package_data: dict,
    ) -> None:
        """Unreferenced definitions should NOT appear in CFDefinitions."""
        # Create an unreferenced item type
        unreferenced_type = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("99999999-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uri="https://example.com/uri/unused-type",
            title="Unused Type",
            last_change_date_time=LCT,
        )
        db_session.add(unreferenced_type)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        defs = response.json()["CFDefinitions"]
        type_titles = [t["title"] for t in defs["CFItemTypes"]]
        assert "Unused Type" not in type_titles

    async def test_items_sorted_by_identifier(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """CFItems should be sorted by identifier ASC."""
        ids = [
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02",
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeee00",
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01",
        ]
        for id_str in ids:
            item = CFItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                cf_document_id=sample_document.id,
                identifier=uuid.UUID(id_str),
                uri=f"https://example.com/uri/{id_str}",
                full_statement=f"Statement {id_str}",
                last_change_date_time=LCT,
            )
            db_session.add(item)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        items = response.json()["CFItems"]
        identifiers = [i["identifier"] for i in items]
        assert identifiers == sorted(identifiers)

    async def test_definitions_empty_keys_excluded(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """Only non-empty definition keys should be present."""
        # Create item with item_type only (no concept, no license, no subjects)
        item_type = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aabbccdd-1111-2222-3333-444444444444"),
            uri="https://example.com/uri/it-only",
            title="TypeOnly",
            last_change_date_time=LCT,
        )
        db_session.add(item_type)
        await db_session.flush()

        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            cf_item_type_id=item_type.id,
            identifier=uuid.UUID("aabbccdd-5555-6666-7777-888888888888"),
            uri="https://example.com/uri/item-only",
            full_statement="Only has type",
            last_change_date_time=LCT,
        )
        db_session.add(item)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        defs = response.json()["CFDefinitions"]
        assert "CFItemTypes" in defs
        # These should NOT be present since nothing references them
        assert "CFConcepts" not in defs
        assert "CFLicenses" not in defs
        assert "CFSubjects" not in defs
        assert "CFAssociationGroupings" not in defs


class TestTenantIsolation:
    async def test_package_not_visible_across_tenants(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        response = await db_client.get(f"/{other_tenant_id}/ims/case/v1p1/CFPackages/{DOC_IDENTIFIER}")
        assert response.status_code == 404
