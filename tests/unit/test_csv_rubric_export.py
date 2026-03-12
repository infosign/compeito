"""Unit tests for rubric CSV export service."""

import csv
import io
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
from src.models.tenant import Tenant
from src.services.csv_rubric_export_service import RUBRIC_CSV_HEADER, export_rubric_csv

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


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


@pytest.fixture
async def rubric_with_data(db_session: AsyncSession, tenant: Tenant, doc: CFDocument) -> CFRubric:
    """Create rubric with criterion (linked to item) and level."""
    rubric = CFRubric(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.UUID("aabbcc01-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/rubric1",
        title="Writing Rubric",
        description="Evaluates writing skills",
        last_change_date_time=LCT,
    )
    db_session.add(rubric)
    await db_session.flush()

    item = CFItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=doc.id,
        identifier=uuid.UUID("aabbcc05-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/item1",
        full_statement="Referenced Item",
        last_change_date_time=LCT,
    )
    db_session.add(item)
    await db_session.flush()

    criterion = CFRubricCriterion(
        id=uuid.uuid4(),
        cf_rubric_id=rubric.id,
        identifier=uuid.UUID("aabbcc02-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/crit1",
        cf_item_id=item.id,
        rubric_id=rubric.identifier,
        category="Organization",
        description="Structure and flow",
        weight=0.3,
        position=1,
        last_change_date_time=LCT,
    )
    db_session.add(criterion)
    await db_session.flush()

    level1 = CFRubricCriterionLevel(
        id=uuid.uuid4(),
        cf_rubric_criterion_id=criterion.id,
        rubric_criterion_id=criterion.identifier,
        identifier=uuid.UUID("aabbcc03-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/level1",
        description="Well organized",
        quality="Excellent",
        score=4.0,
        feedback="Great structure",
        position=1,
        last_change_date_time=LCT,
    )
    level2 = CFRubricCriterionLevel(
        id=uuid.uuid4(),
        cf_rubric_criterion_id=criterion.id,
        rubric_criterion_id=criterion.identifier,
        identifier=uuid.UUID("aabbcc04-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/level2",
        description="Mostly organized",
        quality="Good",
        score=3.0,
        feedback="Room for improvement",
        position=2,
        last_change_date_time=LCT,
    )
    db_session.add_all([level1, level2])
    await db_session.flush()

    return rubric


class TestExportRubricCSV:
    async def test_export_empty(self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument):
        csv_str, r, c, lv = await export_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER))
        assert r == 0
        assert c == 0
        assert lv == 0
        # Should have header only
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 1
        assert rows[0] == RUBRIC_CSV_HEADER

    async def test_export_with_data(
        self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument, rubric_with_data: CFRubric
    ):
        csv_str, r, c, lv = await export_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER))
        assert r == 1
        assert c == 1
        assert lv == 2

        rows = list(csv.reader(io.StringIO(csv_str)))
        # Header + 1 rubric + 1 criterion + 2 levels = 5 rows
        assert len(rows) == 5

        # Header
        assert rows[0] == RUBRIC_CSV_HEADER

        # Rubric row
        assert rows[1][0] == "Rubric"
        assert rows[1][1] == "aabbcc01-0000-0000-0000-000000000001"
        assert rows[1][4] == "Writing Rubric"
        assert rows[1][5] == "Evaluates writing skills"

        # Criterion row
        assert rows[2][0] == "Criterion"
        assert rows[2][1] == "aabbcc02-0000-0000-0000-000000000001"
        assert rows[2][2] == "aabbcc01-0000-0000-0000-000000000001"  # RubricIdentifier
        assert rows[2][6] == "Organization"
        assert rows[2][7] == "0.3"
        assert rows[2][12] == "aabbcc05-0000-0000-0000-000000000001"  # CFItemIdentifier

        # Level rows (sorted by position)
        assert rows[3][0] == "Level"
        assert rows[3][9] == "Excellent"
        assert rows[3][10] == "4.0"
        assert rows[4][0] == "Level"
        assert rows[4][9] == "Good"
        assert rows[4][10] == "3.0"

    async def test_document_not_found(self, db_session: AsyncSession, tenant: Tenant):
        with pytest.raises(ValueError, match="Document not found"):
            await export_rubric_csv(db_session, tenant.id, uuid.uuid4())

    async def test_csv_encoding(
        self, db_session: AsyncSession, tenant: Tenant, doc: CFDocument, rubric_with_data: CFRubric
    ):
        """CSV should use LF line endings, no BOM."""
        csv_str, _, _, _ = await export_rubric_csv(db_session, tenant.id, uuid.UUID(DOC_IDENTIFIER))
        assert "\r\n" not in csv_str
        assert not csv_str.startswith("\ufeff")
