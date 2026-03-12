"""Unit tests for rubric CSV import service."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
from src.models.tenant import Tenant
from src.services.csv_rubric_import_service import import_rubric_csv

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

RUBRIC_IDENT = "eee10000-0000-0000-0000-000000000001"
CRIT_IDENT = "eee20000-0000-0000-0000-000000000001"
LEVEL_IDENT = "eee30000-0000-0000-0000-000000000001"


@pytest.fixture
async def doc(db_session: AsyncSession, tenant: Tenant) -> CFDocument:
    doc = CFDocument(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID(DOC_IDENTIFIER),
        uri=f"https://example.com/uri/{DOC_IDENTIFIER}",
        title="Test Document",
        last_change_date_time=LCT,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


FULL_CSV = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,{RUBRIC_IDENT},,,Test Rubric,A rubric for testing,,,,,,,
Criterion,{CRIT_IDENT},{RUBRIC_IDENT},,,Quality criterion,Quality,1.5,1,,,,
Level,{LEVEL_IDENT},,{CRIT_IDENT},,Excellent performance,,,1,Excellent,5.0,Outstanding work,
"""


class TestBasicImport:
    async def test_import_full_hierarchy(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(FULL_CSV))

        assert report.rubrics_created == 1
        assert report.criteria_created == 1
        assert report.levels_created == 1
        assert report.document_title == "Test Document"

        # Verify rubric
        result = await db_session.execute(select(CFRubric).where(CFRubric.identifier == uuid.UUID(RUBRIC_IDENT)))
        rubric = result.scalar_one()
        assert rubric.title == "Test Rubric"

        # Verify criterion
        result = await db_session.execute(
            select(CFRubricCriterion).where(CFRubricCriterion.identifier == uuid.UUID(CRIT_IDENT))
        )
        criterion = result.scalar_one()
        assert criterion.category == "Quality"
        assert criterion.weight == 1.5
        assert criterion.position == 1

        # Verify level
        result = await db_session.execute(
            select(CFRubricCriterionLevel).where(CFRubricCriterionLevel.identifier == uuid.UUID(LEVEL_IDENT))
        )
        level = result.scalar_one()
        assert level.quality == "Excellent"
        assert level.score == 5.0
        assert level.feedback == "Outstanding work"

    async def test_upsert_rubric(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Re-import should update, not duplicate."""
        await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(FULL_CSV))

        # Re-import with updated title
        updated_csv = FULL_CSV.replace("Test Rubric", "Updated Rubric")
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(updated_csv))

        assert report.rubrics_updated == 1
        assert report.rubrics_created == 0

        result = await db_session.execute(select(CFRubric).where(CFRubric.identifier == uuid.UUID(RUBRIC_IDENT)))
        rubric = result.scalar_one()
        assert rubric.title == "Updated Rubric"


class TestPositionalContext:
    async def test_implicit_rubric_parent(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Criterion without explicit RubricIdentifier uses previous rubric row."""
        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,{RUBRIC_IDENT},,,My Rubric,,,,,,,,
Criterion,{CRIT_IDENT},,,,,,1.0,1,,,,
"""
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))

        assert report.rubrics_created == 1
        assert report.criteria_created == 1

        result = await db_session.execute(
            select(CFRubricCriterion).where(CFRubricCriterion.identifier == uuid.UUID(CRIT_IDENT))
        )
        criterion = result.scalar_one()
        assert criterion.rubric_id == uuid.UUID(RUBRIC_IDENT)

    async def test_implicit_criterion_parent(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Level without explicit CriterionIdentifier uses previous criterion row."""
        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,{RUBRIC_IDENT},,,My Rubric,,,,,,,,
Criterion,{CRIT_IDENT},,,,,,1.0,1,,,,
Level,{LEVEL_IDENT},,,,,,,,Good,3.0,,
"""
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))

        assert report.rubrics_created == 1
        assert report.criteria_created == 1
        assert report.levels_created == 1


class TestValidation:
    async def test_missing_type_column(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        csv_data = b"Identifier,Title\nabc,Test\n"
        with pytest.raises(ValueError, match="'Type' column"):
            await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), csv_data)

    async def test_document_not_found(self, db_session: AsyncSession, tenant: Tenant):
        with pytest.raises(ValueError, match="Document not found"):
            await import_rubric_csv(db_session, tenant.id, uuid.uuid4(), _csv_bytes(FULL_CSV))

    async def test_skip_invalid_rubric_uuid(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        csv_data = b"Type,Identifier,RubricIdentifier,CriterionIdentifier,Title\nRubric,bad-uuid,,,,Test\n"
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), csv_data)
        assert report.rubrics_skipped == 1
        assert any("Invalid Rubric Identifier" in w for w in report.warnings)

    async def test_skip_criterion_no_parent(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Criterion without any rubric context should be skipped."""
        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title
Criterion,{CRIT_IDENT},,,
"""
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))
        assert report.criteria_skipped == 1
        assert any("no parent rubric" in w for w in report.warnings)

    async def test_skip_level_no_parent(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Level without any criterion context should be skipped."""
        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title
Level,{LEVEL_IDENT},,,
"""
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))
        assert report.levels_skipped == 1
        assert any("no parent criterion" in w for w in report.warnings)

    async def test_unknown_type_warning(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        csv_data = b"Type,Identifier\nFoo,abc\n"
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), csv_data)
        assert any("Unknown type" in w for w in report.warnings)

    async def test_auto_generate_uuid(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Empty Identifier should auto-generate UUID."""
        csv_data = b"Type,Identifier,RubricIdentifier,CriterionIdentifier,Title\nRubric,,,,Auto Rubric\n"
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), csv_data)
        assert report.rubrics_created == 1

    async def test_empty_csv(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), b"")
        assert report.rubrics_created == 0


