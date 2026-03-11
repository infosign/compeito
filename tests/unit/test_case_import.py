"""Unit tests for external CASE source import service.

Uses httpx mock for HTTP calls and real DB for persistence tests.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
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
from src.services.case_import_service import (
    CaseImportReport,
    VALID_ASSOCIATION_TYPES,
    _is_valid_uuid,
    _parse_sequence_number,
    _validate_association,
    _validate_cf_package,
    fetch_cf_package,
    import_case_package,
)


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cf_package(
    doc_identifier: str = "aaaa0000-0000-0000-0000-000000000001",
    doc_title: str = "Test Document",
    items: list | None = None,
    associations: list | None = None,
    definitions: dict | None = None,
) -> dict:
    """Build a minimal valid CFPackage JSON."""
    return {
        "CFPackage": {
            "CFDocument": {
                "identifier": doc_identifier,
                "uri": f"https://example.com/uri/{doc_identifier}",
                "title": doc_title,
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            },
            "CFItems": items or [],
            "CFAssociations": associations or [],
            "CFDefinitions": definitions or {},
        }
    }


def _make_item(
    identifier: str = "bbbb0000-0000-0000-0000-000000000001",
    full_statement: str = "Test Item",
    **kwargs,
) -> dict:
    item = {
        "identifier": identifier,
        "uri": f"https://example.com/uri/{identifier}",
        "fullStatement": full_statement,
        "lastChangeDateTime": "2025-01-01T00:00:00Z",
        **kwargs,
    }
    return item


def _make_association(
    identifier: str = "cccc0000-0000-0000-0000-000000000001",
    assoc_type: str = "isChildOf",
    origin_ident: str = "bbbb0000-0000-0000-0000-000000000001",
    dest_ident: str = "aaaa0000-0000-0000-0000-000000000001",
) -> dict:
    return {
        "identifier": identifier,
        "uri": f"https://example.com/uri/{identifier}",
        "associationType": assoc_type,
        "originNodeURI": {
            "identifier": origin_ident,
            "uri": f"https://example.com/uri/{origin_ident}",
            "title": "Origin",
        },
        "destinationNodeURI": {
            "identifier": dest_ident,
            "uri": f"https://example.com/uri/{dest_ident}",
            "title": "Destination",
        },
        "lastChangeDateTime": "2025-01-01T00:00:00Z",
    }


def _make_mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "https://example.com"),
    )


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_cf_package(self):
        pkg = _make_cf_package()
        result = _validate_cf_package(pkg)
        assert "CFDocument" in result

    def test_missing_cf_package_key(self):
        with pytest.raises(ValueError, match="missing 'CFPackage' key"):
            _validate_cf_package({"other": "data"})

    def test_missing_cf_document(self):
        with pytest.raises(ValueError, match="CFDocument is missing"):
            _validate_cf_package({"CFPackage": {}})

    def test_invalid_identifier(self):
        pkg = _make_cf_package(doc_identifier="not-a-uuid")
        with pytest.raises(ValueError, match="identifier is missing or not a valid UUID"):
            _validate_cf_package(pkg)

    def test_empty_title(self):
        pkg = _make_cf_package(doc_title="   ")
        with pytest.raises(ValueError, match="title is missing or empty"):
            _validate_cf_package(pkg)


class TestAssociationValidation:
    def test_valid_association(self):
        assoc = _make_association()
        assert _validate_association(assoc) is None

    def test_missing_identifier(self):
        assoc = _make_association()
        del assoc["identifier"]
        assert "missing identifier" in _validate_association(assoc)

    def test_invalid_identifier(self):
        assoc = _make_association(identifier="bad")
        assert "not a valid UUID" in _validate_association(assoc)

    def test_missing_association_type(self):
        assoc = _make_association()
        del assoc["associationType"]
        assert "missing associationType" in _validate_association(assoc)

    def test_invalid_association_type(self):
        assoc = _make_association(assoc_type="invalidType")
        assert "invalid associationType" in _validate_association(assoc)

    def test_ext_prefix_valid(self):
        assoc = _make_association(assoc_type="ext:customType")
        assert _validate_association(assoc) is None

    def test_missing_origin_uri(self):
        assoc = _make_association()
        del assoc["originNodeURI"]["uri"]
        assert "missing originNodeURI.uri" in _validate_association(assoc)

    def test_missing_destination(self):
        assoc = _make_association()
        del assoc["destinationNodeURI"]
        assert "missing destinationNodeURI" in _validate_association(assoc)

    def test_all_standard_types_valid(self):
        for t in VALID_ASSOCIATION_TYPES:
            assoc = _make_association(assoc_type=t)
            assert _validate_association(assoc) is None


class TestSequenceNumber:
    def test_int(self):
        assert _parse_sequence_number(42, "", []) == 42

    def test_float_truncate(self):
        assert _parse_sequence_number(3.7, "", []) == 3

    def test_string_number(self):
        assert _parse_sequence_number("10", "", []) == 10

    def test_none(self):
        assert _parse_sequence_number(None, "", []) is None

    def test_invalid(self):
        w = []
        assert _parse_sequence_number("abc", "ctx", w) is None
        assert len(w) == 1

    def test_overflow(self):
        w = []
        assert _parse_sequence_number(3000000000, "ctx", w) is None
        assert len(w) == 1


# ---------------------------------------------------------------------------
# Fetch tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchCFPackage:
    async def test_direct_url(self):
        pkg_data = _make_cf_package()
        mock_response = _make_mock_response(pkg_data)

        with patch("src.services.case_import_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            data, warnings = await fetch_cf_package(
                "https://example.com/ims/case/v1p1/CFPackages/aaaa0000-0000-0000-0000-000000000001"
            )

        assert "CFPackage" in data
        assert warnings == []

    async def test_base_url_discovers_document(self):
        docs_data = {
            "CFDocuments": [{"identifier": "aaaa0000-0000-0000-0000-000000000001"}]
        }
        pkg_data = _make_cf_package()

        mock_docs_resp = _make_mock_response(docs_data)
        mock_pkg_resp = _make_mock_response(pkg_data)

        with patch("src.services.case_import_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_docs_resp, mock_pkg_resp])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            data, warnings = await fetch_cf_package(
                "https://example.com/ims/case/v1p1"
            )

        assert "CFPackage" in data

    async def test_multiple_documents_warning(self):
        docs_data = {
            "CFDocuments": [
                {"identifier": "aaaa0000-0000-0000-0000-000000000001"},
                {"identifier": "aaaa0000-0000-0000-0000-000000000002"},
            ]
        }
        pkg_data = _make_cf_package()

        mock_docs_resp = _make_mock_response(docs_data)
        mock_pkg_resp = _make_mock_response(pkg_data)

        with patch("src.services.case_import_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_docs_resp, mock_pkg_resp])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            data, warnings = await fetch_cf_package(
                "https://example.com/ims/case/v1p1"
            )

        assert any("Remote server has 2 documents" in w for w in warnings)

    async def test_empty_documents_error(self):
        docs_data = {"CFDocuments": []}
        mock_resp = _make_mock_response(docs_data)

        with patch("src.services.case_import_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with pytest.raises(ValueError, match="No documents found"):
                await fetch_cf_package("https://example.com/ims/case/v1p1")

    async def test_http_error(self):
        mock_resp = httpx.Response(
            status_code=404,
            request=httpx.Request("GET", "https://example.com/not-found"),
        )

        with patch("src.services.case_import_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with pytest.raises(ValueError, match="HTTP 404"):
                await fetch_cf_package(
                    "https://example.com/ims/case/v1p1/CFPackages/xxx"
                )


# ---------------------------------------------------------------------------
# Integration tests (DB)
# ---------------------------------------------------------------------------


class TestImportBasic:
    async def test_new_document_import(self, db_session: AsyncSession, tenant: Tenant):
        pkg = _make_cf_package(
            items=[_make_item()],
            associations=[_make_association()],
        )

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report.items_created == 1
        assert report.associations_created == 1
        assert report.document_title == "Test Document"

        # Verify document
        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID("aaaa0000-0000-0000-0000-000000000001")
            )
        )
        doc = result.scalar_one()
        assert doc.title == "Test Document"
        assert doc.uri == "https://example.com/uri/aaaa0000-0000-0000-0000-000000000001"

    async def test_update_existing_document(self, db_session: AsyncSession, tenant: Tenant):
        """Re-import with same identifier should update."""
        pkg = _make_cf_package(items=[_make_item()])

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report1 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report1.items_created == 1

        # Re-import
        pkg2 = _make_cf_package(
            doc_title="Updated Title",
            items=[_make_item(full_statement="Updated Statement")],
        )
        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg2, [])
            report2 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report2.items_updated == 1
        assert report2.items_created == 0

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb0000-0000-0000-0000-000000000001")
            )
        )
        item = result.scalar_one()
        assert item.full_statement == "Updated Statement"

    async def test_doc_identifier_override(self, db_session: AsyncSession, tenant: Tenant):
        """--doc flag should use existing document."""
        # Create a document first
        existing_doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("dddd0000-0000-0000-0000-000000000001"),
            uri="https://example.com/existing",
            title="Existing",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(existing_doc)
        await db_session.flush()

        pkg = _make_cf_package(items=[_make_item()])
        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
                doc_identifier=uuid.UUID("dddd0000-0000-0000-0000-000000000001"),
            )

        await db_session.flush()
        assert report.items_created == 1
        # Document identifier should be preserved (not overwritten by external)
        assert report.document_identifier == "dddd0000-0000-0000-0000-000000000001"

    async def test_doc_not_found_error(self, db_session: AsyncSession, tenant: Tenant):
        pkg = _make_cf_package()
        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            with pytest.raises(ValueError, match="Document not found"):
                await import_case_package(
                    db_session, tenant.id, "https://example.com/CFPackages/xxx",
                    doc_identifier=uuid.uuid4(),
                )


class TestDefinitionsImport:
    async def test_import_all_definition_types(self, db_session: AsyncSession, tenant: Tenant):
        defs = {
            "CFItemTypes": [{
                "identifier": "1111aaaa-0000-0000-0000-000000000001",
                "uri": "https://example.com/type/1",
                "title": "Knowledge",
                "typeCode": "K",
                "hierarchyCode": "1",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
            "CFSubjects": [{
                "identifier": "2222aaaa-0000-0000-0000-000000000001",
                "uri": "https://example.com/subject/1",
                "title": "Mathematics",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
            "CFConcepts": [{
                "identifier": "3333aaaa-0000-0000-0000-000000000001",
                "uri": "https://example.com/concept/1",
                "title": "Algebra",
                "keywords": "equations|variables",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
            "CFLicenses": [{
                "identifier": "4444aaaa-0000-0000-0000-000000000001",
                "uri": "https://example.com/license/1",
                "title": "CC BY 4.0",
                "licenseText": "Creative Commons",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
            "CFAssociationGroupings": [{
                "identifier": "5555aaaa-0000-0000-0000-000000000001",
                "uri": "https://example.com/grouping/1",
                "title": "Cross-Subject",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        pkg = _make_cf_package(definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report.item_types_created == 1
        assert report.subjects_created == 1
        assert report.concepts_created == 1
        assert report.licenses_created == 1
        assert report.groupings_created == 1

        # Verify specific fields
        result = await db_session.execute(
            select(CFItemType).where(
                CFItemType.identifier == uuid.UUID("1111aaaa-0000-0000-0000-000000000001")
            )
        )
        it = result.scalar_one()
        assert it.title == "Knowledge"
        assert it.type_code == "K"
        assert it.hierarchy_code == "1"

        result = await db_session.execute(
            select(CFConcept).where(
                CFConcept.identifier == uuid.UUID("3333aaaa-0000-0000-0000-000000000001")
            )
        )
        concept = result.scalar_one()
        assert concept.keywords == "equations|variables"

    async def test_definition_upsert_update(self, db_session: AsyncSession, tenant: Tenant):
        """Re-import should update existing definitions."""
        defs = {
            "CFItemTypes": [{
                "identifier": "1111bbbb-0000-0000-0000-000000000001",
                "uri": "https://example.com/type/1",
                "title": "Original",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        pkg = _make_cf_package(definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report1 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report1.item_types_created == 1

        # Re-import with changed title
        defs2 = {
            "CFItemTypes": [{
                "identifier": "1111bbbb-0000-0000-0000-000000000001",
                "uri": "https://example.com/type/1",
                "title": "Updated",
                "lastChangeDateTime": "2025-06-01T00:00:00Z",
            }],
        }
        pkg2 = _make_cf_package(definitions=defs2)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg2, [])
            report2 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report2.item_types_updated == 1
        assert report2.item_types_created == 0

    async def test_definition_no_change(self, db_session: AsyncSession, tenant: Tenant):
        """Re-import with identical data should count as existing."""
        defs = {
            "CFItemTypes": [{
                "identifier": "1111cccc-0000-0000-0000-000000000001",
                "uri": "https://example.com/type/1",
                "title": "Stable",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        pkg = _make_cf_package(definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        # Re-import same
        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report2 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report2.item_types_existing == 1
        assert report2.item_types_updated == 0

    async def test_definition_skip_invalid(self, db_session: AsyncSession, tenant: Tenant):
        defs = {
            "CFItemTypes": [
                {"identifier": "not-a-uuid", "title": "Bad"},
                {"identifier": "1111dddd-0000-0000-0000-000000000001", "title": ""},
                {"title": "No ID"},
            ],
        }
        pkg = _make_cf_package(definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report.item_types_skipped == 3


class TestItemFKResolution:
    async def test_item_type_fk_resolved(self, db_session: AsyncSession, tenant: Tenant):
        type_ident = "1111eeee-0000-0000-0000-000000000001"
        defs = {
            "CFItemTypes": [{
                "identifier": type_ident,
                "uri": "https://example.com/type/1",
                "title": "Knowledge",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        items = [_make_item(
            CFItemTypeURI={"identifier": type_ident, "uri": "https://example.com/type/1", "title": "Knowledge"},
        )]
        pkg = _make_cf_package(items=items, definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb0000-0000-0000-0000-000000000001")
            )
        )
        item = result.scalar_one()
        assert item.cf_item_type_id is not None

    async def test_item_type_not_found_warning(self, db_session: AsyncSession, tenant: Tenant):
        items = [_make_item(
            CFItemTypeURI={"identifier": "ffff0000-0000-0000-0000-000000000001", "uri": "x", "title": "Missing"},
        )]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert any("CFItemType" in w and "not found" in w for w in report.warnings)

    async def test_concept_fk_resolved(self, db_session: AsyncSession, tenant: Tenant):
        concept_ident = "3333ffff-0000-0000-0000-000000000001"
        defs = {
            "CFConcepts": [{
                "identifier": concept_ident,
                "uri": "https://example.com/concept/1",
                "title": "Algebra",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        items = [_make_item(
            conceptKeywordsURI={"identifier": concept_ident, "uri": "x", "title": "Algebra"},
        )]
        pkg = _make_cf_package(items=items, definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb0000-0000-0000-0000-000000000001")
            )
        )
        item = result.scalar_one()
        assert item.cf_concept_id is not None


class TestAssociationImport:
    async def test_association_grouping_fk(self, db_session: AsyncSession, tenant: Tenant):
        grp_ident = "5555ffff-0000-0000-0000-000000000001"
        defs = {
            "CFAssociationGroupings": [{
                "identifier": grp_ident,
                "uri": "https://example.com/grouping/1",
                "title": "Test Group",
                "lastChangeDateTime": "2025-01-01T00:00:00Z",
            }],
        }
        assocs = [_make_association(
            assoc_type="isPeerOf",
        )]
        assocs[0]["CFAssociationGroupingURI"] = {
            "identifier": grp_ident, "uri": "x", "title": "Test Group",
        }
        pkg = _make_cf_package(associations=assocs, definitions=defs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFAssociation).where(
                CFAssociation.identifier == uuid.UUID("cccc0000-0000-0000-0000-000000000001")
            )
        )
        assoc = result.scalar_one()
        assert assoc.cf_association_grouping_id is not None

    async def test_skip_invalid_association(self, db_session: AsyncSession, tenant: Tenant):
        assocs = [
            _make_association(identifier="bad-uuid"),
            _make_association(assoc_type="invalidType"),
        ]
        pkg = _make_cf_package(associations=assocs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report.associations_skipped == 2

    async def test_association_update_on_reimport(self, db_session: AsyncSession, tenant: Tenant):
        assocs = [_make_association()]
        pkg = _make_cf_package(associations=assocs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report1 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report1.associations_created == 1

        # Re-import same
        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report2 = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report2.associations_updated == 1
        assert report2.associations_created == 0


class TestItemSkipping:
    async def test_skip_item_no_identifier(self, db_session: AsyncSession, tenant: Tenant):
        items = [{"fullStatement": "No ID Item", "uri": "x"}]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        assert report.items_skipped == 1
        assert any("missing identifier" in w for w in report.warnings)

    async def test_skip_item_empty_fullstatement(self, db_session: AsyncSession, tenant: Tenant):
        items = [_make_item(full_statement="   ")]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        assert report.items_skipped == 1

    async def test_skip_item_bad_uuid(self, db_session: AsyncSession, tenant: Tenant):
        items = [_make_item(identifier="not-a-uuid")]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        assert report.items_skipped == 1


class TestDepthCalculation:
    async def test_depth_from_is_child_of(self, db_session: AsyncSession, tenant: Tenant):
        doc_ident = "aaaa0000-0000-0000-0000-000000000001"
        parent_ident = "bbbb0000-0000-0000-0000-000000000001"
        child_ident = "bbbb0000-0000-0000-0000-000000000002"

        items = [
            _make_item(identifier=parent_ident, full_statement="Parent"),
            _make_item(identifier=child_ident, full_statement="Child"),
        ]
        assocs = [
            _make_association(
                identifier="cccc0000-0000-0000-0000-000000000001",
                origin_ident=parent_ident,
                dest_ident=doc_ident,
            ),
            _make_association(
                identifier="cccc0000-0000-0000-0000-000000000002",
                origin_ident=child_ident,
                dest_ident=parent_ident,
            ),
        ]
        pkg = _make_cf_package(items=items, associations=assocs)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(CFItem.identifier == uuid.UUID(child_ident))
        )
        child = result.scalar_one()
        assert child.depth == 1


class TestURIPreservation:
    async def test_external_uri_preserved(self, db_session: AsyncSession, tenant: Tenant):
        """External URIs should be kept, not replaced with local URIs."""
        items = [_make_item()]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb0000-0000-0000-0000-000000000001")
            )
        )
        item = result.scalar_one()
        assert item.uri == "https://example.com/uri/bbbb0000-0000-0000-0000-000000000001"

    async def test_uri_preserved_on_update(self, db_session: AsyncSession, tenant: Tenant):
        items = [_make_item()]
        pkg = _make_cf_package(items=items)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg, [])
            await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        # Re-import with different URI
        items2 = [_make_item()]
        items2[0]["uri"] = "https://new-server.com/different-uri"
        pkg2 = _make_cf_package(items=items2)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg2, [])
            await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb0000-0000-0000-0000-000000000001")
            )
        )
        item = result.scalar_one()
        # URI should be the original, not the new one
        assert item.uri == "https://example.com/uri/bbbb0000-0000-0000-0000-000000000001"


class TestItemMovement:
    async def test_item_moved_between_documents(self, db_session: AsyncSession, tenant: Tenant):
        """Item in another document should be moved to current document."""
        # Create first document with an item
        doc1_ident = "aaaa0000-0000-0000-0000-000000000010"
        items1 = [_make_item(identifier="bbbb0000-0000-0000-0000-000000000010")]
        pkg1 = _make_cf_package(doc_identifier=doc1_ident, items=items1)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg1, [])
            await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()

        # Import second document that claims the same item
        doc2_ident = "aaaa0000-0000-0000-0000-000000000020"
        items2 = [_make_item(identifier="bbbb0000-0000-0000-0000-000000000010", full_statement="Moved")]
        pkg2 = _make_cf_package(doc_identifier=doc2_ident, doc_title="Second Doc", items=items2)

        with patch("src.services.case_import_service.fetch_cf_package") as mock_fetch:
            mock_fetch.return_value = (pkg2, [])
            report = await import_case_package(
                db_session, tenant.id, "https://example.com/CFPackages/xxx",
            )

        await db_session.flush()
        assert report.items_updated == 1
        assert any("moved from document" in w for w in report.warnings)
