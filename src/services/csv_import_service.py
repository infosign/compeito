"""CSV Import Service — supports custom, OpenSALT, and simple formats.

See docs/csv-format.md and docs/import-logic.md for the full specification.
"""
from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_subject import CFSubject


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ImportReport:
    document_title: str = ""
    document_identifier: str = ""
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    associations_created: int = 0
    existing_is_child_of_deleted: int = 0
    item_types_created: int = 0
    item_types_existing: int = 0
    licenses_created: int = 0
    licenses_existing: int = 0
    subjects_created: int = 0
    subjects_existing: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedRow:
    """Internal representation of one parsed CSV row."""
    row_number: int
    identifier: uuid.UUID | None  # None = auto-generate
    full_statement: str
    human_coding_scheme: str | None = None
    parent_identifier: str | None = None  # UUID string or None
    sequence_number: int | None = None
    cf_item_type: str | None = None
    education_level: list[str] | None = None
    concept_keywords: list[str] | None = None
    abbreviated_statement: str | None = None
    language: str | None = None
    list_enumeration: str | None = None
    license: str | None = None
    status_start_date: date | None = None
    status_end_date: date | None = None
    depth: int = 0  # simple format only

    # Track which fields had non-empty raw values (for upsert empty-cell logic)
    _present_fields: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class FormatType:
    CUSTOM = "custom"
    OPENSALT = "opensalt"
    SIMPLE = "simple"


def _detect_format(header_columns: list[str]) -> str:
    lower = [c.lower().strip() for c in header_columns]
    if "identifier" in lower and "fullstatement" in lower:
        return FormatType.CUSTOM
    if "case item identifier" in lower or "full statement" in lower:
        return FormatType.OPENSALT
    return FormatType.SIMPLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_UUID_LEN = {32, 36}  # without/with hyphens


def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


