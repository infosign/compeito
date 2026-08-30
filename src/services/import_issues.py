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
    so nothing regresses for someone reading the terminal. `severity` is always
    "warning" today — import stays lenient and rejects nothing — but consumers
    should read it rather than assume, since an "error" level is the natural
    next step if that ever changes.
    """

    message: str
    code: str | None = None
    severity: str = "warning"
    context: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"message": self.message, "code": self.code, "severity": self.severity}
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
        # ValueError, not assert: the code set is an external contract and
        # `python -O` would strip an assertion.
        if code is not None and code not in KNOWN_CODES:
            raise ValueError(f"unknown issue code: {code}")
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


LOST_LINK_SAMPLE_CAP = 20


def destructive_summary(report: Any) -> dict[str, Any]:
    """What an import would take away, measured after the fact.

    Lives here rather than in the CLI because the CLI is not the only consumer:
    anything that calls the import services directly (compeito-aws's Admin API
    does) needs the same answer, and two implementations of "what counts as
    destructive" would drift apart. The transaction gate — prompting, refusing,
    committing — stays with whoever owns the transaction.

    Counted from the report the service actually produced, not from a guess made
    beforehand: the delete scope depends on which columns the header carries and
    how many rows are valid, so a pre-estimate would be a second implementation
    of the importer to keep in sync.

    Reports that cannot lose anything (rubric import) simply return zeroes.
    """
    lost = getattr(report, "lost_associations_count", 0)
    items_moved = getattr(report, "items_moved", 0)
    assocs_moved = getattr(report, "associations_moved", 0)
    return {
        "lostAssociationsCount": lost,
        "lostAssociationsSample": [
            {"associationType": a, "origin": o, "destination": d}
            for a, o, d in getattr(report, "lost_associations_sample", [])[:LOST_LINK_SAMPLE_CAP]
        ],
        # Kept apart: an item taken from another document breaks that document's
        # tree, a re-attached association does not necessarily.
        "itemsMoved": items_moved,
        "associationsMoved": assocs_moved,
        "total": lost + items_moved + assocs_moved,
    }


REPORT_VERSION = 1


def build_report_json(
    report: Any,
    *,
    dry_run: bool,
    applied: bool,
    cancelled: bool = False,
    destructive: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The `--report <path>` payload.

    `applied` is not derivable from `dryRun`: a run refused at the guard also
    writes a report, and without this flag it would be indistinguishable from a
    successful one for anything reading only the file.

    `issues` holds what was classified; `warnings` holds every message including
    the unclassified ones, so the file is never a lossy view of the run.
    """
    classified = {i.message for i in getattr(report, "issues", [])}
    unclassified = [w for w in report.warnings if w not in classified]
    return {
        "reportVersion": REPORT_VERSION,
        "documentTitle": report.document_title,
        "documentIdentifier": report.document_identifier,
        "dryRun": dry_run,
        "applied": applied,
        "cancelled": cancelled,
        "counts": _counts(report),
        "destructive": destructive or {},
        "issues": [i.to_json() for i in getattr(report, "issues", [])]
        + [ValidationIssue(message=w).to_json() for w in unclassified],
        "warnings": list(report.warnings),
    }
