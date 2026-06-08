"""Query-parameter support for the CASE listing endpoint(s): sort / orderBy /
filter / fields.

The CASE v1.1 REST/JSON binding reuses the IMS (OneRoster-style) conventions:

- ``sort`` + ``orderBy`` (asc|desc): single-field sorting.
- ``filter``: predicates ``field <op> value`` (op ∈ ``=`` ``!=`` ``>`` ``>=``
  ``<`` ``<=`` ``~``), joined by a single ``AND`` or ``OR``. String values are
  single-quoted; ``~`` is "contains" (case-insensitive).
- ``fields``: comma-separated list restricting the returned fields.

These operate on CFDocument scalar fields. sort/filter are translated to SQL so
they run BEFORE pagination; ``fields`` projects the serialized output.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import and_, or_

from src.models.cf_document import CFDocument
from src.schemas.cf_document import CFDocumentDType


class QueryParamError(Exception):
    """Raised on an invalid sort/filter/fields parameter.

    ``code_minor`` maps to an imsx_codeMinorFieldValue ("invalid_sort_field" /
    "invalid_selection_field"); ``message`` is the human-readable description.
    """

    def __init__(self, code_minor: str, message: str):
        super().__init__(message)
        self.code_minor = code_minor
        self.message = message


# CASE field name (camelCase, as in CFDocumentDType) → (ORM column, kind).
# kind drives value coercion for filter/sort: "str" | "date" | "datetime" | "uuid".
_CFDOC_FIELDS: dict[str, tuple] = {
    "identifier": (CFDocument.identifier, "uuid"),
    "uri": (CFDocument.uri, "str"),
    "title": (CFDocument.title, "str"),
    "creator": (CFDocument.creator, "str"),
    "publisher": (CFDocument.publisher, "str"),
    "description": (CFDocument.description, "str"),
    "frameworkType": (CFDocument.framework_type, "str"),
    "caseVersion": (CFDocument.case_version, "str"),
    "language": (CFDocument.language, "str"),
    "version": (CFDocument.version, "str"),
    "adoptionStatus": (CFDocument.adoption_status, "str"),
    "statusStartDate": (CFDocument.status_start_date, "date"),
    "statusEndDate": (CFDocument.status_end_date, "date"),
    "officialSourceURL": (CFDocument.official_source_url, "str"),
    "notes": (CFDocument.notes, "str"),
    "lastChangeDateTime": (CFDocument.last_change_date_time, "datetime"),
}

# Valid `fields` values = all CFDocument output keys (aliases).
_CFDOC_OUTPUT_FIELDS = {f.alias or n for n, f in CFDocumentDType.model_fields.items()}

_PREDICATE_RE = re.compile(r"^\s*([A-Za-z]+)\s*(>=|<=|!=|=|>|<|~)\s*(.+?)\s*$")


def parse_sort(sort: str | None, order_by: str | None):
    """Return an ORM order_by clause (or None for the default)."""
    if order_by is not None and order_by not in ("asc", "desc"):
        raise QueryParamError("invalid_sort_field", f"Invalid orderBy: '{order_by}'. Valid values: asc, desc")
    if not sort:
        return None
    entry = _CFDOC_FIELDS.get(sort)
    if entry is None:
        raise QueryParamError("invalid_sort_field", f"Invalid sort field: '{sort}'")
    col = entry[0]
    return col.desc() if order_by == "desc" else col.asc()


def _coerce(value: str, kind: str):
    """Coerce a filter literal to the column's type (raises QueryParamError)."""
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        value = value[1:-1]
    if kind == "uuid":
        try:
            return uuid.UUID(value)
        except ValueError:
            raise QueryParamError("invalid_selection_field", f"Invalid UUID in filter: '{value}'")
    if kind == "date":
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise QueryParamError("invalid_selection_field", f"Invalid date in filter: '{value}'")
    if kind == "datetime":
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise QueryParamError("invalid_selection_field", f"Invalid datetime in filter: '{value}'")
    return value


def _predicate(token: str):
    m = _PREDICATE_RE.match(token)
    if not m:
        raise QueryParamError("invalid_selection_field", f"Invalid filter predicate: '{token.strip()}'")
    field, op, raw = m.group(1), m.group(2), m.group(3)
    entry = _CFDOC_FIELDS.get(field)
    if entry is None:
        raise QueryParamError("invalid_selection_field", f"Invalid filter field: '{field}'")
    col, kind = entry
    if op == "~":
        # contains (case-insensitive). Only meaningful for text columns.
        if kind != "str":
            raise QueryParamError("invalid_selection_field", f"Operator '~' not supported on field '{field}'")
        return col.ilike(f"%{_coerce(raw, 'str')}%")
    val = _coerce(raw, kind)
    if op in (">", "<", ">=", "<=") and kind == "uuid":
        raise QueryParamError("invalid_selection_field", f"Operator '{op}' not supported on field '{field}'")
    return {
        "=": col == val,
        "!=": col != val,
        ">": col > val,
        ">=": col >= val,
        "<": col < val,
        "<=": col <= val,
    }[op]


def parse_filter(filter_str: str | None):
    """Translate a CASE filter expression to an ORM clause (or None)."""
    if not filter_str or not filter_str.strip():
        return None
    has_and = " AND " in filter_str
    has_or = " OR " in filter_str
    if has_and and has_or:
        raise QueryParamError("invalid_selection_field", "Mixing AND and OR in filter is not supported")
    if has_or:
        return or_(*[_predicate(t) for t in filter_str.split(" OR ")])
    if has_and:
        return and_(*[_predicate(t) for t in filter_str.split(" AND ")])
    return _predicate(filter_str)


def parse_fields(fields: str | None) -> list[str] | None:
    """Parse a comma-separated `fields` list; validate against CFDocument keys."""
    if not fields or not fields.strip():
        return None
    names = [f.strip() for f in fields.split(",") if f.strip()]
    invalid = [n for n in names if n not in _CFDOC_OUTPUT_FIELDS]
    if invalid:
        raise QueryParamError("invalid_selection_field", f"Invalid field(s): {', '.join(invalid)}")
    return names


def project_fields(dump: dict, fields: list[str] | None) -> dict:
    """Restrict a serialized CFDocument dict to the requested fields."""
    if fields is None:
        return dump
    return {k: v for k, v in dump.items() if k in fields}