def _parse_uuid(s: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(s)
    except (ValueError, AttributeError):
        return None


def _parse_date(s: str) -> date | None:
    """Parse YYYY-MM-DD date, returns None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_int(s: str) -> int | None:
    """Parse integer within PostgreSQL INTEGER range."""
    try:
        val = int(s)
    except (ValueError, TypeError):
        return None
    if val < -2147483648 or val > 2147483647:
        return None
    return val


def _parse_csv_list(s: str) -> list[str]:
    """Parse comma-separated values, trim each, filter empty."""
    if not s:
        return []
    return [v.strip() for v in s.split(",") if v.strip()]


def _build_uri(tenant_id: uuid.UUID, identifier: uuid.UUID) -> str:
    return f"{settings.base_url}/{tenant_id}/uri/{identifier}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _simple_depth_from_indent(text: str) -> int:
    """Calculate depth from leading whitespace (tabs expanded to 2 spaces)."""
    expanded = ""
    for ch in text:
        if ch == "\t":
            expanded += "  "
        elif ch == " ":
            expanded += " "
        else:
            break
    return len(expanded) // 2


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

_KNOWN_META_KEYS = {
    "title", "version", "creator", "publisher", "description",
    "language", "adoption_status", "official_source_url",
    "license", "status_start_date", "status_end_date", "subject",
}


def _parse_metadata_lines(lines: list[list[str]]) -> tuple[dict[str, str], list[str], list[str]]:
    """Parse # metadata lines.

    Returns (metadata_dict, subject_list, warnings).
    subject_list is separate because it's multi-value.
    """
    meta: dict[str, str] = {}
    subjects: list[str] = []
    warnings: list[str] = []
    seen_keys: dict[str, int] = {}

    for row in lines:
        if not row or not row[0].startswith("#"):
            break
        raw_key = row[0][1:]  # remove '#'
        key = raw_key.strip().lower()

        if key not in _KNOWN_META_KEYS:
            warnings.append(f"Unknown metadata key '#{raw_key}', ignored")
            continue

        if key in seen_keys:
            warnings.append(
                f"Duplicate metadata key '#{key}', overwriting previous value"
            )
        seen_keys[key] = 1

        if key == "subject":
            # multi-value: all fields after the key
            raw_subjects = [v.strip() for v in row[1:] if v.strip()]
            subjects = raw_subjects
        else:
            # single value: second field only
            value = row[1].strip() if len(row) > 1 else ""
            meta[key] = value

    return meta, subjects, warnings


# ---------------------------------------------------------------------------
# Row parsing — Custom format
# ---------------------------------------------------------------------------

def _build_column_map(header: list[str]) -> dict[str, int]:
    """Map lowercase column names to indices."""
    return {col.strip().lower(): i for i, col in enumerate(header)}


def _get_cell(row: list[str], col_map: dict[str, int], key: str) -> str:
    idx = col_map.get(key)
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def _parse_custom_rows(
    data_rows: list[tuple[int, list[str]]],
    col_map: dict[str, int],
    warnings: list[str],
) -> list[ParsedRow]:
    """Parse rows in custom format. Returns list of ParsedRow."""
    results: list[ParsedRow] = []
    seen_identifiers: dict[str, int] = {}  # identifier -> row_number

    for row_num, row in data_rows:
        present = set()

        # fullStatement
        fs_raw = _get_cell(row, col_map, "fullstatement")
        present_fs = bool(fs_raw)
        fs = fs_raw.strip()
        if not fs:
            if present_fs:
                warnings.append(f"Row {row_num}: fullStatement is empty, skipped")
            continue

        # Identifier
        ident_raw = _get_cell(row, col_map, "identifier").strip()
        ident: uuid.UUID | None = None
        if ident_raw:
            present.add("identifier")
            if not _is_valid_uuid(ident_raw):
                warnings.append(f"Row {row_num}: Invalid Identifier '{ident_raw}', skipped")
                continue
            ident = uuid.UUID(ident_raw)
            ident_str = str(ident)
            if ident_str in seen_identifiers:
                warnings.append(
                    f"Row {row_num}: Duplicate Identifier '{ident_str}', "
                    f"overwriting Row {seen_identifiers[ident_str]}"
                )
            seen_identifiers[ident_str] = row_num

        present.add("full_statement")

        # humanCodingScheme
        hcs = _get_cell(row, col_map, "humancodingscheme").strip() or None
        if hcs is not None:
            present.add("human_coding_scheme")

        # parentIdentifier
        parent_raw = _get_cell(row, col_map, "parentidentifier").strip()
        parent_id: str | None = None
        if parent_raw:
            present.add("parent_identifier")
            if _is_valid_uuid(parent_raw):
                parent_id = str(uuid.UUID(parent_raw))
            else:
                warnings.append(
                    f"Row {row_num}: parentIdentifier '{parent_raw}' is not a valid UUID, treated as root"
                )

        # sequenceNumber
        seq_raw = _get_cell(row, col_map, "sequencenumber").strip()
        seq: int | None = None
        if seq_raw:
            present.add("sequence_number")
            seq = _parse_int(seq_raw)
            if seq is None:
                warnings.append(f"Row {row_num}: Invalid sequenceNumber '{seq_raw}', skipped")
                continue

        # CFItemType
        item_type_raw = _get_cell(row, col_map, "cfitemtype").strip() or None
        if item_type_raw is not None:
            present.add("cf_item_type")

        # educationLevel
        el_raw = _get_cell(row, col_map, "educationlevel")
        el: list[str] | None = None
        if el_raw:
            present.add("education_level")
            el = _parse_csv_list(el_raw)

        # conceptKeywords
        ck_raw = _get_cell(row, col_map, "conceptkeywords")
        ck: list[str] | None = None
        if ck_raw:
            present.add("concept_keywords")
            ck = _parse_csv_list(ck_raw)

        # abbreviatedStatement
        abst = _get_cell(row, col_map, "abbreviatedstatement").strip() or None
        if abst is not None:
            present.add("abbreviated_statement")

        # language
        lang = _get_cell(row, col_map, "language").strip() or None
        if lang is not None:
            present.add("language")
            if len(lang) > 10:
                warnings.append(f"Row {row_num}: language '{lang}' exceeds 10 characters, set to null")
                lang = None

        # listEnumeration
        le = _get_cell(row, col_map, "listenumeration").strip() or None
        if le is not None:
            present.add("list_enumeration")

        # license
        lic = _get_cell(row, col_map, "license").strip() or None
        if lic is not None:
            present.add("license")

        # statusStartDate
        ssd_raw = _get_cell(row, col_map, "statusstartdate").strip()
        ssd: date | None = None
        if ssd_raw:
            present.add("status_start_date")
            ssd = _parse_date(ssd_raw)
            if ssd is None:
                warnings.append(f"Row {row_num}: Invalid statusStartDate '{ssd_raw}', set to null")

        # statusEndDate
        sed_raw = _get_cell(row, col_map, "statusenddate").strip()
        sed: date | None = None
        if sed_raw:
            present.add("status_end_date")
            sed = _parse_date(sed_raw)
            if sed is None:
                warnings.append(f"Row {row_num}: Invalid statusEndDate '{sed_raw}', set to null")

        results.append(ParsedRow(
            row_number=row_num,
            identifier=ident,
            full_statement=fs,
            human_coding_scheme=hcs,
            parent_identifier=parent_id,
            sequence_number=seq,
            cf_item_type=item_type_raw,
            education_level=el,
            concept_keywords=ck,
            abbreviated_statement=abst,
            language=lang,
            list_enumeration=le,
            license=lic,
            status_start_date=ssd,
            status_end_date=sed,
            _present_fields=present,
        ))

    # Handle duplicate identifiers: keep last occurrence
    final: dict[str, ParsedRow] = {}
    result_list: list[ParsedRow] = []
    for pr in results:
        if pr.identifier is not None:
            ident_str = str(pr.identifier)
            if ident_str in final:
                # Remove earlier occurrence from result_list
                result_list = [r for r in result_list if r is not final[ident_str]]
            final[ident_str] = pr
        result_list.append(pr)

    return result_list


# ---------------------------------------------------------------------------
# Row parsing — OpenSALT format
# ---------------------------------------------------------------------------

def _parse_opensalt_rows(
    data_rows: list[tuple[int, list[str]]],
    col_map: dict[str, int],
    warnings: list[str],
    doc_identifier_str: str | None,
) -> list[ParsedRow]:
    """Parse rows in OpenSALT format."""
    results: list[ParsedRow] = []
    seen_identifiers: dict[str, int] = {}

    for row_num, row in data_rows:
        present = set()

        # Full Statement
        fs_raw = _get_cell(row, col_map, "full statement")
        present_fs = bool(fs_raw)
        fs = fs_raw.strip()
        if not fs:
            if present_fs:
                warnings.append(f"Row {row_num}: fullStatement is empty, skipped")
            continue

        # CASE Item Identifier
        ident_raw = _get_cell(row, col_map, "case item identifier").strip()
        ident: uuid.UUID | None = None
        if ident_raw:
            present.add("identifier")
            if not _is_valid_uuid(ident_raw):
                warnings.append(f"Row {row_num}: Invalid Identifier '{ident_raw}', skipped")
                continue
            ident = uuid.UUID(ident_raw)
            ident_str = str(ident)
            if ident_str in seen_identifiers:
                warnings.append(
                    f"Row {row_num}: Duplicate Identifier '{ident_str}', "
                    f"overwriting Row {seen_identifiers[ident_str]}"
                )
            seen_identifiers[ident_str] = row_num

        present.add("full_statement")

        # Human Coding Scheme
        hcs = _get_cell(row, col_map, "human coding scheme").strip() or None
        if hcs is not None:
            present.add("human_coding_scheme")

        # Is Child Of (= parentIdentifier)
        parent_raw = _get_cell(row, col_map, "is child of").strip()
        parent_id: str | None = None
        if parent_raw:
            present.add("parent_identifier")
            if _is_valid_uuid(parent_raw):
                parent_id = str(uuid.UUID(parent_raw))
            else:
                warnings.append(
                    f"Row {row_num}: parentIdentifier '{parent_raw}' is not a valid UUID, treated as root"
                )

        # Is Part Of — warn if differs from doc_identifier
        is_part_of = _get_cell(row, col_map, "is part of").strip()
        if is_part_of and doc_identifier_str and str(_parse_uuid(is_part_of) or is_part_of) != doc_identifier_str:
            warnings.append(
                f"Row {row_num}: Is Part Of '{is_part_of}' differs from document identifier '{doc_identifier_str}', ignored"
            )

        # Sequence Number
        seq_raw = _get_cell(row, col_map, "sequence number").strip()
        seq: int | None = None
        if seq_raw:
            present.add("sequence_number")
            seq = _parse_int(seq_raw)
            if seq is None:
                warnings.append(f"Row {row_num}: Invalid sequenceNumber '{seq_raw}', skipped")
                continue

        # CF Item Type
        item_type_raw = _get_cell(row, col_map, "cf item type").strip() or None
        if item_type_raw is not None:
            present.add("cf_item_type")

        # Education Level
        el_raw = _get_cell(row, col_map, "education level")
        el: list[str] | None = None
        if el_raw:
            present.add("education_level")
            el = _parse_csv_list(el_raw)

        # Concept Keywords
        ck_raw = _get_cell(row, col_map, "concept keywords")
        ck: list[str] | None = None
        if ck_raw:
            present.add("concept_keywords")
            ck = _parse_csv_list(ck_raw)

        # Abbreviated Statement
        abst = _get_cell(row, col_map, "abbreviated statement").strip() or None
        if abst is not None:
            present.add("abbreviated_statement")

        # Language
        lang = _get_cell(row, col_map, "language").strip() or None
        if lang is not None:
            present.add("language")
            if len(lang) > 10:
                warnings.append(f"Row {row_num}: language '{lang}' exceeds 10 characters, set to null")
                lang = None

        # License column is ignored for OpenSALT (managed at document level)

        results.append(ParsedRow(
            row_number=row_num,
            identifier=ident,
            full_statement=fs,
            human_coding_scheme=hcs,
            parent_identifier=parent_id,
            sequence_number=seq,
            cf_item_type=item_type_raw,
            education_level=el,
            concept_keywords=ck,
            abbreviated_statement=abst,
            language=lang,
            _present_fields=present,
        ))

    # Handle duplicate identifiers: keep last occurrence
    final: dict[str, ParsedRow] = {}
    result_list: list[ParsedRow] = []
    for pr in results:
        if pr.identifier is not None:
            ident_str = str(pr.identifier)
            if ident_str in final:
                result_list = [r for r in result_list if r is not final[ident_str]]
            final[ident_str] = pr
        result_list.append(pr)

    return result_list


# ---------------------------------------------------------------------------
# Row parsing — Simple format
# ---------------------------------------------------------------------------

def _parse_simple_rows(
    data_rows: list[tuple[int, list[str]]],
    warnings: list[str],
) -> list[ParsedRow]:
    """Parse rows in simple format (positional, indent-based hierarchy)."""
    results: list[ParsedRow] = []

    for row_num, row in data_rows:
        # Check if all cells empty
        if all(not cell.strip() for cell in row):
            continue

        # Column 1 = fullStatement (with indent)
        raw_fs = row[0] if row else ""

        # Calculate depth from indent BEFORE trimming
        depth = _simple_depth_from_indent(raw_fs)

        fs = raw_fs.strip()
        if not fs:
            if raw_fs:
                warnings.append(f"Row {row_num}: fullStatement is empty, skipped")
            continue

        present = {"full_statement"}

        # Column 2 = humanCodingScheme
        hcs = row[1].strip() if len(row) > 1 and row[1].strip() else None
        if hcs is not None:
            present.add("human_coding_scheme")

        # Column 3 = CFItemType
        item_type = row[2].strip() if len(row) > 2 and row[2].strip() else None
        if item_type is not None:
            present.add("cf_item_type")

        # Column 4 = educationLevel
        el_raw = row[3] if len(row) > 3 else ""
        el: list[str] | None = None
        if el_raw:
            present.add("education_level")
            el = _parse_csv_list(el_raw)

        results.append(ParsedRow(
            row_number=row_num,
            identifier=None,
            full_statement=fs,
            human_coding_scheme=hcs,
            cf_item_type=item_type,
            education_level=el,
            depth=depth,
            _present_fields=present,
        ))

    return results


# ---------------------------------------------------------------------------
# Simple format: resolve parent from indent depth
# ---------------------------------------------------------------------------

def _resolve_simple_parents(rows: list[ParsedRow], warnings: list[str]) -> None:
    """For simple format, assign parent_identifier based on depth using a stack."""
    # Stack of (depth, identifier_str)
    stack: list[tuple[int, str]] = []

    for pr in rows:
        d = pr.depth
        # Pop stack until we find a parent with lower depth
        while stack and stack[-1][0] >= d:
            stack.pop()

        if stack:
            if d - stack[-1][0] > 1:
                warnings.append(
                    f"Row {pr.row_number}: depth jumped from {stack[-1][0]} to {d}, "
                    f"treating previous item as parent"
                )
            pr.parent_identifier = stack[-1][1]

        # identifier must be assigned already (auto-generated before this step)
        if pr.identifier:
            stack.append((d, str(pr.identifier)))


# ---------------------------------------------------------------------------
# OpenSALT: scan Is Part Of
# ---------------------------------------------------------------------------

def _scan_is_part_of(
    data_rows: list[tuple[int, list[str]]],
    col_map: dict[str, int],
) -> str | None:
    """Pre-scan Is Part Of column for OpenSALT format.

    Returns the first non-empty Is Part Of value as normalized UUID string, or None.
    """
    for _row_num, row in data_rows:
        val = _get_cell(row, col_map, "is part of").strip()
        if val:
            parsed = _parse_uuid(val)
            if parsed is not None:
                return str(parsed)
            # Return raw value; caller will validate and raise error
            return val
    return None


# ---------------------------------------------------------------------------
# Lookup find-or-create
# ---------------------------------------------------------------------------

async def _find_or_create_item_type(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    now: datetime,
    report: ImportReport,
    cache: dict[str, uuid.UUID],
) -> uuid.UUID:
    """Find or create CFItemType by title. Returns internal PK (id)."""
    if title in cache:
        return cache[title]

    result = await session.execute(
        select(CFItemType)
        .where(CFItemType.tenant_id == tenant_id, CFItemType.title == title)
        .order_by(CFItemType.identifier)
    )
    existing = result.scalars().first()
    if existing:
        cache[title] = existing.id
        report.item_types_existing += 1
        return existing.id

    new_ident = uuid.uuid4()
    obj = CFItemType(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier=new_ident,
        uri=_build_uri(tenant_id, new_ident),
        title=title,
        last_change_date_time=now,
    )
    session.add(obj)
    await session.flush()
    cache[title] = obj.id
    report.item_types_created += 1
    return obj.id


async def _find_or_create_license(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    now: datetime,
    report: ImportReport,
    cache: dict[str, uuid.UUID],
) -> uuid.UUID:
    if title in cache:
        return cache[title]

    result = await session.execute(
        select(CFLicense)
        .where(CFLicense.tenant_id == tenant_id, CFLicense.title == title)
        .order_by(CFLicense.identifier)
    )
    existing = result.scalars().first()
    if existing:
        cache[title] = existing.id
        report.licenses_existing += 1
        return existing.id

    new_ident = uuid.uuid4()
    obj = CFLicense(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier=new_ident,
        uri=_build_uri(tenant_id, new_ident),
        title=title,
        last_change_date_time=now,
    )
    session.add(obj)
    await session.flush()
    cache[title] = obj.id
    report.licenses_created += 1
    return obj.id


async def _find_or_create_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    now: datetime,
    report: ImportReport,
    cache: dict[str, tuple[uuid.UUID, uuid.UUID, str]],
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Returns (id, identifier, uri)."""
    if title in cache:
        return cache[title]

    result = await session.execute(
        select(CFSubject)
        .where(CFSubject.tenant_id == tenant_id, CFSubject.title == title)
        .order_by(CFSubject.identifier)
    )
    existing = result.scalars().first()
    if existing:
        cache[title] = (existing.id, existing.identifier, existing.uri)
        report.subjects_existing += 1
        return cache[title]

    new_ident = uuid.uuid4()
    new_uri = _build_uri(tenant_id, new_ident)
    obj = CFSubject(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier=new_ident,
        uri=new_uri,
        title=title,
        last_change_date_time=now,
    )
    session.add(obj)
    await session.flush()
    cache[title] = (obj.id, obj.identifier, obj.uri)
    report.subjects_created += 1
    return cache[title]


# ---------------------------------------------------------------------------
# CFItem upsert
# ---------------------------------------------------------------------------

async def _upsert_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc: CFDocument,
    pr: ParsedRow,
    now: datetime,
    report: ImportReport,
    item_type_cache: dict[str, uuid.UUID],
    license_cache: dict[str, uuid.UUID],
) -> CFItem:
    """Upsert a CFItem. Returns the created/updated item."""
    existing: CFItem | None = None

    # Match 1: Identifier
    if pr.identifier is not None:
        result = await session.execute(
            select(CFItem).where(
                CFItem.tenant_id == tenant_id,
                CFItem.identifier == pr.identifier,
            )
        )
        existing = result.scalar_one_or_none()

    # Match 2: humanCodingScheme (same tenant + same document)
    if existing is None and pr.human_coding_scheme is not None:
        result = await session.execute(
            select(CFItem)
            .where(
                CFItem.tenant_id == tenant_id,
                CFItem.cf_document_id == doc.id,
                CFItem.human_coding_scheme == pr.human_coding_scheme,
            )
            .order_by(CFItem.identifier)
        )
        existing = result.scalars().first()

    # Resolve lookups
    item_type_id: uuid.UUID | None = None
    if pr.cf_item_type and pr.cf_item_type.strip():
        item_type_id = await _find_or_create_item_type(
            session, tenant_id, pr.cf_item_type.strip(), now, report, item_type_cache,
        )

    license_id: uuid.UUID | None = None
    if pr.license and pr.license.strip():
        license_id = await _find_or_create_license(
            session, tenant_id, pr.license.strip(), now, report, license_cache,
        )

    if existing is not None:
        # Update existing item
        if existing.cf_document_id != doc.id:
            old_doc = await session.get(CFDocument, existing.cf_document_id)
            old_doc_ident = str(old_doc.identifier) if old_doc else "unknown"
            report.warnings.append(
                f"Row {pr.row_number}: Item '{existing.identifier}' moved from "
                f"document '{old_doc_ident}' to current document"
            )
            existing.cf_document_id = doc.id

        # Update fields only if present in CSV
        if "full_statement" in pr._present_fields:
            existing.full_statement = pr.full_statement
        if "human_coding_scheme" in pr._present_fields:
            existing.human_coding_scheme = pr.human_coding_scheme
        if "education_level" in pr._present_fields:
            existing.education_level = pr.education_level
        if "concept_keywords" in pr._present_fields:
            existing.concept_keywords = pr.concept_keywords
        if "abbreviated_statement" in pr._present_fields:
            existing.abbreviated_statement = pr.abbreviated_statement
        if "language" in pr._present_fields:
            existing.language = pr.language
        if "list_enumeration" in pr._present_fields:
            existing.list_enumeration = pr.list_enumeration
        if "status_start_date" in pr._present_fields:
            existing.status_start_date = pr.status_start_date
        if "status_end_date" in pr._present_fields:
            existing.status_end_date = pr.status_end_date
        if "cf_item_type" in pr._present_fields:
            existing.cf_item_type_id = item_type_id
        if "license" in pr._present_fields:
            existing.cf_license_id = license_id
        # uri: preserve existing
        existing.last_change_date_time = now
        report.items_updated += 1
        return existing
    else:
        # Create new item
        ident = pr.identifier or uuid.uuid4()
        item = CFItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            cf_document_id=doc.id,
            identifier=ident,
            uri=_build_uri(tenant_id, ident),
            full_statement=pr.full_statement,
            human_coding_scheme=pr.human_coding_scheme,
            education_level=pr.education_level,
            concept_keywords=pr.concept_keywords,
            abbreviated_statement=pr.abbreviated_statement,
            language=pr.language if pr.language else doc.language,
            list_enumeration=pr.list_enumeration,
            cf_item_type_id=item_type_id,
            cf_license_id=license_id,
            status_start_date=pr.status_start_date,
            status_end_date=pr.status_end_date,
            depth=0,
            last_change_date_time=now,
        )
        session.add(item)
        await session.flush()
        # Assign identifier back to ParsedRow for parent resolution
        pr.identifier = ident
        report.items_created += 1
        return item


