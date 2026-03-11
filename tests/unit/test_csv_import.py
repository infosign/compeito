"""Unit tests for CSV import service.

Tests the pure parsing/detection functions and integration with DB via fixtures.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant
from src.services.csv_import_service import (
    FormatType,
    ImportReport,
    _build_column_map,
    _detect_format,
    _is_valid_uuid,
    _parse_csv_list,
    _parse_date,
    _parse_int,
    _parse_metadata_lines,
    _simple_depth_from_indent,
    import_csv,
)


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_custom_format(self):
        assert _detect_format(["Identifier", "fullStatement", "humanCodingScheme"]) == FormatType.CUSTOM

    def test_custom_format_case_insensitive(self):
        assert _detect_format(["identifier", "FULLSTATEMENT", "other"]) == FormatType.CUSTOM

    def test_opensalt_format_by_case_item_identifier(self):
        assert _detect_format(["CASE Item Identifier", "Full Statement"]) == FormatType.OPENSALT

    def test_opensalt_format_by_full_statement(self):
        assert _detect_format(["Something", "Full Statement", "Other"]) == FormatType.OPENSALT

    def test_opensalt_case_insensitive(self):
        assert _detect_format(["case item identifier", "full statement"]) == FormatType.OPENSALT

    def test_simple_format_fallback(self):
        assert _detect_format(["name", "code"]) == FormatType.SIMPLE

    def test_fullstatement_without_identifier_is_simple(self):
        """fullStatement alone (no Identifier) falls back to simple."""
        assert _detect_format(["fullStatement", "humanCodingScheme"]) == FormatType.SIMPLE

    def test_empty_header(self):
        assert _detect_format([]) == FormatType.SIMPLE


class TestHelpers:
    def test_valid_uuid(self):
        assert _is_valid_uuid("d86774f2-1234-5678-9abc-def012345678")

    def test_invalid_uuid(self):
        assert not _is_valid_uuid("not-a-uuid")

    def test_parse_date_valid(self):
        assert _parse_date("2025-03-15") == date(2025, 3, 15)

    def test_parse_date_invalid(self):
        assert _parse_date("2025-13-45") is None

    def test_parse_date_empty(self):
        assert _parse_date("") is None

    def test_parse_int_valid(self):
        assert _parse_int("42") == 42

    def test_parse_int_negative(self):
        assert _parse_int("-10") == -10

    def test_parse_int_invalid(self):
        assert _parse_int("abc") is None

    def test_parse_int_overflow(self):
        assert _parse_int("3000000000") is None

    def test_parse_csv_list(self):
        assert _parse_csv_list("09, 10, 11") == ["09", "10", "11"]

    def test_parse_csv_list_filter_empty(self):
        assert _parse_csv_list("09,,11") == ["09", "11"]

    def test_parse_csv_list_empty(self):
        assert _parse_csv_list("") == []

    def test_simple_depth_spaces(self):
        assert _simple_depth_from_indent("    text") == 2

    def test_simple_depth_tabs(self):
        assert _simple_depth_from_indent("\t\ttext") == 2

    def test_simple_depth_mixed(self):
        assert _simple_depth_from_indent("\t  text") == 2

    def test_simple_depth_no_indent(self):
        assert _simple_depth_from_indent("text") == 0


class TestMetadataParsing:
    def test_basic_metadata(self):
        lines = [
            ["#title", "Test Document"],
            ["#version", "1.0"],
            ["#language", "ja"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert meta["title"] == "Test Document"
        assert meta["version"] == "1.0"
        assert meta["language"] == "ja"
        assert subjects == []
        assert warnings == []

    def test_subject_multi_value(self):
        lines = [
            ["#subject", "国語", "地理歴史", "公民"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert subjects == ["国語", "地理歴史", "公民"]

    def test_subject_trim_and_filter(self):
        lines = [
            ["#subject", "国語", "", "地理歴史"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert subjects == ["国語", "地理歴史"]

    def test_unknown_key(self):
        lines = [
            ["#unknown_key", "value"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert "Unknown metadata key '#unknown_key', ignored" in warnings

    def test_duplicate_key_overwrites(self):
        lines = [
            ["#title", "First"],
            ["#title", "Second"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert meta["title"] == "Second"
        assert any("Duplicate metadata key" in w for w in warnings)

    def test_empty_value(self):
        lines = [
            ["#title"],
        ]
        meta, subjects, warnings = _parse_metadata_lines(lines)
        assert meta["title"] == ""


class TestColumnMap:
    def test_builds_correct_map(self):
        header = ["Identifier", "fullStatement", "CFItemType"]
        m = _build_column_map(header)
        assert m["identifier"] == 0
        assert m["fullstatement"] == 1
        assert m["cfitemtype"] == 2


# ---------------------------------------------------------------------------
# Integration tests (require DB via conftest fixtures)
# ---------------------------------------------------------------------------


class TestImportCustomFormat:
    async def test_basic_import(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Test Doc\n"
            "#language,ja\n"
            "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType\n"
            ",国語,,,10,教科\n"
            ",現代の国語,,,20,科目\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 2
        assert report.items_updated == 0
        assert report.document_title == "Test Doc"
        assert report.item_types_created == 2  # 教科, 科目
        assert report.associations_created == 2

        # Verify items in DB
        result = await db_session.execute(
            select(CFItem).where(CFItem.cf_document_id == (
                select(CFDocument.id).where(
                    CFDocument.tenant_id == tenant.id,
                    CFDocument.title == "Test Doc",
                ).scalar_subquery()
            ))
        )
        items = list(result.scalars().all())
        assert len(items) == 2

    async def test_with_parent_hierarchy(self, db_session: AsyncSession, tenant: Tenant):
        parent_id = "aaaa1111-1111-1111-1111-111111111111"
        csv = (
            "#title,Hierarchy Test\n"
            f"Identifier,fullStatement,humanCodingScheme,parentIdentifier\n"
            f"{parent_id},Parent Item,P-1,\n"
            f",Child Item,C-1,{parent_id}\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 2
        assert report.associations_created == 2

        # Check isChildOf
        result = await db_session.execute(
            select(CFAssociation).where(
                CFAssociation.association_type == "isChildOf",
                CFAssociation.origin_node_identifier == str(
                    select(CFItem.identifier)
                    .where(CFItem.full_statement == "Child Item")
                    .scalar_subquery()
                ),
            )
        )

    async def test_upsert_by_identifier(self, db_session: AsyncSession, tenant: Tenant):
        """First import creates, second import updates."""
        csv1 = (
            "#title,Upsert Test\n"
            "Identifier,fullStatement,humanCodingScheme\n"
            "bbbb1111-1111-1111-1111-111111111111,Original Statement,H-1\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv1)
        await db_session.flush()
        assert report1.items_created == 1
        doc_ident = uuid.UUID(report1.document_identifier)

        csv2 = (
            "Identifier,fullStatement,humanCodingScheme\n"
            "bbbb1111-1111-1111-1111-111111111111,Updated Statement,H-1\n"
        ).encode("utf-8")

        report2 = await import_csv(
            db_session, tenant.id, csv2, doc_identifier=doc_ident,
        )
        await db_session.flush()
        assert report2.items_updated == 1
        assert report2.items_created == 0

        # Verify updated value
        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("bbbb1111-1111-1111-1111-111111111111")
            )
        )
        item = result.scalar_one()
        assert item.full_statement == "Updated Statement"

    async def test_upsert_by_human_coding_scheme(self, db_session: AsyncSession, tenant: Tenant):
        csv1 = (
            "#title,HCS Upsert Test\n"
            "Identifier,fullStatement,humanCodingScheme\n"
            ",Original,H-1\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv1)
        await db_session.flush()
        doc_ident = uuid.UUID(report1.document_identifier)

        csv2 = (
            "Identifier,fullStatement,humanCodingScheme\n"
            ",Updated by HCS,H-1\n"
        ).encode("utf-8")

        report2 = await import_csv(
            db_session, tenant.id, csv2, doc_identifier=doc_ident,
        )
        await db_session.flush()
        assert report2.items_updated == 1

    async def test_empty_cell_preserves_existing(self, db_session: AsyncSession, tenant: Tenant):
        """Empty cells in update should preserve existing values."""
        csv1 = (
            "#title,Preserve Test\n"
            "Identifier,fullStatement,humanCodingScheme,abbreviatedStatement\n"
            "cccc1111-1111-1111-1111-111111111111,Statement,H-1,Short form\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv1)
        await db_session.flush()
        doc_ident = uuid.UUID(report1.document_identifier)

        # Second import: abbreviatedStatement is empty → should preserve "Short form"
        csv2 = (
            "Identifier,fullStatement,humanCodingScheme,abbreviatedStatement\n"
            "cccc1111-1111-1111-1111-111111111111,Statement v2,H-1,\n"
        ).encode("utf-8")

        report2 = await import_csv(
            db_session, tenant.id, csv2, doc_identifier=doc_ident,
        )
        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(
                CFItem.identifier == uuid.UUID("cccc1111-1111-1111-1111-111111111111")
            )
        )
        item = result.scalar_one()
        assert item.full_statement == "Statement v2"
        assert item.abbreviated_statement == "Short form"  # preserved

    async def test_auto_sequence_numbers(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Seq Test\n"
            "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber\n"
            ",First,,,\n"
            ",Second,,,\n"
            ",Third,,,\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        # Check sequence numbers on isChildOf associations
        doc_id = (await db_session.execute(
            select(CFDocument.id).where(CFDocument.title == "Seq Test")
        )).scalar_one()

        result = await db_session.execute(
            select(CFAssociation)
            .where(CFAssociation.cf_document_id == doc_id)
            .order_by(CFAssociation.sequence_number)
        )
        assocs = list(result.scalars().all())
        assert [a.sequence_number for a in assocs] == [10, 20, 30]

    async def test_lookup_auto_generation(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Lookup Test\n"
            "#license,CC BY 4.0\n"
            "#subject,国語,数学\n"
            "Identifier,fullStatement,CFItemType,license\n"
            ",Item 1,知識及び技能,MIT\n"
            ",Item 2,知識及び技能,\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.item_types_created == 1  # 知識及び技能 (reused)
        assert report.licenses_created == 2  # CC BY 4.0 + MIT
        assert report.subjects_created == 2  # 国語, 数学
        assert report.item_types_existing == 0

        # Second reference to same item type should reuse
        # (already counted above via the two rows)

    async def test_invalid_identifier_skipped(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Invalid ID\n"
            "Identifier,fullStatement\n"
            "not-a-uuid,Bad Item\n"
            ",Good Item\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 1
        assert report.items_skipped == 0
        assert any("Invalid Identifier" in w for w in report.warnings)

    async def test_invalid_sequence_number_skipped(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Bad Seq\n"
            "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber\n"
            ",Good Item,,,,\n"
            ",Bad Seq Item,,,abc\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 1
        assert any("Invalid sequenceNumber" in w for w in report.warnings)

    async def test_empty_fullstatement_skipped(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Empty FS\n"
            "Identifier,fullStatement\n"
            ",\n"
            ",Valid Item\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 1

    async def test_doc_not_found_error(self, db_session: AsyncSession, tenant: Tenant):
        csv = b"Identifier,fullStatement\n,Item\n"
        fake_doc = uuid.uuid4()
        with pytest.raises(ValueError, match="Document not found"):
            await import_csv(
                db_session, tenant.id, csv, doc_identifier=fake_doc,
            )

    async def test_title_required_error(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "Identifier,fullStatement\n"
            ",Item\n"
        ).encode("utf-8")

        with pytest.raises(ValueError, match="Document title is required"):
            await import_csv(db_session, tenant.id, csv)

    async def test_bom_support(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,BOM Test\n"
            "Identifier,fullStatement\n"
            ",Item 1\n"
        ).encode("utf-8-sig")  # utf-8-sig adds BOM automatically

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.document_title == "BOM Test"
        assert report.items_created == 1

    async def test_duplicate_identifier_keeps_last(self, db_session: AsyncSession, tenant: Tenant):
        ident = "dddd1111-1111-1111-1111-111111111111"
        csv = (
            f"#title,Dup Test\n"
            f"Identifier,fullStatement\n"
            f"{ident},First occurrence\n"
            f"{ident},Second occurrence\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 1
        assert any("Duplicate Identifier" in w for w in report.warnings)

        result = await db_session.execute(
            select(CFItem).where(CFItem.identifier == uuid.UUID(ident))
        )
        item = result.scalar_one()
        assert item.full_statement == "Second occurrence"


class TestImportOpenSALTFormat:
    async def test_basic_opensalt(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,OpenSALT Test\n"
            "CASE Item Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,"
            "Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of\n"
            "aaaa2222-1111-1111-1111-111111111111,国語,,,,,教科,ja,,,,\n"
            "bbbb2222-1111-1111-1111-111111111111,現代の国語,,,,,科目,ja,,aaaa2222-1111-1111-1111-111111111111,10,\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 2
        assert report.document_title == "OpenSALT Test"

    async def test_opensalt_is_part_of_creates_doc(self, db_session: AsyncSession, tenant: Tenant):
        doc_ident = "eeee2222-1111-1111-1111-111111111111"
        csv = (
            "#title,IPO Doc\n"
            "CASE Item Identifier,Full Statement,Is Part Of\n"
            f",Item 1,{doc_ident}\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        # Document should have the Is Part Of identifier
        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID(doc_ident)
            )
        )
        doc = result.scalar_one()
        assert doc.title == "IPO Doc"

    async def test_opensalt_is_part_of_invalid_uuid(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Bad IPO\n"
            "CASE Item Identifier,Full Statement,Is Part Of\n"
            ",Item 1,not-a-uuid\n"
        ).encode("utf-8")

        with pytest.raises(ValueError, match="Is Part Of value is not a valid UUID"):
            await import_csv(db_session, tenant.id, csv)


class TestImportSimpleFormat:
    async def test_basic_simple(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Simple Test\n"
            "国語\n"
            "  現代の国語\n"
            "    言葉の特徴\n"
            "  言語文化\n"
            "地理歴史\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 5
        assert report.associations_created == 5

        # Verify depths
        result = await db_session.execute(
            select(CFItem)
            .where(CFItem.cf_document_id == (
                select(CFDocument.id)
                .where(CFDocument.title == "Simple Test")
                .scalar_subquery()
            ))
            .order_by(CFItem.depth)
        )
        items = list(result.scalars().all())
        depths = sorted([i.depth for i in items])
        assert depths == [0, 0, 1, 1, 2]

    async def test_simple_with_hcs_and_type(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Simple HCS\n"
            "国語,K-1,教科\n"
            "  現代の国語,K-1-1,科目\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 2
        assert report.item_types_created == 2

    async def test_simple_tab_indent(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Tab Test\n"
            "Root\n"
            "\tChild 1\n"
            "\t\tGrandchild\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 3

        result = await db_session.execute(
            select(CFItem).where(CFItem.full_statement == "Grandchild")
        )
        gc = result.scalar_one()
        assert gc.depth == 2

    async def test_simple_no_data(self, db_session: AsyncSession, tenant: Tenant):
        csv = b"#title,Empty Doc\n"

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.items_created == 0
        assert report.document_title == "Empty Doc"
        assert any("No items processed, empty document created" in w for w in report.warnings)

    async def test_simple_title_required(self, db_session: AsyncSession, tenant: Tenant):
        csv = b"Item 1\n"

        with pytest.raises(ValueError, match="Document title is required"):
            await import_csv(db_session, tenant.id, csv)

    async def test_simple_depth_jump_warning(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Jump Test\n"
            "Root\n"
            "      Deep Child\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert any("depth jumped" in w for w in report.warnings)


class TestDepthCalculation:
    async def test_correct_depths(self, db_session: AsyncSession, tenant: Tenant):
        p_id = "aaaa3333-1111-1111-1111-111111111111"
        c_id = "bbbb3333-1111-1111-1111-111111111111"
        gc_id = "cccc3333-1111-1111-1111-111111111111"
        csv = (
            "#title,Depth Test\n"
            "Identifier,fullStatement,parentIdentifier\n"
            f"{p_id},Parent,\n"
            f"{c_id},Child,{p_id}\n"
            f"{gc_id},Grandchild,{c_id}\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        result = await db_session.execute(
            select(CFItem).where(CFItem.identifier == uuid.UUID(gc_id))
        )
        gc = result.scalar_one()
        assert gc.depth == 2

    async def test_self_reference_treated_as_root(self, db_session: AsyncSession, tenant: Tenant):
        self_id = "aaaa4444-1111-1111-1111-111111111111"
        csv = (
            "#title,Self Ref\n"
            "Identifier,fullStatement,parentIdentifier\n"
            f"{self_id},Self Ref Item,{self_id}\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert any("parentIdentifier references self" in w for w in report.warnings)

        result = await db_session.execute(
            select(CFItem).where(CFItem.identifier == uuid.UUID(self_id))
        )
        item = result.scalar_one()
        assert item.depth == 0


class TestIsChildOfDeletion:
    async def test_update_deletes_existing_is_child_of(self, db_session: AsyncSession, tenant: Tenant):
        """Updating a document should delete all existing isChildOf and regenerate."""
        csv1 = (
            "#title,Delete Test\n"
            "Identifier,fullStatement\n"
            "aaaa5555-1111-1111-1111-111111111111,Item A\n"
            "bbbb5555-1111-1111-1111-111111111111,Item B\n"
        ).encode("utf-8")

        report1 = await import_csv(db_session, tenant.id, csv1)
        await db_session.flush()
        doc_ident = uuid.UUID(report1.document_identifier)
        assert report1.associations_created == 2

        # Re-import with only 1 item
        csv2 = (
            "Identifier,fullStatement\n"
            "aaaa5555-1111-1111-1111-111111111111,Item A updated\n"
        ).encode("utf-8")

        report2 = await import_csv(
            db_session, tenant.id, csv2, doc_identifier=doc_ident,
        )
        await db_session.flush()

        assert report2.existing_is_child_of_deleted == 2
        assert report2.associations_created == 1


class TestMetadataDocumentFields:
    async def test_all_metadata_fields(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Full Meta\n"
            "#version,2.0\n"
            "#creator,Author\n"
            "#publisher,Publisher Corp\n"
            "#description,A test document\n"
            "#language,en\n"
            "#adoption_status,Adopted\n"
            "#official_source_url,https://example.com\n"
            "#status_start_date,2025-01-01\n"
            "#status_end_date,2025-12-31\n"
            "#license,CC BY 4.0\n"
            "#subject,Math,Science\n"
            "Identifier,fullStatement\n"
            ",Item 1\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID(report.document_identifier)
            )
        )
        doc = result.scalar_one()
        assert doc.title == "Full Meta"
        assert doc.version == "2.0"
        assert doc.creator == "Author"
        assert doc.publisher == "Publisher Corp"
        assert doc.description == "A test document"
        assert doc.language == "en"
        assert doc.adoption_status == "Adopted"
        assert doc.official_source_url == "https://example.com"
        assert doc.status_start_date == date(2025, 1, 1)
        assert doc.status_end_date == date(2025, 12, 31)
        assert doc.cf_license_id is not None
        assert doc.subject == ["Math", "Science"]
        assert len(doc.subject_uri) == 2

    async def test_cli_title_overrides_metadata(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Meta Title\n"
            "Identifier,fullStatement\n"
            ",Item\n"
        ).encode("utf-8")

        report = await import_csv(
            db_session, tenant.id, csv, doc_title="CLI Title",
        )
        await db_session.flush()

        assert report.document_title == "CLI Title"

    async def test_invalid_status_date_warning(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Bad Date\n"
            "#status_start_date,not-a-date\n"
            "Identifier,fullStatement\n"
            ",Item\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert any("#status_start_date" in w for w in report.warnings)

        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID(report.document_identifier)
            )
        )
        doc = result.scalar_one()
        assert doc.status_start_date is None

    async def test_language_exceeds_limit(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Lang Test\n"
            "#language,this-is-way-too-long-for-language\n"
            "Identifier,fullStatement\n"
            ",Item\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert any("#language" in w for w in report.warnings)

        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID(report.document_identifier)
            )
        )
        doc = result.scalar_one()
        assert doc.language is None


class TestLookupReuse:
    async def test_item_type_reused_across_rows(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,Reuse Test\n"
            "Identifier,fullStatement,CFItemType\n"
            ",Item 1,知識\n"
            ",Item 2,知識\n"
            ",Item 3,技能\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.item_types_created == 2  # 知識, 技能

    async def test_license_shared_between_doc_and_item(self, db_session: AsyncSession, tenant: Tenant):
        csv = (
            "#title,License Share\n"
            "#license,MIT\n"
            "Identifier,fullStatement,license\n"
            ",Item 1,MIT\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        # MIT created once for doc, then reused from cache for item
        assert report.licenses_created == 1

        # Verify both doc and item point to same license
        result = await db_session.execute(
            select(CFDocument).where(
                CFDocument.identifier == uuid.UUID(report.document_identifier)
            )
        )
        doc = result.scalar_one()
        result = await db_session.execute(
            select(CFItem).where(CFItem.full_statement == "Item 1")
        )
        item = result.scalar_one()
        assert doc.cf_license_id == item.cf_license_id

    async def test_existing_lookup_found(self, db_session: AsyncSession, tenant: Tenant):
        """Pre-existing CFItemType should be found by title match."""
        pre = CFItemType(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/pre",
            title="既存タイプ",
            last_change_date_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(pre)
        await db_session.flush()

        csv = (
            "#title,Pre Existing\n"
            "Identifier,fullStatement,CFItemType\n"
            ",Item 1,既存タイプ\n"
        ).encode("utf-8")

        report = await import_csv(db_session, tenant.id, csv)
        await db_session.flush()

        assert report.item_types_created == 0
        assert report.item_types_existing == 1

        # Verify FK points to pre-existing record
        result = await db_session.execute(
            select(CFItem).where(CFItem.full_statement == "Item 1")
        )
        item = result.scalar_one()
        assert item.cf_item_type_id == pre.id
