"""Structured issues for import reports (backlog B6).

Import warnings have always been English strings in a list: fine for a human
reading the CLI output, useless for anything that has to act on them. The
producer of a package needs to know *which* required field is missing on *which*
resource to go fix its source data — that is the operational half of conformance
backlog C3, where compeito deliberately does not fabricate values on output.

So a warning may also carry a `code` and a bit of context. Codes are added where
something machine-readable is needed; everything else stays a plain message and
appears in the report as `code: null`. See
docs/dev/designs/import-dry-run-and-ai-guide.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Issue codes. Keep them stable: a consumer may branch on them.
REQUIRED_FIELD_MISSING = "required_field_missing"
RESOURCE_SKIPPED = "resource_skipped"
ITEM_MOVED = "item_moved"
ASSOCIATION_MOVED = "association_moved"
LOST_ASSOCIATIONS = "lost_associations"
URI_TENANT_MISMATCH = "uri_tenant_mismatch"
LIFECYCLE_DATE_KEPT = "lifecycle_date_kept"
LIFECYCLE_DATE_CLEARED = "lifecycle_date_cleared"

KNOWN_CODES = frozenset(
    {
        REQUIRED_FIELD_MISSING,
        RESOURCE_SKIPPED,
        ITEM_MOVED,
        ASSOCIATION_MOVED,
        LOST_ASSOCIATIONS,
        URI_TENANT_MISMATCH,
        LIFECYCLE_DATE_KEPT,
        LIFECYCLE_DATE_CLEARED,
    }
)


@dataclass
class ValidationIssue:
    """One warning, optionally classified.

    `message` stays the human-readable English string the CLI has always shown,
    so nothing regresses for someone reading the terminal.
    """

    message: str
    code: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"message": self.message, "code": self.code}
        if self.context:
            out["context"] = self.context
        return out


class IssueCollector:
    """Mixin for the three import report dataclasses.

    `warnings` remains the canonical list of strings (every existing caller and
    test reads it); `issues` carries the classified subset alongside it. Keeping
    both avoids turning `warnings` into a property, which would silently swallow
    the `warnings.append(...)` calls that are spread across ~85 sites and the
    parser helpers that take a plain `list[str]`.
    """

    warnings: list[str]
    issues: list[ValidationIssue]

    def warn(self, message: str, code: str | None = None, **context: Any) -> None:
        assert code is None or code in KNOWN_CODES, f"unknown issue code: {code}"
        self.warnings.append(message)
        self.issues.append(ValidationIssue(message=message, code=code, context=context or {}))


def _counts(report: Any) -> dict[str, Any]:
    """Every int counter on the report, camelCased for the JSON consumer."""
    out: dict[str, Any] = {}
    for name, value in vars(report).items():
        if isinstance(value, int) and not isinstance(value, bool):
            head, *rest = name.split("_")
            out[head + "".join(p.title() for p in rest)] = value
    return out


def build_report_json(report: Any, *, dry_run: bool, destructive: dict[str, Any] | None = None) -> dict[str, Any]:
    """The `--report <path>` payload.

    `issues` holds what was classified; `warnings` holds every message including
    the unclassified ones, so the file is never a lossy view of the run.
    """
    classified = {i.message for i in getattr(report, "issues", [])}
    unclassified = [w for w in report.warnings if w not in classified]
    return {
        "documentTitle": report.document_title,
        "documentIdentifier": report.document_identifier,
        "dryRun": dry_run,
        "counts": _counts(report),
        "destructive": destructive or {},
        "issues": [i.to_json() for i in getattr(report, "issues", [])]
        + [ValidationIssue(message=w).to_json() for w in unclassified],
        "warnings": list(report.warnings),
    }