# ---------------------------------------------------------------------------
# isChildOf Association generation
# ---------------------------------------------------------------------------

def _generate_is_child_of(
    tenant_id: uuid.UUID,
    doc: CFDocument,
    items: list[CFItem],
    parsed_rows: list[ParsedRow],
    now: datetime,
    warnings: list[str],
) -> list[CFAssociation]:
    """Generate isChildOf associations from parsed rows and items."""
    # Build maps: identifier_str -> CFItem, identifier_str -> ParsedRow
    item_by_ident: dict[str, CFItem] = {str(it.identifier): it for it in items}

    # Build parent->children with sequence numbers
    associations: list[CFAssociation] = []
    auto_seq_counters: dict[str, int] = defaultdict(lambda: 0)  # parent_ident -> next_seq

    for pr, item in zip(parsed_rows, items):
        parent_ident = pr.parent_identifier
        seq = pr.sequence_number

        # Self-reference check
        if parent_ident and parent_ident == str(item.identifier):
            warnings.append(
                f"Row {pr.row_number}: parentIdentifier references self, treated as root"
            )
            parent_ident = None

        # Determine destination (parent)
        if parent_ident and parent_ident in item_by_ident:
            parent_item = item_by_ident[parent_ident]
            dest_ident = str(parent_item.identifier)
            dest_uri = parent_item.uri
            dest_title = parent_item.full_statement
        elif parent_ident:
            # Parent not found in document items
            warnings.append(
                f"Row {pr.row_number}: Parent '{parent_ident}' not found, treated as root"
            )
            dest_ident = str(doc.identifier)
            dest_uri = doc.uri
            dest_title = doc.title
        else:
            # Root level — parent is document
            dest_ident = str(doc.identifier)
            dest_uri = doc.uri
            dest_title = doc.title

        # Auto-assign sequence number if not specified
        if seq is None:
            auto_seq_counters[dest_ident] += 10
            seq = auto_seq_counters[dest_ident]
        else:
            # Track counter for this parent even with explicit values
            if auto_seq_counters[dest_ident] < seq:
                auto_seq_counters[dest_ident] = seq

        assoc_ident = uuid.uuid4()
        assoc = CFAssociation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            cf_document_id=doc.id,
            identifier=assoc_ident,
            uri=_build_uri(tenant_id, assoc_ident),
            association_type="isChildOf",
            origin_node_identifier=str(item.identifier),
            origin_node_uri=item.uri,
            origin_node_title=item.full_statement,
            origin_node_target_type=None,
            destination_node_identifier=dest_ident,
            destination_node_uri=dest_uri,
            destination_node_title=dest_title,
            destination_node_target_type=None,
            sequence_number=seq,
            last_change_date_time=now,
        )
        associations.append(assoc)

    return associations