class TestCFItemResolution:
    async def test_cf_item_fk_resolved(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        item_ident = "aabbcc05-0000-0000-0000-000000000001"
        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=doc.id,
            identifier=uuid.UUID(item_ident),
            uri="https://example.com/uri/item1",
            full_statement="Test Item",
            last_change_date_time=LCT,
        )
        db_session.add(item)
        await db_session.flush()

        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,{RUBRIC_IDENT},,,Test Rubric,,,,,,,,
Criterion,{CRIT_IDENT},{RUBRIC_IDENT},,,,Quality,1.0,1,,,,{item_ident}
"""
        await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))

        result = await db_session.execute(
            select(CFRubricCriterion).where(CFRubricCriterion.identifier == uuid.UUID(CRIT_IDENT))
        )
        criterion = result.scalar_one()
        assert criterion.cf_item_id is not None

    async def test_cf_item_not_found_warning(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        csv_data = f"""\
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,{RUBRIC_IDENT},,,Test Rubric,,,,,,,,
Criterion,{CRIT_IDENT},{RUBRIC_IDENT},,,,,,,,,,ffff0000-0000-0000-0000-000000000099
"""
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), _csv_bytes(csv_data))
        assert any("CFItemIdentifier" in w and "not found" in w for w in report.warnings)


class TestRoundTrip:
    async def test_export_then_import(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        """Export rubrics, then re-import the CSV — data should match."""
        from src.services.csv_rubric_export_service import export_rubric_csv

        # Create rubric
        rubric = CFRubric(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=doc.id,
            identifier=uuid.UUID(RUBRIC_IDENT),
            uri=f"https://example.com/uri/{RUBRIC_IDENT}",
            title="Round Trip Rubric",
            description="Testing round trip",
            last_change_date_time=LCT,
        )
        db_session.add(rubric)
        await db_session.flush()

        criterion = CFRubricCriterion(
            id=uuid.uuid4(),
            cf_rubric_id=rubric.id,
            identifier=uuid.UUID(CRIT_IDENT),
            uri=f"https://example.com/uri/{CRIT_IDENT}",
            rubric_id=rubric.identifier,
            category="Content",
            weight=0.5,
            position=1,
            last_change_date_time=LCT,
        )
        db_session.add(criterion)
        await db_session.flush()

        level = CFRubricCriterionLevel(
            id=uuid.uuid4(),
            cf_rubric_criterion_id=criterion.id,
            rubric_criterion_id=criterion.identifier,
            identifier=uuid.UUID(LEVEL_IDENT),
            uri=f"https://example.com/uri/{LEVEL_IDENT}",
            quality="High",
            score=5.0,
            position=1,
            last_change_date_time=LCT,
        )
        db_session.add(level)
        await db_session.flush()

        # Export
        csv_str, r, c, lv = await export_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER))
        assert r == 1
        assert c == 1
        assert lv == 1

        # Re-import (should update, not create)
        report = await import_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER), csv_str.encode("utf-8"))
        assert report.rubrics_updated == 1
        assert report.rubrics_created == 0
        assert report.criteria_updated == 1
        assert report.levels_updated == 1
