"""Round-trip fidelity test: OpenCASE → compeito → re-export.

The fixture is a real CFPackage JSON exported from OpenCASE. The test:
  1. imports the fixture via compeito's CFPackage import path
     (`case_import_service.import_case_from_dict`)
  2. re-exports via the `GET /CFPackages/{id}` response builder
     (`cf_view_service.get_cf_package` → `.model_dump(by_alias=True)`)
  3. structurally diffs the two payloads and asserts no gap

Perfect round-trip is the acceptance criterion for OpenCASE interop: any
field present in OpenCASE's output must survive compeito's import → export
unchanged, so that "OpenCASE → compeito → OpenCASE" reproduces the original
framework 100%.

The test is currently expected to fail; each failure is a discrete gap to
close in a follow-up PR. Pytest's xfail prints the diff so the gap list is
visible in CI output.

Diff normalization (these are NOT considered round-trip violations):
- list-of-dicts sorted by `identifier` (order differences ignored)
- `null` values treated as missing keys (CASE v1.1 allows either form;
  compeito emits null per FR-2.10, OpenCASE omits)
- empty lists treated as missing keys (CASE v1.1 allows either form;
  compeito follows FR-2.3 — omits empty CFDefinitions sub-arrays; OpenCASE
  emits them as `[]`)
- `lastChangeDateTime` ignored (compeito stamps it at import time;
  preserving the source timestamp is tracked separately under FR-7.2 work)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant
from src.services import case_import_service, cf_view_service

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "opencase_round_trip_baseline.json"

# Resource keys at the top of a CFPackage payload. CFDocument is a single
# object; the rest are arrays of dicts.
_LIST_RESOURCE_KEYS = ("CFItems", "CFAssociations", "CFRubrics")
_DEFINITIONS_LIST_KEYS = (
    "CFItemTypes",
    "CFSubjects",
    "CFConcepts",
    "CFLicenses",
    "CFAssociationGroupings",
)

# Fields we deliberately exclude from the comparison (see module docstring).
_IGNORED_FIELDS = {"lastChangeDateTime"}


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _normalize(node):
    """Recursively normalize a payload for comparison.

    - Dict: drop `_IGNORED_FIELDS` and drop keys whose value is None (treat
      null and missing as equivalent — CASE v1.1 allows either form).
    - List of dicts whose first element has an `identifier` key: sort by it.
    - Otherwise pass through.
    """
    if isinstance(node, dict):
        return {k: _normalize(v) for k, v in node.items() if k not in _IGNORED_FIELDS and v is not None and v != []}
    if isinstance(node, list):
        if node and isinstance(node[0], dict) and "identifier" in node[0]:
            return sorted(
                (_normalize(item) for item in node),
                key=lambda d: str(d.get("identifier", "")),
            )
        return [_normalize(item) for item in node]
    return node


def _diff(path: str, expected, actual, out: list[str]) -> None:
    """Append a human-readable diff line per mismatch. Recursive."""
    if type(expected) is not type(actual):
        out.append(f"{path}: type {type(expected).__name__} → {type(actual).__name__}")
        return
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            sub_path = f"{path}.{key}" if path else key
            if key not in actual:
                out.append(f"{sub_path}: missing in actual (expected {expected[key]!r})")
            elif key not in expected:
                out.append(f"{sub_path}: unexpected in actual ({actual[key]!r})")
            else:
                _diff(sub_path, expected[key], actual[key], out)
        return
    if isinstance(expected, list):
        if len(expected) != len(actual):
            out.append(f"{path}: list length {len(expected)} → {len(actual)}")
            return
        for i, (e, a) in enumerate(zip(expected, actual)):
            _diff(f"{path}[{i}]", e, a, out)
        return
    if expected != actual:
        out.append(f"{path}: {expected!r} → {actual!r}")


def _format_diffs(diffs: list[str], limit: int = 50) -> str:
    if not diffs:
        return "(no diffs)"
    shown = diffs[:limit]
    suffix = f"\n... and {len(diffs) - limit} more" if len(diffs) > limit else ""
    return "\n".join(shown) + suffix


class TestOpenCaseRoundTrip:
    @pytest.mark.xfail(
        reason="Baseline: known round-trip gaps catalogued in "
        "docs/dev/round_trip_status.md. Each category is a follow-up PR; "
        "flip to strict pass once all are closed.",
        strict=False,
    )
    async def test_lossless(self, db_session: AsyncSession):
        fixture = _load_fixture()
        doc_ident = uuid.UUID(fixture["CFDocument"]["identifier"])

        # Fresh tenant; the fixture's own URIs already exist (its `uri` fields
        # point to OpenCASE / playground.compeito.org) so we just need any
        # tenant_id that doesn't collide.
        tenant = Tenant(id=uuid.uuid4(), name="RoundTrip", is_private=False)
        db_session.add(tenant)
        await db_session.flush()

        # Import. `source_url` matters only for v1.0 detection — this is v1.1
        # so any value is fine; pass the fixture's CFDocument.uri for realism.
        report = await case_import_service.import_case_from_dict(
            db_session,
            tenant.id,
            fixture,
            source_url=fixture["CFDocument"].get("uri", ""),
        )
        await db_session.flush()
        # Surfaced for triage in case import itself dropped resources.
        if report.warnings:
            print("\nImport warnings:")
            for w in report.warnings:
                print(f"  - {w}")

        # Re-export
        package = await cf_view_service.get_cf_package(db_session, tenant.id, doc_ident)
        assert package is not None, "CFDocument disappeared after import"
        actual = package.model_dump(by_alias=True)

        # Normalize + diff
        norm_expected = _normalize(fixture)
        norm_actual = _normalize(actual)
        diffs: list[str] = []
        _diff("", norm_expected, norm_actual, diffs)

        print(f"\n=== Round-trip diff ({len(diffs)} mismatches) ===")
        print(_format_diffs(diffs))

        assert diffs == [], f"{len(diffs)} round-trip mismatches (see test output for details)"


# Smoke checks on the fixture itself so a corrupted fixture fails loudly.


class TestFixtureSanity:
    def test_fixture_is_valid_json(self):
        _load_fixture()

    def test_fixture_has_expected_top_level(self):
        f = _load_fixture()
        assert "CFDocument" in f
        assert isinstance(f.get("CFItems"), list) and f["CFItems"]
        assert isinstance(f.get("CFAssociations"), list) and f["CFAssociations"]

    def test_fixture_has_definitions(self):
        defs = _load_fixture().get("CFDefinitions", {})
        for key in _DEFINITIONS_LIST_KEYS:
            assert isinstance(defs.get(key, []), list)