# ---------------------------------------------------------------------------
# Depth calculation (BFS)
# ---------------------------------------------------------------------------

def _calculate_depths(
    doc: CFDocument,
    items: list[CFItem],
    associations: list[CFAssociation],
    warnings: list[str],
) -> None:
    """Calculate depth for all items using BFS on isChildOf associations."""
    doc_ident = str(doc.identifier)
    item_by_ident: dict[str, CFItem] = {str(it.identifier): it for it in items}

    # Build parent -> children map from isChildOf associations
    # isChildOf: origin=child, destination=parent
    children_of: dict[str, list[str]] = defaultdict(list)
    is_child_of_assocs = [a for a in associations if a.association_type == "isChildOf"]

    for assoc in is_child_of_assocs:
        parent = assoc.destination_node_identifier
        child = assoc.origin_node_identifier
        children_of[parent].append(child)

    # BFS from document root
    visited: set[str] = set()
    queue: list[tuple[str, int]] = []

    # Seed: children of document
    for child_ident in children_of.get(doc_ident, []):
        if child_ident in item_by_ident:
            queue.append((child_ident, 0))

    idx = 0
    while idx < len(queue):
        ident, depth = queue[idx]
        idx += 1

        if ident in visited:
            continue
        visited.add(ident)

        if ident in item_by_ident:
            item_by_ident[ident].depth = depth

        for child_ident in children_of.get(ident, []):
            if child_ident not in visited and child_ident in item_by_ident:
                queue.append((child_ident, depth + 1))

    # Handle orphan/unreachable items
    unreachable = set(item_by_ident.keys()) - visited
    if unreachable:
        # Check for circular references
        # Nodes in unreachable that have isChildOf pointing to other unreachable nodes
        cycle_nodes: set[str] = set()
        for ident in unreachable:
            item_by_ident[ident].depth = 0

        # Detect cycles among unreachable
        for assoc in is_child_of_assocs:
            child = assoc.origin_node_identifier
            parent = assoc.destination_node_identifier
            if child in unreachable and parent in unreachable:
                cycle_nodes.add(child)
                cycle_nodes.add(parent)

        if cycle_nodes:
            sorted_cycle = sorted(cycle_nodes)
            ident_list = ", ".join(f"'{i}'" for i in sorted_cycle)
            warnings.append(
                f"Circular reference detected involving items: {ident_list}, set to depth 0"
            )

        for ident in unreachable - cycle_nodes:
            warnings.append(
                f"Orphan item '{ident}' has no reachable parent, set to depth 0"
            )


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

