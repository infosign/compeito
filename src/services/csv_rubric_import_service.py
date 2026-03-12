"""Rubric CSV Import Service — imports CFRubrics from CSV into DB.

See docs/csv-format.md "Rubric CSV Format" and docs/import-logic.md for specs.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel


@dataclass
class RubricImportReport:
    document_title: str = ""
    document_identifier: str = ""
    rubrics_created: int = 0
    rubrics_updated: int = 0
    rubrics_skipped: int = 0
    criteria_created: int = 0
    criteria_updated: int = 0
    criteria_skipped: int = 0
    levels_created: int = 0
    levels_updated: int = 0
    levels_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _parse_float(val: str, field_name: str, row_num: int, warnings: list[str]) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        warnings.append(f"Row {row_num}: Invalid {field_name} '{val}', set to null")
        return None


def _parse_int(val: str, field_name: str, row_num: int, warnings: list[str]) -> int | None:
    if not val or not val.strip():
        return None
    try:
        return int(float(val.strip()))
    except (ValueError, TypeError):
        warnings.append(f"Row {row_num}: Invalid {field_name} '{val}', set to null")
        return None


async def import_rubric_csv(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc_identifier: uuid.UUID,
    csv_data: bytes,
) -> RubricImportReport:
    """Import rubrics from CSV data into the database.

    Args:
        session: Async database session (caller manages transaction).
        tenant_id: Target tenant UUID.
        doc_identifier: Target document UUID (must exist).
        csv_data: Raw CSV bytes (UTF-8).

    Returns:
        RubricImportReport with counts and warnings.
    """
    report = RubricImportReport()
    now = datetime.now(timezone.utc)

    # Decode CSV
    try:
        text = csv_data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV file is not valid UTF-8")

    # Load document
    result = await session.execute(
        select(CFDocument)
        .where(
            CFDocument.tenant_id == tenant_id,
            CFDocument.identifier == doc_identifier,
        )
        .with_for_update()
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document not found: '{doc_identifier}'")

    report.document_title = doc.title
    report.document_identifier = str(doc.identifier)

    # Parse CSV
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return report

    # Find header row (skip empty rows)
    header_idx = None
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_idx = i
            break

    if header_idx is None:
        return report

    header = [c.strip().lower() for c in rows[header_idx]]

    # Validate Type column exists
    if "type" not in header:
        raise ValueError("CSV header must contain a 'Type' column")

    # Build column index
    col_idx = {name: i for i, name in enumerate(header)}

    def _get(row: list[str], col_name: str) -> str:
        idx = col_idx.get(col_name)
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip()

    # Track current context for positional parent resolution
    current_rubric_ident: str | None = None
    current_criterion_ident: str | None = None

    # Process data rows
    for row_num_offset, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not any(cell.strip() for cell in row):
            continue  # Skip empty rows

        row_type = _get(row, "type").lower()
        if not row_type:
            continue

        if row_type == "rubric":
            rubric_ident = await _process_rubric_row(
                session, tenant_id, doc, row, col_idx, _get, row_num_offset, now, report
            )
            if rubric_ident:
                current_rubric_ident = rubric_ident
                current_criterion_ident = None  # Reset criterion context

        elif row_type == "criterion":
            crit_ident = await _process_criterion_row(
                session,
                tenant_id,
                doc,
                row,
                col_idx,
                _get,
                row_num_offset,
                now,
                report,
                current_rubric_ident,
            )
            if crit_ident:
                current_criterion_ident = crit_ident

        elif row_type == "level":
            await _process_level_row(
                session,
                row,
                col_idx,
                _get,
                row_num_offset,
                now,
                report,
                current_criterion_ident,
            )

        else:
            report.warnings.append(f"Row {row_num_offset}: Unknown type '{row_type}', skipped")

    await session.flush()
    return report


async def _process_rubric_row(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc: CFDocument,
    row: list[str],
    col_idx: dict,
    _get,
    row_num: int,
    now: datetime,
    report: RubricImportReport,
) -> str | None:
    """Process a Rubric row. Returns the rubric identifier string, or None if skipped."""
    ident_str = _get(row, "identifier")

    # Auto-generate if empty
    if not ident_str:
        ident_str = str(uuid.uuid4())

    if not _is_valid_uuid(ident_str):
        report.rubrics_skipped += 1
        report.warnings.append(f"Row {row_num}: Invalid Rubric Identifier '{ident_str}', skipped")
        return None

    ident_uuid = uuid.UUID(ident_str)
    title = _get(row, "title") or None
    description = _get(row, "description") or None

    # Upsert
    result = await session.execute(
        select(CFRubric).where(
            CFRubric.tenant_id == tenant_id,
            CFRubric.identifier == ident_uuid,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.cf_document_id = doc.id
        if title is not None:
            existing.title = title
        if description is not None:
            existing.description = description
        existing.last_change_date_time = now
        report.rubrics_updated += 1
    else:
        rubric = CFRubric(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            cf_document_id=doc.id,
            identifier=ident_uuid,
            uri=f"{settings.base_url}/{tenant_id}/uri/{ident_uuid}",
            title=title,
            description=description,
            last_change_date_time=now,
        )
        session.add(rubric)
        report.rubrics_created += 1

    await session.flush()
    return ident_str


async def _process_criterion_row(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc: CFDocument,
    row: list[str],
    col_idx: dict,
    _get,
    row_num: int,
    now: datetime,
    report: RubricImportReport,
    current_rubric_ident: str | None,
) -> str | None:
    """Process a Criterion row. Returns the criterion identifier string, or None if skipped."""
    ident_str = _get(row, "identifier")

    if not ident_str:
        ident_str = str(uuid.uuid4())

    if not _is_valid_uuid(ident_str):
        report.criteria_skipped += 1
        report.warnings.append(f"Row {row_num}: Invalid Criterion Identifier '{ident_str}', skipped")
        return None

    # Resolve parent rubric
    rubric_ident_str = _get(row, "rubricidentifier") or current_rubric_ident
    if not rubric_ident_str:
        report.criteria_skipped += 1
        report.warnings.append(f"Row {row_num}: Criterion has no parent rubric, skipped")
        return None

    if not _is_valid_uuid(rubric_ident_str):
        report.criteria_skipped += 1
        report.warnings.append(f"Row {row_num}: Invalid RubricIdentifier '{rubric_ident_str}', skipped")
        return None

    # Find rubric in DB
    rubric_uuid = uuid.UUID(rubric_ident_str)
    result = await session.execute(
        select(CFRubric).where(
            CFRubric.tenant_id == tenant_id,
            CFRubric.identifier == rubric_uuid,
        )
    )
    rubric = result.scalar_one_or_none()
    if rubric is None:
        report.criteria_skipped += 1
        report.warnings.append(f"Row {row_num}: RubricIdentifier '{rubric_ident_str}' not found, skipped")
        return None

    crit_ident_uuid = uuid.UUID(ident_str)
    description = _get(row, "description") or None
    category = _get(row, "category") or None
    weight = _parse_float(_get(row, "weight"), "weight", row_num, report.warnings)
    position = _parse_int(_get(row, "position"), "position", row_num, report.warnings)

    # Resolve CFItemIdentifier FK
    cf_item_id: uuid.UUID | None = None
    cf_item_ident_str = _get(row, "cfitemidentifier")
    if cf_item_ident_str:
        if _is_valid_uuid(cf_item_ident_str):
            result = await session.execute(
                select(CFItem.id).where(
                    CFItem.tenant_id == tenant_id,
                    CFItem.identifier == uuid.UUID(cf_item_ident_str),
                )
            )
            cf_item_id = result.scalar_one_or_none()
            if cf_item_id is None:
                report.warnings.append(f"Row {row_num}: CFItemIdentifier '{cf_item_ident_str}' not found, set to null")
        else:
            report.warnings.append(f"Row {row_num}: Invalid CFItemIdentifier '{cf_item_ident_str}', set to null")

    # Upsert
    result = await session.execute(
        select(CFRubricCriterion).where(
            CFRubricCriterion.identifier == crit_ident_uuid,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.cf_rubric_id = rubric.id
        if description is not None:
            existing.description = description
        if category is not None:
            existing.category = category
        if weight is not None:
            existing.weight = weight
        if position is not None:
            existing.position = position
        if cf_item_ident_str:
            existing.cf_item_id = cf_item_id
        existing.rubric_id = rubric.identifier
        existing.last_change_date_time = now
        report.criteria_updated += 1
    else:
        criterion = CFRubricCriterion(
            id=uuid.uuid4(),
            cf_rubric_id=rubric.id,
            identifier=crit_ident_uuid,
            uri=f"{settings.base_url}/{tenant_id}/uri/{crit_ident_uuid}",
            cf_item_id=cf_item_id,
            rubric_id=rubric.identifier,
            category=category,
            description=description,
            weight=weight,
            position=position,
            last_change_date_time=now,
        )
        session.add(criterion)
        report.criteria_created += 1

    await session.flush()
    return ident_str


async def _process_level_row(
    session: AsyncSession,
    row: list[str],
    col_idx: dict,
    _get,
    row_num: int,
    now: datetime,
    report: RubricImportReport,
    current_criterion_ident: str | None,
) -> None:
    """Process a Level row."""
    ident_str = _get(row, "identifier")

    if not ident_str:
        ident_str = str(uuid.uuid4())

    if not _is_valid_uuid(ident_str):
        report.levels_skipped += 1
        report.warnings.append(f"Row {row_num}: Invalid Level Identifier '{ident_str}', skipped")
        return

    # Resolve parent criterion
    crit_ident_str = _get(row, "criterionidentifier") or current_criterion_ident
    if not crit_ident_str:
        report.levels_skipped += 1
        report.warnings.append(f"Row {row_num}: Level has no parent criterion, skipped")
        return

    if not _is_valid_uuid(crit_ident_str):
        report.levels_skipped += 1
        report.warnings.append(f"Row {row_num}: Invalid CriterionIdentifier '{crit_ident_str}', skipped")
        return

    # Find criterion in DB
    crit_uuid = uuid.UUID(crit_ident_str)
    result = await session.execute(
        select(CFRubricCriterion).where(
            CFRubricCriterion.identifier == crit_uuid,
        )
    )
    criterion = result.scalar_one_or_none()
    if criterion is None:
        report.levels_skipped += 1
        report.warnings.append(f"Row {row_num}: CriterionIdentifier '{crit_ident_str}' not found, skipped")
        return

    level_ident_uuid = uuid.UUID(ident_str)
    description = _get(row, "description") or None
    quality = _get(row, "quality") or None
    score = _parse_float(_get(row, "score"), "score", row_num, report.warnings)
    feedback = _get(row, "feedback") or None
    position = _parse_int(_get(row, "position"), "position", row_num, report.warnings)

    # Upsert
    result = await session.execute(
        select(CFRubricCriterionLevel).where(
            CFRubricCriterionLevel.identifier == level_ident_uuid,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.cf_rubric_criterion_id = criterion.id
        if description is not None:
            existing.description = description
        if quality is not None:
            existing.quality = quality
        if score is not None:
            existing.score = score
        if feedback is not None:
            existing.feedback = feedback
        if position is not None:
            existing.position = position
        existing.rubric_criterion_id = criterion.identifier
        existing.last_change_date_time = now
        report.levels_updated += 1
    else:
        level = CFRubricCriterionLevel(
            id=uuid.uuid4(),
            cf_rubric_criterion_id=criterion.id,
            rubric_criterion_id=criterion.identifier,
            identifier=level_ident_uuid,
            uri=f"urn:csv-import:{level_ident_uuid}",
            description=description,
            quality=quality,
            score=score,
            feedback=feedback,
            position=position,
            last_change_date_time=now,
        )
        session.add(level)
        report.levels_created += 1

    await session.flush()
