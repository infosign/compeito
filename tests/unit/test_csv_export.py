"""Unit tests for CSV export service."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.tenant import Tenant
from src.services.csv_export_service import export_csv, export_opensalt_csv
from src.services.csv_import_service import import_csv

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
LCT = datetime(2025, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def doc_with_items(db_session: AsyncSession, tenant: Tenant):
    """Create a document with items and isChildOf associations."""
    doc = CFDocument(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        uri="https://example.com/doc/1",
        title="Export Test Doc",
        creator="Author",
        language="ja",
        version="1.0",
        last_change_date_time=LCT,
    )
    db_session.add(doc)
    await db_session.flush()

    item1 = CFItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        uri="https://example.com/item/1",
        full_statement="Root Item 1",
        human_coding_scheme="R-1",
        depth=0,
        last_change_date_time=LCT,
    )
    item2 = CFItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"),
        uri="https://example.com/item/2",
        full_statement="Child Item 1",
        human_coding_scheme="R-1-1",
        depth=1,
        last_change_date_time=LCT,
    )
    item3 = CFItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.UUID("bbbbbbbb-0000-0000-0000-000000000003"),
        uri="https://example.com/item/3",
        full_statement="Root Item 2",
        human_coding_scheme="R-2",
        depth=0,
        last_change_date_time=LCT,
    )
    db_session.add_all([item1, item2, item3])
    await db_session.flush()

    doc_ident = str(doc.identifier)
    # isChildOf: item1 -> doc (root)
    a1 = CFAssociation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/assoc/1",
        association_type="isChildOf",
        origin_node_identifier=str(item1.identifier),
        origin_node_uri=item1.uri,
        destination_node_identifier=doc_ident,
        destination_node_uri=doc.uri,
        sequence_number=10,
        last_change_date_time=LCT,
    )
    # isChildOf: item2 -> item1
    a2 = CFAssociation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/assoc/2",
        association_type="isChildOf",
        origin_node_identifier=str(item2.identifier),
        origin_node_uri=item2.uri,
        destination_node_identifier=str(item1.identifier),
        destination_node_uri=item1.uri,
        sequence_number=10,
        last_change_date_time=LCT,
    )
    # isChildOf: item3 -> doc (root)
    a3 = CFAssociation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/assoc/3",
        association_type="isChildOf",
        origin_node_identifier=str(item3.identifier),
        origin_node_uri=item3.uri,
        destination_node_identifier=doc_ident,
        destination_node_uri=doc.uri,
        sequence_number=20,
        last_change_date_time=LCT,
    )
    db_session.add_all([a1, a2, a3])
    await db_session.flush()

    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBasicExport:
    async def test_export_produces_csv(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        assert csv_str
        lines = csv_str.strip().split("\n")
        # Should have metadata + header + 3 data rows
        assert len(lines) >= 4  # at least meta + header + data

    async def test_metadata_rows(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        assert "#title,Export Test Doc" in csv_str
        assert "#language,ja" in csv_str
        assert "#version,1.0" in csv_str
        assert "#creator,Author" in csv_str

    async def test_header_row(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        lines = csv_str.strip().split("\n")
        # Find header line (after metadata)
        header_line = None
        for line in lines:
            if line.startswith("Identifier,"):
                header_line = line
                break
        assert header_line is not None
        assert "fullStatement" in header_line
        assert "parentIdentifier" in header_line

    async def test_depth_first_order(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        lines = csv_str.strip().split("\n")
        # Find data rows (after header)
        data_start = None
        for i, line in enumerate(lines):
            if line.startswith("Identifier,"):
                data_start = i + 1
                break
        assert data_start is not None

        data_lines = lines[data_start:]
        statements = []
        for line in data_lines:
            # Second field is fullStatement
            parts = line.split(",")
            if len(parts) > 1:
                statements.append(parts[1])

        # Depth-first: Root 1, Child 1, Root 2
        assert statements == ["Root Item 1", "Child Item 1", "Root Item 2"]

    async def test_parent_identifier_output(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        # Child Item 1 should have Root Item 1's identifier as parent
        assert "bbbbbbbb-0000-0000-0000-000000000001" in csv_str
        lines = csv_str.strip().split("\n")
        for line in lines:
            if "Child Item 1" in line:
                parts = line.split(",")
                # parentIdentifier is 4th column (index 3)
                assert parts[3] == "bbbbbbbb-0000-0000-0000-000000000001"
                break

    async def test_root_items_no_parent(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        lines = csv_str.strip().split("\n")
        for line in lines:
            if "Root Item 1" in line:
                parts = line.split(",")
                # parentIdentifier should be empty for root items
                assert parts[3] == ""
                break

    async def test_lf_line_endings(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        doc_with_items: CFDocument,
    ):
        csv_str = await export_csv(
            db_session,
            tenant.id,
            doc_with_items.identifier,
        )
        assert "\r\n" not in csv_str
        assert "\n" in csv_str


class TestMetadataOutput:
    async def test_license_metadata(self, db_session: AsyncSession, tenant: Tenant):
        lic = CFLicense(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/lic",
            title="CC BY 4.0",
            last_change_date_time=LCT,
        )
        db_session.add(lic)
        await db_session.flush()

        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-1111-0000-0000-000000000001"),
            uri="https://example.com/doc",
            title="License Doc",
            cf_license_id=lic.id,
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        assert "#license,CC BY 4.0" in csv_str

    async def test_subject_metadata(self, db_session: AsyncSession, tenant: Tenant):
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-2222-0000-0000-000000000001"),
            uri="https://example.com/doc",
            title="Subject Doc",
            subject=["国語", "数学", "英語"],
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        assert "#subject,国語,数学,英語" in csv_str

    async def test_empty_subject_not_output(self, db_session: AsyncSession, tenant: Tenant):
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-3333-0000-0000-000000000001"),
            uri="https://example.com/doc",
            title="No Subject",
            subject=[],
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        assert "#subject" not in csv_str

    async def test_status_dates_metadata(self, db_session: AsyncSession, tenant: Tenant):
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-4444-0000-0000-000000000001"),
            uri="https://example.com/doc",
            title="Dates Doc",
            status_start_date=date(2025, 1, 1),
            status_end_date=date(2025, 12, 31),
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        assert "#status_start_date,2025-01-01" in csv_str
        assert "#status_end_date,2025-12-31" in csv_str


class TestItemFieldsExport:
    async def test_item_type_and_education_level(self, db_session: AsyncSession, tenant: Tenant):
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-5555-0000-0000-000000000001"),
            uri="x",
            title="Fields Doc",
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        it = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="x",
            title="Knowledge",
            last_change_date_time=LCT,
        )
        db_session.add(it)
        await db_session.flush()

        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=doc.id,
            identifier=uuid.UUID("bbbbbbbb-5555-0000-0000-000000000001"),
            uri="x",
            full_statement="Test Item",
            cf_item_type_id=it.id,
            education_level=["09", "10", "11"],
            concept_keywords=["分析", "評価"],
            depth=0,
            last_change_date_time=LCT,
        )
        db_session.add(item)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        assert "Knowledge" in csv_str
        assert '"09,10,11"' in csv_str  # CSV-quoted because contains commas
        assert '"分析,評価"' in csv_str


class TestSortOrder:
    async def test_natsort_ordering(self, db_session: AsyncSession, tenant: Tenant):
        """Items with same parent should be sorted by sequence, then hcs natsort."""
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("aaaaaaaa-6666-0000-0000-000000000001"),
            uri="x",
            title="Sort Doc",
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        items = []
        for i, hcs in enumerate(["A-10", "A-2", "A-1"]):
            item = CFItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                cf_document_id=doc.id,
                identifier=uuid.UUID(f"bbbbbbbb-6666-0000-0000-00000000000{i + 1}"),
                uri="x",
                full_statement=f"Item {hcs}",
                human_coding_scheme=hcs,
                depth=0,
                last_change_date_time=LCT,
            )
            items.append(item)
            db_session.add(item)
        await db_session.flush()

        doc_ident = str(doc.identifier)
        # All root items, same sequence number (10)
        for item in items:
            a = CFAssociation(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                cf_document_id=doc.id,
                identifier=uuid.uuid4(),
                uri="x",
                association_type="isChildOf",
                origin_node_identifier=str(item.identifier),
                origin_node_uri=item.uri,
                destination_node_identifier=doc_ident,
                destination_node_uri=doc.uri,
                sequence_number=10,
                last_change_date_time=LCT,
            )
            db_session.add(a)
        await db_session.flush()

        csv_str = await export_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        data_lines = [line for line in lines if not line.startswith("#") and not line.startswith("Identifier")]
        statements = [line.split(",")[1] for line in data_lines]
        # natsort: A-1 < A-2 < A-10
        assert statements == ["Item A-1", "Item A-2", "Item A-10"]


class TestRoundTrip:
    async def test_export_reimport(self, db_session: AsyncSession, tenant: Tenant):
        """Export then re-import should preserve data."""
        # Create via CSV import
        csv_input = (
            "#title,Round Trip Test\n"
            "#language,ja\n"
            "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType\n"
            "11110000-0000-0000-0000-000000000001,国語,K-1,,10,教科\n"
            "11110000-0000-0000-0000-000000000002,現代の国語,K-1-1,11110000-0000-0000-0000-000000000001,10,科目\n"
            "11110000-0000-0000-0000-000000000003,古典,K-1-2,11110000-0000-0000-0000-000000000001,20,科目\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv_input)
        await db_session.flush()
        doc_ident = uuid.UUID(report1.document_identifier)

        # Export
        csv_output = await export_csv(db_session, tenant.id, doc_ident)

        # Verify exported CSV has correct structure
        lines = csv_output.strip().split("\n")
        assert any("#title,Round Trip Test" in line for line in lines)
        assert any("#language,ja" in line for line in lines)

        # Find data rows
        data_lines = [line for line in lines if not line.startswith("#") and not line.startswith("Identifier")]
        assert len(data_lines) == 3

        # First should be 国語 (root, seq 10)
        assert "国語" in data_lines[0]
        # Second should be 現代の国語 (child of 国語, seq 10)
        assert "現代の国語" in data_lines[1]
        # Third should be 古典 (child of 国語, seq 20)
        assert "古典" in data_lines[2]

        # Re-import into same document
        report2 = await import_csv(
            db_session,
            tenant.id,
            csv_output.encode("utf-8"),
            doc_identifier=doc_ident,
        )
        await db_session.flush()

        # All items should be updated (not created new)
        assert report2.items_updated == 3
        assert report2.items_created == 0


class TestDocumentNotFound:
    async def test_not_found_raises(self, db_session: AsyncSession, tenant: Tenant):
        with pytest.raises(ValueError, match="Document not found"):
            await export_csv(db_session, tenant.id, uuid.uuid4())


# ---------------------------------------------------------------------------
# OpenSALT format export tests
# ---------------------------------------------------------------------------


class TestOpenSALTExport:
    async def test_opensalt_header(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        doc = doc_with_items
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        # Find header line (first non-metadata line)
        header_line = next(line for line in lines if not line.startswith("#"))
        assert header_line.startswith("CASE Item Identifier,")
        assert "Is Part Of" in header_line
        assert "Is Child Of" in header_line

    async def test_opensalt_is_part_of(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        """Every data row should have document identifier in Is Part Of column."""
        doc = doc_with_items
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        data_lines = [
            line for line in lines if not line.startswith("#") and not line.startswith("CASE Item Identifier")
        ]
        doc_ident = str(doc.identifier)
        for line in data_lines:
            assert line.endswith(doc_ident)

    async def test_opensalt_is_child_of(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        """Child items have parent identifier; root items have empty Is Child Of."""
        doc = doc_with_items
        # Item identifiers from the fixture
        item1_ident = "bbbbbbbb-0000-0000-0000-000000000001"
        item2_ident = "bbbbbbbb-0000-0000-0000-000000000002"
        item3_ident = "bbbbbbbb-0000-0000-0000-000000000003"
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)

        import csv as csv_mod
        import io

        reader = csv_mod.reader(io.StringIO(csv_str))
        rows = [row for row in reader if not row[0].startswith("#")]
        header = rows[0]
        is_child_of_idx = header.index("Is Child Of")

        data_rows = {row[0]: row for row in rows[1:]}
        # item1 is root -> empty Is Child Of
        assert data_rows[item1_ident][is_child_of_idx] == ""
        # item2 is child of item1
        assert data_rows[item2_ident][is_child_of_idx] == item1_ident
        # item3 is root -> empty Is Child Of
        assert data_rows[item3_ident][is_child_of_idx] == ""

    async def test_opensalt_license_column_empty(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        """License column should always be empty in OpenSALT format."""
        doc = doc_with_items
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)

        import csv as csv_mod
        import io

        reader = csv_mod.reader(io.StringIO(csv_str))
        rows = [row for row in reader if not row[0].startswith("#")]
        header = rows[0]
        license_idx = header.index("License")
        for row in rows[1:]:
            assert row[license_idx] == ""

    async def test_opensalt_metadata_rows(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        doc = doc_with_items
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        assert any("#title,Export Test Doc" in line for line in lines)
        assert any("#language,ja" in line for line in lines)

    async def test_opensalt_depth_first_order(self, db_session: AsyncSession, tenant: Tenant, doc_with_items):
        """Items should be in depth-first order: R-1, R-1-1, R-2."""
        doc = doc_with_items
        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        data_lines = [
            line for line in lines if not line.startswith("#") and not line.startswith("CASE Item Identifier")
        ]
        statements = [line.split(",")[1] for line in data_lines]
        assert statements == ["Root Item 1", "Child Item 1", "Root Item 2"]

    async def test_opensalt_empty_document(self, db_session: AsyncSession, tenant: Tenant):
        """Document with no items should produce metadata + header only."""
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/doc/empty",
            title="Empty Doc",
            last_change_date_time=LCT,
        )
        db_session.add(doc)
        await db_session.flush()

        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)
        lines = csv_str.strip().split("\n")
        data_lines = [
            line for line in lines if not line.startswith("#") and not line.startswith("CASE Item Identifier")
        ]
        assert len(data_lines) == 0

    async def test_opensalt_column_mapping(self, db_session: AsyncSession, tenant: Tenant):
        """Verify specific fields map to correct OpenSALT columns."""
        item_type = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/type/1",
            title="教科",
            last_change_date_time=LCT,
        )
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.UUID("dddddddd-0000-0000-0000-000000000001"),
            uri="https://example.com/doc/map",
            title="Mapping Test",
            language="ja",
            last_change_date_time=LCT,
        )
        db_session.add_all([item_type, doc])
        await db_session.flush()

        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=doc.id,
            identifier=uuid.UUID("eeeeeeee-0000-0000-0000-000000000001"),
            uri="https://example.com/item/map",
            full_statement="国語",
            abbreviated_statement="Kokugo",
            language="ja",
            cf_item_type_id=item_type.id,
            depth=0,
            last_change_date_time=LCT,
        )
        db_session.add(item)
        await db_session.flush()

        csv_str = await export_opensalt_csv(db_session, tenant.id, doc.identifier)

        import csv as csv_mod
        import io

        reader = csv_mod.reader(io.StringIO(csv_str))
        rows = [row for row in reader if not row[0].startswith("#")]
        header = rows[0]
        data = dict(zip(header, rows[1]))

        assert data["CASE Item Identifier"] == str(item.identifier)
        assert data["Full Statement"] == "国語"
        assert data["Abbreviated Statement"] == "Kokugo"
        assert data["CF Item Type"] == "教科"
        assert data["Language"] == "ja"
        assert data["Is Part Of"] == str(doc.identifier)


class TestOpenSALTRoundTrip:
    async def test_opensalt_export_reimport(self, db_session: AsyncSession, tenant: Tenant):
        """Export in OpenSALT format, reimport, verify data preserved."""
        # Create via custom CSV import
        csv_input = (
            "#title,OpenSALT RT\n"
            "#language,ja\n"
            "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType\n"
            "11110000-0000-0000-0000-000000000001,国語,K-1,,10,\n"
            "11110000-0000-0000-0000-000000000002,現代の国語,K-1-1,11110000-0000-0000-0000-000000000001,10,\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv_input)
        await db_session.flush()
        doc_ident = uuid.UUID(report1.document_identifier)

        # Export in OpenSALT format
        csv_output = await export_opensalt_csv(db_session, tenant.id, doc_ident)

        # Verify structure
        lines = csv_output.strip().split("\n")
        assert any("#title,OpenSALT RT" in line for line in lines)
        header_line = next(line for line in lines if line.startswith("CASE Item Identifier"))
        assert "Is Part Of" in header_line

        # Reimport the OpenSALT CSV
        report2 = await import_csv(db_session, tenant.id, csv_output.encode("utf-8"))
        await db_session.flush()
        assert report2.items_updated == 2
        assert report2.items_created == 0