async def import_csv(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    csv_data: bytes,
    *,
    doc_identifier: uuid.UUID | None = None,
    doc_title: str | None = None,
    doc_version: str | None = None,
) -> ImportReport:
    """Import a CSV file into the database.

    Args:
        session: Async database session (caller manages transaction).
        tenant_id: Target tenant UUID.
        csv_data: Raw CSV file bytes (UTF-8, with or without BOM).
        doc_identifier: Optional --doc parameter (existing document UUID).
        doc_title: Optional --doc-title override.
        doc_version: Optional --doc-version override.

    Returns:
        ImportReport with counts and warnings.
    """
    report = ImportReport()
    now = _now_utc()

    # Step 1: Decode and parse CSV
    try:
        text = csv_data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV file is not valid UTF-8")

    reader = csv.reader(io.StringIO(text))
    all_rows: list[list[str]] = list(reader)

    # Separate metadata lines from data
    meta_lines: list[list[str]] = []
    data_start = 0
    for i, row in enumerate(all_rows):
        if row and row[0].startswith("#"):
            meta_lines.append(row)
            data_start = i + 1
        else:
            break

    # Step 2: Parse metadata
    metadata, meta_subjects, meta_warnings = _parse_metadata_lines(meta_lines)
    report.warnings.extend(meta_warnings)

    # Validate metadata fields
    meta_language = metadata.get("language")
    if meta_language and len(meta_language) > 10:
        report.warnings.append(
            f"Metadata #language '{meta_language}' exceeds 10 characters, set to null"
        )
        meta_language = None
    elif meta_language == "":
        meta_language = None
    else:
        meta_language = metadata.get("language") or None

    meta_ssd_raw = metadata.get("status_start_date", "")
    meta_ssd: date | None = None
    if meta_ssd_raw:
        meta_ssd = _parse_date(meta_ssd_raw)
        if meta_ssd is None:
            report.warnings.append(f"Invalid #status_start_date '{meta_ssd_raw}', set to null")

    meta_sed_raw = metadata.get("status_end_date", "")
    meta_sed: date | None = None
    if meta_sed_raw:
        meta_sed = _parse_date(meta_sed_raw)
        if meta_sed is None:
            report.warnings.append(f"Invalid #status_end_date '{meta_sed_raw}', set to null")

    meta_adoption = metadata.get("adoption_status")
    if meta_adoption:
        valid_statuses = {"Draft", "Private Draft", "Adopted", "Deprecated"}
        if meta_adoption not in valid_statuses:
            report.warnings.append(f"Invalid adoption_status '{meta_adoption}', storing as-is")

    # Skip empty lines after metadata to find header/data
    remaining_rows: list[list[str]] = []
    for row in all_rows[data_start:]:
        remaining_rows.append(row)

    # Filter out truly empty rows for format detection
    non_empty_remaining = [(i, row) for i, row in enumerate(remaining_rows) if any(cell.strip() for cell in row)]

    # Determine format
    if not non_empty_remaining:
        fmt = FormatType.SIMPLE
        header: list[str] = []
        data_rows_indexed: list[tuple[int, list[str]]] = []
    else:
        first_row = non_empty_remaining[0][1]
        fmt = _detect_format(first_row)

        if fmt == FormatType.SIMPLE:
            # Simple format: no header skip, first row is data
            # Row numbers are 1-based from the original file
            data_rows_indexed = [
                (data_start + i + 1, row)
                for i, row in enumerate(remaining_rows)
                if any(cell.strip() for cell in row)
            ]
            header = []
        else:
            # Custom/OpenSALT: first non-empty row is header
            header_local_idx = non_empty_remaining[0][0]
            header = non_empty_remaining[0][1]
            # Data rows: everything after header, skip empty rows
            data_rows_indexed = []
            for i, row in enumerate(remaining_rows):
                if i <= header_local_idx:
                    continue
                if any(cell.strip() for cell in row):
                    data_rows_indexed.append((data_start + i + 1, row))

    # Step 2.5: OpenSALT Is Part Of pre-scan
    opensalt_doc_ident: str | None = None
    if fmt == FormatType.OPENSALT and header:
        col_map = _build_column_map(header)
        opensalt_doc_ident = _scan_is_part_of(data_rows_indexed, col_map)
        if opensalt_doc_ident:
            if not _is_valid_uuid(opensalt_doc_ident):
                raise ValueError(f"Is Part Of value is not a valid UUID: '{opensalt_doc_ident}'")
            opensalt_doc_ident = str(uuid.UUID(opensalt_doc_ident))

    # Step 3: CFDocument create/update
    doc: CFDocument
    is_update = False

    # Resolve title
    effective_title = doc_title or metadata.get("title") or None
    # Treat empty string as unspecified
    if effective_title is not None and not effective_title.strip():
        effective_title = None

    effective_version = doc_version or metadata.get("version") or None
    if effective_version is not None and not effective_version.strip():
        effective_version = None

    if doc_identifier is not None:
        # --doc specified: must exist
        result = await session.execute(
            select(CFDocument).where(
                CFDocument.tenant_id == tenant_id,
                CFDocument.identifier == doc_identifier,
            ).with_for_update()
        )
        doc_obj = result.scalar_one_or_none()
        if doc_obj is None:
            raise ValueError(f"Document not found: '{doc_identifier}'")
        doc = doc_obj
        is_update = True

        # Update fields from metadata
        if effective_title:
            doc.title = effective_title
        if effective_version:
            doc.version = effective_version
        if metadata.get("creator"):
            doc.creator = metadata["creator"]
        if metadata.get("publisher"):
            doc.publisher = metadata["publisher"]
        if metadata.get("description"):
            doc.description = metadata["description"]
        if meta_language:
            doc.language = meta_language
        if meta_adoption is not None and meta_adoption != "":
            doc.adoption_status = meta_adoption
        if metadata.get("official_source_url"):
            doc.official_source_url = metadata["official_source_url"]
        if meta_ssd_raw:
            doc.status_start_date = meta_ssd
        if meta_sed_raw:
            doc.status_end_date = meta_sed
        doc.last_change_date_time = now

    elif fmt == FormatType.OPENSALT and opensalt_doc_ident:
        # OpenSALT with Is Part Of
        ident_uuid = uuid.UUID(opensalt_doc_ident)
        result = await session.execute(
            select(CFDocument).where(
                CFDocument.tenant_id == tenant_id,
                CFDocument.identifier == ident_uuid,
            ).with_for_update()
        )
        doc_obj = result.scalar_one_or_none()
        if doc_obj is not None:
            doc = doc_obj
            is_update = True
            if effective_title:
                doc.title = effective_title
            if effective_version:
                doc.version = effective_version
            if metadata.get("creator"):
                doc.creator = metadata["creator"]
            if metadata.get("publisher"):
                doc.publisher = metadata["publisher"]
            if metadata.get("description"):
                doc.description = metadata["description"]
            if meta_language:
                doc.language = meta_language
            if meta_adoption is not None and meta_adoption != "":
                doc.adoption_status = meta_adoption
            if metadata.get("official_source_url"):
                doc.official_source_url = metadata["official_source_url"]
            if meta_ssd_raw:
                doc.status_start_date = meta_ssd
            if meta_sed_raw:
                doc.status_end_date = meta_sed
            doc.last_change_date_time = now
        else:
            # Create new with Is Part Of identifier
            if not effective_title:
                raise ValueError("Document title is required")
            doc = CFDocument(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                identifier=ident_uuid,
                uri=_build_uri(tenant_id, ident_uuid),
                title=effective_title,
                version=effective_version,
                creator=metadata.get("creator") or None,
                publisher=metadata.get("publisher") or None,
                description=metadata.get("description") or None,
                language=meta_language,
                adoption_status=meta_adoption if meta_adoption else None,
                official_source_url=metadata.get("official_source_url") or None,
                status_start_date=meta_ssd,
                status_end_date=meta_sed,
                last_change_date_time=now,
            )
            session.add(doc)
            await session.flush()

    else:
        # New document
        if not effective_title:
            raise ValueError("Document title is required")
        new_ident = uuid.uuid4()
        doc = CFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            identifier=new_ident,
            uri=_build_uri(tenant_id, new_ident),
            title=effective_title,
            version=effective_version,
            creator=metadata.get("creator") or None,
            publisher=metadata.get("publisher") or None,
            description=metadata.get("description") or None,
            language=meta_language,
            adoption_status=meta_adoption if meta_adoption else None,
            official_source_url=metadata.get("official_source_url") or None,
            status_start_date=meta_ssd,
            status_end_date=meta_sed,
            last_change_date_time=now,
        )
        session.add(doc)
        await session.flush()

    # Handle #license for document
    license_cache: dict[str, uuid.UUID] = {}
    meta_license = metadata.get("license", "").strip()
    if meta_license:
        doc_license_id = await _find_or_create_license(
            session, tenant_id, meta_license, now, report, license_cache,
        )
        doc.cf_license_id = doc_license_id
    elif "license" in metadata:
        # Key present but empty => clear (new) or keep (update)
        if not is_update:
            doc.cf_license_id = None

    # Handle #subject for document
    subject_cache: dict[str, tuple[uuid.UUID, uuid.UUID, str]] = {}
    if meta_subjects:
        subject_list: list[str] = []
        subject_uri_list: list[dict] = []
        for subj_title in meta_subjects:
            _id, subj_ident, subj_uri = await _find_or_create_subject(
                session, tenant_id, subj_title, now, report, subject_cache,
            )
            subject_list.append(subj_title)
            subject_uri_list.append({
                "title": subj_title,
                "identifier": str(subj_ident),
                "uri": subj_uri,
            })
        doc.subject = subject_list
        doc.subject_uri = subject_uri_list
    elif any(row and row[0].startswith("#") and row[0][1:].strip().lower() == "subject" for row in meta_lines):
        # #subject key present but no values => clear
        doc.subject = []
        doc.subject_uri = []

    report.document_title = doc.title
    report.document_identifier = str(doc.identifier)

    # Step 4: Parse data rows
    parsed_rows: list[ParsedRow]
    if fmt == FormatType.CUSTOM:
        col_map = _build_column_map(header)
        parsed_rows = _parse_custom_rows(data_rows_indexed, col_map, report.warnings)
    elif fmt == FormatType.OPENSALT:
        col_map = _build_column_map(header)
        parsed_rows = _parse_opensalt_rows(
            data_rows_indexed, col_map, report.warnings, opensalt_doc_ident,
        )
    else:
        parsed_rows = _parse_simple_rows(data_rows_indexed, report.warnings)

    # Step 5 & 6: Upsert items (lookups created inside _upsert_item)
    item_type_cache: dict[str, uuid.UUID] = {}
    upserted_items: list[CFItem] = []
    for pr in parsed_rows:
        item = await _upsert_item(
            session, tenant_id, doc, pr, now, report,
            item_type_cache, license_cache,
        )
        upserted_items.append(item)

    # For simple format: assign auto-generated identifiers and resolve parents
    if fmt == FormatType.SIMPLE:
        _resolve_simple_parents(parsed_rows, report.warnings)
        # Update parent_identifier references with actual identifiers
        # (identifiers were auto-generated in _upsert_item)

    # Step 7: isChildOf Association generation
    # Delete existing isChildOf if updating
    if is_update:
        result = await session.execute(
            select(CFAssociation).where(
                CFAssociation.cf_document_id == doc.id,
                CFAssociation.association_type == "isChildOf",
            )
        )
        existing_assocs = list(result.scalars().all())
        existing_count = len(existing_assocs)

        for assoc in existing_assocs:
            await session.delete(assoc)
        await session.flush()
        report.existing_is_child_of_deleted = existing_count

        if existing_count > 0 and len(upserted_items) == 0:
            report.warnings.append(
                f"No items processed, but {existing_count} existing isChildOf associations were deleted"
            )
    elif len(upserted_items) == 0:
        report.warnings.append("No items processed, empty document created")

    # Generate new isChildOf associations
    new_assocs = _generate_is_child_of(
        tenant_id, doc, upserted_items, parsed_rows, now, report.warnings,
    )
    for assoc in new_assocs:
        session.add(assoc)
    await session.flush()
    report.associations_created = len(new_assocs)

    # Step 8: Depth calculation
    # Get ALL isChildOf for this document (just generated ones for CSV import)
    result = await session.execute(
        select(CFAssociation).where(
            CFAssociation.cf_document_id == doc.id,
            CFAssociation.association_type == "isChildOf",
        )
    )
    all_doc_assocs = list(result.scalars().all())

    # Get ALL items in this document
    result = await session.execute(
        select(CFItem).where(CFItem.cf_document_id == doc.id)
    )
    all_doc_items = list(result.scalars().all())

    _calculate_depths(doc, all_doc_items, all_doc_assocs, report.warnings)
    await session.flush()

    return report
