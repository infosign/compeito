"""External CASE source import service — fetches CFPackage JSON and saves to DB.

See docs/import-logic.md "外部CASEソースインポート" section for the full specification.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timezone

import httpx
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
from src.services.csv_import_service import _calculate_depths


# ---------------------------------------------------------------------------
# Import report
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class CaseImportReport:
    document_title: str = ""
    document_identifier: str = ""
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    associations_created: int = 0
    associations_updated: int = 0
    associations_skipped: int = 0
    item_types_created: int = 0
    item_types_updated: int = 0
    item_types_existing: int = 0
    item_types_skipped: int = 0
    subjects_created: int = 0
    subjects_updated: int = 0
    subjects_existing: int = 0
    subjects_skipped: int = 0
    concepts_created: int = 0
    concepts_updated: int = 0
    concepts_existing: int = 0
    concepts_skipped: int = 0
    licenses_created: int = 0
    licenses_updated: int = 0
    licenses_existing: int = 0
    licenses_skipped: int = 0
    groupings_created: int = 0
    groupings_updated: int = 0
    groupings_existing: int = 0
    groupings_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ASSOCIATION_TYPES = {
    "isChildOf", "isPeerOf", "isPartOf", "exactMatchOf",
    "precedes", "isRelatedTo", "replacedBy", "exemplar",
    "hasSkillLevel", "isTranslationOf",
}

HTTP_TIMEOUT = 30.0
MAX_REDIRECTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(val: str | None, now: datetime) -> datetime:
    """Parse ISO 8601 datetime. Returns now on failure or None."""
    if not val:
        return now
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return now


def _parse_datetime_with_warning(
    val: str | None, now: datetime, context: str, warnings: list[str],
) -> datetime:
    if not val:
        return now
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        warnings.append(f"{context}: Invalid lastChangeDateTime '{val}', using current timestamp")
        return now


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_date_with_warning(
    val: str | None, field_name: str, context: str, warnings: list[str],
) -> date | None:
    if not val:
        return None
    d = _parse_date(val)
    if d is None:
        warnings.append(f"{context}: Invalid {field_name} '{val}', set to null")
    return d


def _parse_sequence_number(
    val, context: str, warnings: list[str],
) -> int | None:
    """Parse sequence number from external data (may be int, float, or string)."""
    if val is None:
        return None
    try:
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                warnings.append(f"{context}: Invalid sequenceNumber '{val}', set to null")
                return None
            int_val = int(val)  # truncate float
        elif isinstance(val, int) and not isinstance(val, bool):
            int_val = val
        else:
            int_val = int(float(str(val)))
    except (ValueError, TypeError):
        warnings.append(f"{context}: Invalid sequenceNumber '{val}', set to null")
        return None

    if int_val < -2147483648 or int_val > 2147483647:
        warnings.append(f"{context}: sequenceNumber '{val}' out of range, set to null")
        return None
    return int_val


def _validate_language(
    val: str | None, context: str, warnings: list[str],
) -> str | None:
    if not val:
        return val
    if len(val) > 10:
        warnings.append(f"{context}: language '{val}' exceeds 10 characters, set to null")
        return None
    return val


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    """Fetch JSON from URL with error handling per spec."""
    try:
        response = await client.get(url)
    except httpx.ConnectError:
        raise ValueError(f"Failed to connect to remote server: {url}")
    except httpx.TimeoutException:
        raise ValueError(f"Request timed out: {url}")
    except httpx.HTTPError as e:
        if "SSL" in str(e) or "ssl" in str(e) or "certificate" in str(e).lower():
            raise ValueError("SSL certificate verification failed")
        raise ValueError(f"HTTP error fetching {url}: {e}")

    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError(f"Remote server returned HTTP {response.status_code}: {url}")

    try:
        return response.json()
    except Exception:
        raise ValueError("Response is not valid JSON")


async def fetch_cf_package(url: str) -> tuple[dict, list[str]]:
    """Fetch CFPackage JSON from remote CASE API.

    Args:
        url: Either a direct CFPackage URL or a CASE API base URL.

    Returns:
        (cfpackage_dict, warnings) — the CFPackage JSON and any warnings.
    """
    warnings: list[str] = []

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
    ) as client:
        if "/CFPackages/" in url:
            # Direct CFPackage URL
            data = await _fetch_json(client, url)
        else:
            # Base URL — need to discover document first
            base = url.rstrip("/")
            docs_url = f"{base}/CFDocuments"
            docs_data = await _fetch_json(client, docs_url)

            if "CFDocuments" not in docs_data or not isinstance(docs_data["CFDocuments"], list):
                raise ValueError(f"Invalid CFDocuments response: {docs_url}")

            doc_list = docs_data["CFDocuments"]
            if not doc_list:
                raise ValueError(f"No documents found on remote server: {url}")

            if len(doc_list) > 1:
                first_ident = doc_list[0].get("identifier", "unknown")
                warnings.append(
                    f"Remote server has {len(doc_list)} documents. "
                    f"Importing first document '{first_ident}'"
                )

            doc_ident = doc_list[0].get("identifier")
            if not doc_ident:
                raise ValueError("Invalid CFDocuments response: first document has no identifier")

            pkg_url = f"{base}/CFPackages/{doc_ident}"
            data = await _fetch_json(client, pkg_url)

    return data, warnings


# ---------------------------------------------------------------------------
# CFPackage validation
# ---------------------------------------------------------------------------

def _validate_cf_package(data: dict) -> dict:
    """Validate CFPackage structure. Returns the CFPackage dict.

    Raises ValueError on structural issues.
    """
    if "CFPackage" not in data:
        raise ValueError("Invalid CFPackage response: missing 'CFPackage' key")

    pkg = data["CFPackage"]
    cf_doc = pkg.get("CFDocument")
    if cf_doc is None or not isinstance(cf_doc, dict):
        raise ValueError("Invalid CFPackage response: CFDocument is missing or not an object")

    ident = cf_doc.get("identifier")
    if not ident or not _is_valid_uuid(str(ident)):
        raise ValueError(
            f"Invalid CFPackage response: CFDocument.identifier is missing or not a valid UUID"
        )

    title = cf_doc.get("title", "")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(
            "Invalid CFPackage response: CFDocument.title is missing or empty"
        )

    return pkg


# ---------------------------------------------------------------------------
# Definition upsert helpers
# ---------------------------------------------------------------------------

def _has_changes(existing, field_map: dict) -> bool:
    """Check if any field in field_map differs from existing ORM object."""
    for db_col, new_val in field_map.items():
        if new_val is not None and getattr(existing, db_col) != new_val:
            return True
    return False


async def _upsert_definition(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    model_class,
    resource_type: str,
    data: dict,
    now: datetime,
    report: CaseImportReport,
    extra_fields: dict | None = None,
) -> None:
    """Upsert a single CFDefinition resource."""
    ident_str = data.get("identifier")
    title = data.get("title")

    # Validation
    if not ident_str:
        getattr(report, f"{_def_counter_prefix(resource_type)}_skipped", None)
        _inc_skipped(report, resource_type)
        report.warnings.append(
            f"Skipped {resource_type}: missing identifier. identifier='None'"
        )
        return
    if not _is_valid_uuid(str(ident_str)):
        _inc_skipped(report, resource_type)
        report.warnings.append(
            f"Skipped {resource_type}: identifier is not a valid UUID. identifier='{ident_str}'"
        )
        return
    if not title:
        _inc_skipped(report, resource_type)
        report.warnings.append(
            f"Skipped {resource_type}: missing title. identifier='{ident_str}'"
        )
        return

    ident_uuid = uuid.UUID(str(ident_str))
    ldt = _parse_datetime_with_warning(
        data.get("lastChangeDateTime"), now,
        f"{resource_type} '{ident_str}'", report.warnings,
    )

    # Common fields
    field_map = {
        "uri": data.get("uri"),
        "title": title,
        "description": data.get("description"),
        "last_change_date_time": ldt,
    }

    # Extra model-specific fields
    if extra_fields:
        field_map.update(extra_fields)

    # Search by identifier
    result = await session.execute(
        select(model_class).where(
            model_class.tenant_id == tenant_id,
            model_class.identifier == ident_uuid,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Update only non-null fields
        changes = False
        for db_col, new_val in field_map.items():
            if new_val is not None and getattr(existing, db_col) != new_val:
                setattr(existing, db_col, new_val)
                changes = True

        if changes:
            _inc_updated(report, resource_type)
        else:
            _inc_existing(report, resource_type)
    else:
        # Create new
        kwargs = {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "identifier": ident_uuid,
        }
        for db_col, new_val in field_map.items():
            if new_val is not None:
                kwargs[db_col] = new_val
            elif db_col in ("uri", "title", "last_change_date_time"):
                # Required fields
                if db_col == "uri":
                    kwargs[db_col] = data.get("uri", "")
                elif db_col == "title":
                    kwargs[db_col] = title
                elif db_col == "last_change_date_time":
                    kwargs[db_col] = now

        # Ensure required fields
        if "uri" not in kwargs or not kwargs["uri"]:
            kwargs["uri"] = f"urn:missing:{ident_uuid}"
        if "title" not in kwargs:
            kwargs["title"] = title
        if "last_change_date_time" not in kwargs:
            kwargs["last_change_date_time"] = now

        obj = model_class(**kwargs)
        session.add(obj)
        _inc_created(report, resource_type)

    await session.flush()


def _def_counter_prefix(resource_type: str) -> str:
    mapping = {
        "CFItemType": "item_types",
        "CFSubject": "subjects",
        "CFConcept": "concepts",
        "CFLicense": "licenses",
        "CFAssociationGrouping": "groupings",
    }
    return mapping.get(resource_type, resource_type.lower())


def _inc_created(report: CaseImportReport, rt: str):
    attr = f"{_def_counter_prefix(rt)}_created"
    setattr(report, attr, getattr(report, attr) + 1)


def _inc_updated(report: CaseImportReport, rt: str):
    attr = f"{_def_counter_prefix(rt)}_updated"
    setattr(report, attr, getattr(report, attr) + 1)


def _inc_existing(report: CaseImportReport, rt: str):
    attr = f"{_def_counter_prefix(rt)}_existing"
    setattr(report, attr, getattr(report, attr) + 1)


def _inc_skipped(report: CaseImportReport, rt: str):
    attr = f"{_def_counter_prefix(rt)}_skipped"
    setattr(report, attr, getattr(report, attr) + 1)


# ---------------------------------------------------------------------------
# FK resolution helpers
# ---------------------------------------------------------------------------

async def _resolve_fk_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    model_class,
    ident_str: str | None,
) -> uuid.UUID | None:
    """Find a lookup record by identifier and return its internal PK (id)."""
    if not ident_str:
        return None
    parsed = uuid.UUID(str(ident_str)) if _is_valid_uuid(str(ident_str)) else None
    if parsed is None:
        return None
    result = await session.execute(
        select(model_class.id).where(
            model_class.tenant_id == tenant_id,
            model_class.identifier == parsed,
        )
    )
    row = result.scalar_one_or_none()
    return row


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

async def import_case_package(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    url: str,
    *,
    doc_identifier: uuid.UUID | None = None,
) -> CaseImportReport:
    """Import an external CASE v1.1 CFPackage into the database.

    Args:
        session: Async database session (caller manages transaction).
        tenant_id: Target tenant UUID.
        url: Remote CASE API URL (direct CFPackage or base URL).
        doc_identifier: Optional --doc parameter (existing document UUID).

    Returns:
        CaseImportReport with counts and warnings.
    """
    report = CaseImportReport()
    now = _now_utc()

    # Step 1: Fetch CFPackage
    data, fetch_warnings = await fetch_cf_package(url)
    report.warnings.extend(fetch_warnings)

    # Step 2: Validate
    pkg = _validate_cf_package(data)
    cf_doc_data = pkg["CFDocument"]

    # Step 3: CFDocument create/update
    ext_ident = uuid.UUID(str(cf_doc_data["identifier"]))
    is_update = False

    if doc_identifier is not None:
        # --doc specified
        result = await session.execute(
            select(CFDocument).where(
                CFDocument.tenant_id == tenant_id,
                CFDocument.identifier == doc_identifier,
            ).with_for_update()
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise ValueError(f"Document not found: '{doc_identifier}'")
        is_update = True
    else:
        # Search by external identifier
        result = await session.execute(
            select(CFDocument).where(
                CFDocument.tenant_id == tenant_id,
                CFDocument.identifier == ext_ident,
            ).with_for_update()
        )
        doc = result.scalar_one_or_none()
        if doc is not None:
            is_update = True

    if is_update:
        _update_document(doc, cf_doc_data, now, report)
    else:
        doc = _create_document(tenant_id, cf_doc_data, now, report)
        session.add(doc)
        await session.flush()

    # Resolve document licenseURI FK
    license_uri = cf_doc_data.get("licenseURI")
    if license_uri and isinstance(license_uri, dict):
        lic_ident = license_uri.get("identifier")
        if lic_ident:
            fk = await _resolve_fk_by_identifier(session, tenant_id, CFLicense, lic_ident)
            if fk is not None:
                doc.cf_license_id = fk
            else:
                report.warnings.append(
                    f"CFDocument '{ext_ident}': CFLicense '{lic_ident}' not found, set to null"
                )
                if not is_update:
                    doc.cf_license_id = None

    report.document_title = doc.title
    report.document_identifier = str(doc.identifier)

    # Step 4: CFDefinitions
    cf_defs = pkg.get("CFDefinitions", {}) or {}
    await _import_definitions(session, tenant_id, cf_defs, now, report)
    await session.flush()

    # Re-resolve document licenseURI FK (definitions may have been created)
    if license_uri and isinstance(license_uri, dict):
        lic_ident = license_uri.get("identifier")
        if lic_ident:
            fk = await _resolve_fk_by_identifier(session, tenant_id, CFLicense, lic_ident)
            if fk is not None:
                doc.cf_license_id = fk

    # Step 5: CFItems
    cf_items = pkg.get("CFItems", []) or []
    await _import_items(session, tenant_id, doc, cf_items, now, report)
    await session.flush()

    # Step 6: CFAssociations
    cf_assocs = pkg.get("CFAssociations", []) or []
    await _import_associations(session, tenant_id, doc, cf_assocs, now, report)
    await session.flush()

    # Step 7: Depth calculation
    result = await session.execute(
        select(CFAssociation).where(
            CFAssociation.cf_document_id == doc.id,
            CFAssociation.association_type == "isChildOf",
        )
    )
    all_assocs = list(result.scalars().all())

    result = await session.execute(
        select(CFItem).where(CFItem.cf_document_id == doc.id)
    )
    all_items = list(result.scalars().all())

    _calculate_depths(doc, all_items, all_assocs, report.warnings)
    await session.flush()

    return report


# ---------------------------------------------------------------------------
# CFDocument create/update
# ---------------------------------------------------------------------------

def _create_document(
    tenant_id: uuid.UUID, data: dict, now: datetime, report: CaseImportReport,
) -> CFDocument:
    ident = uuid.UUID(str(data["identifier"]))
    warnings = report.warnings

    lang = _validate_language(data.get("language"), "CFDocument", warnings)
    ssd = _parse_date_with_warning(
        data.get("statusStartDate"), "statusStartDate", "CFDocument", warnings,
    )
    sed = _parse_date_with_warning(
        data.get("statusEndDate"), "statusEndDate", "CFDocument", warnings,
    )
    ldt = _parse_datetime_with_warning(
        data.get("lastChangeDateTime"), now, "CFDocument", warnings,
    )

    return CFDocument(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier=ident,
        uri=data.get("uri", f"urn:missing:{ident}"),
        title=data["title"].strip(),
        creator=data.get("creator"),
        publisher=data.get("publisher"),
        description=data.get("description"),
        framework_type=data.get("frameworkType"),
        case_version=data.get("caseVersion"),
        language=lang,
        version=data.get("version"),
        adoption_status=data.get("adoptionStatus"),
        status_start_date=ssd,
        status_end_date=sed,
        official_source_url=data.get("officialSourceURL"),
        subject=data.get("subject"),
        subject_uri=data.get("subjectURI"),
        last_change_date_time=ldt,
    )


def _update_document(
    doc: CFDocument, data: dict, now: datetime, report: CaseImportReport,
) -> None:
    warnings = report.warnings

    # Update non-null fields (identifier and uri preserved)
    if data.get("title"):
        doc.title = data["title"].strip()
    if data.get("creator") is not None:
        doc.creator = data["creator"]
    if data.get("publisher") is not None:
        doc.publisher = data["publisher"]
    if data.get("description") is not None:
        doc.description = data["description"]
    if data.get("frameworkType") is not None:
        doc.framework_type = data["frameworkType"]
    if data.get("caseVersion") is not None:
        doc.case_version = data["caseVersion"]

    lang = data.get("language")
    if lang is not None:
        doc.language = _validate_language(lang, "CFDocument", warnings)

    if data.get("version") is not None:
        doc.version = data["version"]
    if data.get("adoptionStatus") is not None:
        doc.adoption_status = data["adoptionStatus"]

    if data.get("statusStartDate") is not None:
        doc.status_start_date = _parse_date_with_warning(
            data["statusStartDate"], "statusStartDate", "CFDocument", warnings,
        )
    if data.get("statusEndDate") is not None:
        doc.status_end_date = _parse_date_with_warning(
            data["statusEndDate"], "statusEndDate", "CFDocument", warnings,
        )

    if data.get("officialSourceURL") is not None:
        doc.official_source_url = data["officialSourceURL"]
    if data.get("subject") is not None:
        doc.subject = data["subject"]
    if data.get("subjectURI") is not None:
        doc.subject_uri = data["subjectURI"]

    ldt = _parse_datetime_with_warning(
        data.get("lastChangeDateTime"), now, "CFDocument", warnings,
    )
    doc.last_change_date_time = ldt


# ---------------------------------------------------------------------------
# CFDefinitions import
# ---------------------------------------------------------------------------

async def _import_definitions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    cf_defs: dict,
    now: datetime,
    report: CaseImportReport,
) -> None:
    # CFItemTypes
    for item in (cf_defs.get("CFItemTypes") or []):
        await _upsert_definition(
            session, tenant_id, CFItemType, "CFItemType", item, now, report,
            extra_fields={
                "type_code": item.get("typeCode"),
                "hierarchy_code": item.get("hierarchyCode"),
            },
        )

    # CFSubjects
    for item in (cf_defs.get("CFSubjects") or []):
        await _upsert_definition(
            session, tenant_id, CFSubject, "CFSubject", item, now, report,
            extra_fields={"hierarchy_code": item.get("hierarchyCode")},
        )

    # CFConcepts
    for item in (cf_defs.get("CFConcepts") or []):
        await _upsert_definition(
            session, tenant_id, CFConcept, "CFConcept", item, now, report,
            extra_fields={
                "keywords": item.get("keywords"),
                "hierarchy_code": item.get("hierarchyCode"),
            },
        )

    # CFLicenses
    for item in (cf_defs.get("CFLicenses") or []):
        await _upsert_definition(
            session, tenant_id, CFLicense, "CFLicense", item, now, report,
            extra_fields={"license_text": item.get("licenseText")},
        )

    # CFAssociationGroupings
    for item in (cf_defs.get("CFAssociationGroupings") or []):
        await _upsert_definition(
            session, tenant_id, CFAssociationGrouping, "CFAssociationGrouping",
            item, now, report,
        )


# ---------------------------------------------------------------------------
# CFItems import
# ---------------------------------------------------------------------------

async def _import_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc: CFDocument,
    items_data: list[dict],
    now: datetime,
    report: CaseImportReport,
) -> None:
    for item_data in items_data:
        ident_str = item_data.get("identifier")
        fs_raw = item_data.get("fullStatement", "")

        # Validation
        if not ident_str:
            report.items_skipped += 1
            report.warnings.append(
                f"Skipped CFItem: missing identifier. identifier='None'"
            )
            continue
        if not _is_valid_uuid(str(ident_str)):
            report.items_skipped += 1
            report.warnings.append(
                f"Skipped CFItem: identifier is not a valid UUID. identifier='{ident_str}'"
            )
            continue

        fs = str(fs_raw).strip() if fs_raw else ""
        if not fs:
            report.items_skipped += 1
            report.warnings.append(
                f"Skipped CFItem: fullStatement is empty. identifier='{ident_str}'"
            )
            continue

        ident_uuid = uuid.UUID(str(ident_str))
        ctx = f"CFItem '{ident_str}'"

        # Check for existing item (tenant-wide by identifier)
        result = await session.execute(
            select(CFItem).where(
                CFItem.tenant_id == tenant_id,
                CFItem.identifier == ident_uuid,
            )
        )
        existing = result.scalar_one_or_none()

        # Resolve FKs
        # CFItemType
        item_type_id: uuid.UUID | None = None
        item_type_uri = item_data.get("CFItemTypeURI")
        if item_type_uri and isinstance(item_type_uri, dict):
            type_ident = item_type_uri.get("identifier")
            if type_ident:
                item_type_id = await _resolve_fk_by_identifier(
                    session, tenant_id, CFItemType, type_ident,
                )
                if item_type_id is None:
                    report.warnings.append(
                        f"{ctx}: CFItemType '{type_ident}' not found, set to null"
                    )

        # CFConcept
        concept_id: uuid.UUID | None = None
        concept_uri = item_data.get("conceptKeywordsURI")
        if concept_uri and isinstance(concept_uri, dict):
            concept_ident = concept_uri.get("identifier")
            if concept_ident:
                concept_id = await _resolve_fk_by_identifier(
                    session, tenant_id, CFConcept, concept_ident,
                )
                if concept_id is None:
                    report.warnings.append(
                        f"{ctx}: CFConcept '{concept_ident}' not found, set to null"
                    )

        # CFLicense
        license_id: uuid.UUID | None = None
        license_uri = item_data.get("licenseURI")
        if license_uri and isinstance(license_uri, dict):
            lic_ident = license_uri.get("identifier")
            if lic_ident:
                license_id = await _resolve_fk_by_identifier(
                    session, tenant_id, CFLicense, lic_ident,
                )
                if license_id is None:
                    report.warnings.append(
                        f"{ctx}: CFLicense '{lic_ident}' not found, set to null"
                    )

        lang = _validate_language(item_data.get("language"), ctx, report.warnings)
        ssd = _parse_date_with_warning(
            item_data.get("statusStartDate"), "statusStartDate", ctx, report.warnings,
        )
        sed = _parse_date_with_warning(
            item_data.get("statusEndDate"), "statusEndDate", ctx, report.warnings,
        )
        ldt = _parse_datetime_with_warning(
            item_data.get("lastChangeDateTime"), now, ctx, report.warnings,
        )

        if existing is not None:
            # Update
            if existing.cf_document_id != doc.id:
                old_doc = await session.get(CFDocument, existing.cf_document_id)
                old_ident = str(old_doc.identifier) if old_doc else "unknown"
                report.warnings.append(
                    f"Item '{ident_str}' moved from document '{old_ident}' to current document"
                )
            existing.cf_document_id = doc.id
            # uri preserved
            if fs:
                existing.full_statement = fs
            if item_data.get("humanCodingScheme") is not None:
                existing.human_coding_scheme = item_data["humanCodingScheme"]
            if item_data.get("abbreviatedStatement") is not None:
                existing.abbreviated_statement = item_data["abbreviatedStatement"]
            if item_data.get("listEnumeration") is not None:
                existing.list_enumeration = item_data["listEnumeration"]
            if lang is not None:
                existing.language = lang
            if item_data.get("educationLevel") is not None:
                existing.education_level = item_data["educationLevel"]
            if item_data.get("conceptKeywords") is not None:
                existing.concept_keywords = item_data["conceptKeywords"]
            if item_data.get("subject") is not None:
                existing.subject = item_data["subject"]
            if item_data.get("subjectURI") is not None:
                existing.subject_uri = item_data["subjectURI"]
            if ssd is not None or item_data.get("statusStartDate") is not None:
                existing.status_start_date = ssd
            if sed is not None or item_data.get("statusEndDate") is not None:
                existing.status_end_date = sed
            if item_type_uri:
                existing.cf_item_type_id = item_type_id
            if concept_uri:
                existing.cf_concept_id = concept_id
            if license_uri:
                existing.cf_license_id = license_id
            existing.last_change_date_time = ldt
            report.items_updated += 1
        else:
            # Create new
            item = CFItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                cf_document_id=doc.id,
                identifier=ident_uuid,
                uri=item_data.get("uri", f"urn:missing:{ident_uuid}"),
                full_statement=fs,
                human_coding_scheme=item_data.get("humanCodingScheme"),
                abbreviated_statement=item_data.get("abbreviatedStatement"),
                list_enumeration=item_data.get("listEnumeration"),
                language=lang,
                education_level=item_data.get("educationLevel"),
                concept_keywords=item_data.get("conceptKeywords"),
                subject=item_data.get("subject"),
                subject_uri=item_data.get("subjectURI"),
                status_start_date=ssd,
                status_end_date=sed,
                cf_item_type_id=item_type_id,
                cf_concept_id=concept_id,
                cf_license_id=license_id,
                depth=0,
                last_change_date_time=ldt,
            )
            session.add(item)
            report.items_created += 1

        await session.flush()


# ---------------------------------------------------------------------------
# CFAssociations import
# ---------------------------------------------------------------------------

async def _import_associations(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc: CFDocument,
    assocs_data: list[dict],
    now: datetime,
    report: CaseImportReport,
) -> None:
    for assoc_data in assocs_data:
        ident_str = assoc_data.get("identifier")

        # Validation
        skip_reason = _validate_association(assoc_data)
        if skip_reason:
            report.associations_skipped += 1
            report.warnings.append(
                f"Skipped CFAssociation: {skip_reason}. identifier='{ident_str or 'None'}'"
            )
            continue

        ident_uuid = uuid.UUID(str(ident_str))
        ctx = f"CFAssociation '{ident_str}'"

        origin = assoc_data["originNodeURI"]
        dest = assoc_data["destinationNodeURI"]

        seq = _parse_sequence_number(
            assoc_data.get("sequenceNumber"), ctx, report.warnings,
        )
        ldt = _parse_datetime_with_warning(
            assoc_data.get("lastChangeDateTime"), now, ctx, report.warnings,
        )

        # Resolve CFAssociationGrouping FK
        grouping_id: uuid.UUID | None = None
        grouping_uri = assoc_data.get("CFAssociationGroupingURI")
        if grouping_uri and isinstance(grouping_uri, dict):
            grp_ident = grouping_uri.get("identifier")
            if grp_ident:
                grouping_id = await _resolve_fk_by_identifier(
                    session, tenant_id, CFAssociationGrouping, grp_ident,
                )
                if grouping_id is None:
                    report.warnings.append(
                        f"{ctx}: CFAssociationGrouping '{grp_ident}' not found, set to null"
                    )

        # Check existing
        result = await session.execute(
            select(CFAssociation).where(
                CFAssociation.tenant_id == tenant_id,
                CFAssociation.identifier == ident_uuid,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.cf_document_id != doc.id:
                old_doc = await session.get(CFDocument, existing.cf_document_id)
                old_ident = str(old_doc.identifier) if old_doc else "unknown"
                report.warnings.append(
                    f"CFAssociation '{ident_str}' moved from document '{old_ident}' to current document"
                )
            existing.cf_document_id = doc.id
            # uri preserved
            if assoc_data.get("associationType") is not None:
                existing.association_type = assoc_data["associationType"]
            existing.origin_node_identifier = origin.get("identifier", "")
            existing.origin_node_uri = origin.get("uri", "")
            existing.origin_node_title = origin.get("title")
            existing.origin_node_target_type = origin.get("targetType")
            existing.destination_node_identifier = dest.get("identifier", "")
            existing.destination_node_uri = dest.get("uri", "")
            existing.destination_node_title = dest.get("title")
            existing.destination_node_target_type = dest.get("targetType")
            existing.sequence_number = seq
            existing.cf_association_grouping_id = grouping_id
            existing.last_change_date_time = ldt
            report.associations_updated += 1
        else:
            assoc = CFAssociation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                cf_document_id=doc.id,
                identifier=ident_uuid,
                uri=assoc_data.get("uri", f"urn:missing:{ident_uuid}"),
                association_type=assoc_data["associationType"],
                origin_node_identifier=origin.get("identifier", ""),
                origin_node_uri=origin.get("uri", ""),
                origin_node_title=origin.get("title"),
                origin_node_target_type=origin.get("targetType"),
                destination_node_identifier=dest.get("identifier", ""),
                destination_node_uri=dest.get("uri", ""),
                destination_node_title=dest.get("title"),
                destination_node_target_type=dest.get("targetType"),
                sequence_number=seq,
                cf_association_grouping_id=grouping_id,
                last_change_date_time=ldt,
            )
            session.add(assoc)
            report.associations_created += 1

        await session.flush()


def _validate_association(data: dict) -> str | None:
    """Validate association data. Returns skip reason or None if valid."""
    ident = data.get("identifier")
    if not ident:
        return "missing identifier"
    if not _is_valid_uuid(str(ident)):
        return "identifier is not a valid UUID"

    assoc_type = data.get("associationType")
    if not assoc_type:
        return "missing associationType"
    if assoc_type not in VALID_ASSOCIATION_TYPES and not str(assoc_type).startswith("ext:"):
        return f"invalid associationType '{assoc_type}'"

    origin = data.get("originNodeURI")
    if not origin or not isinstance(origin, dict):
        return "missing originNodeURI"
    if not origin.get("identifier"):
        return "missing originNodeURI.identifier"
    if not origin.get("uri"):
        return "missing originNodeURI.uri"

    dest = data.get("destinationNodeURI")
    if not dest or not isinstance(dest, dict):
        return "missing destinationNodeURI"
    if not dest.get("identifier"):
        return "missing destinationNodeURI.identifier"
    if not dest.get("uri"):
        return "missing destinationNodeURI.uri"

    return None
