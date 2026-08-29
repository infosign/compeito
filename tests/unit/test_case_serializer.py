"""Unit tests for the CASE output modes (conformance backlog C16 / C1 / C2 / C8).

Design: docs/dev/designs/strict-output.md. These build schema objects directly —
no DB — so they pin the serialization rules themselves rather than any route.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from src.errors import OutputModeConflictError
from src.schemas.cf_association import CFAssociationDType
from src.schemas.cf_document import CFDocumentDType, CFPckgDocumentDType
from src.schemas.cf_item import CFPckgItemDType
from src.schemas.cf_package import CFPackageDType
from src.services.case_serializer import (
    CASE_VERSION_EMIT,
    dump_collection,
    dump_model,
    dump_package,
    dump_single,
    resolve_output_mode,
)

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _link(title: str = "T") -> dict:
    return {"title": title, "identifier": str(uuid.uuid4()), "uri": "https://example.com/x"}


def _document(**overrides) -> CFDocumentDType:
    data = {
        "identifier": str(uuid.uuid4()),
        "uri": "https://example.com/doc",
        "title": "Doc",
        "creator": "Creator",
        "lastChangeDateTime": NOW,
        "CFPackageURI": _link(),
    }
    data.update(overrides)
    return CFDocumentDType(**data)


class TestResolveOutputMode:
    def test_default_is_compat(self):
        assert resolve_output_mode(None, None) == "compat"

    def test_config_default_can_flip(self, monkeypatch):
        """The planned major-version change has to be one setting, not a rewrite."""
        from src.config import settings

        monkeypatch.setattr(settings, "case_output_default", "strict")
        assert resolve_output_mode(None, None) == "strict"

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
    def test_truthy_spellings(self, value: str):
        assert resolve_output_mode(value, None) == "strict"

    @pytest.mark.parametrize("value", ["0", "false", "abc", ""])
    def test_non_truthy_falls_back_to_default(self, value: str):
        """A typo must not select the other mode silently."""
        assert resolve_output_mode(value, None) == "compat"

    def test_explicit_compat(self):
        assert resolve_output_mode(None, "1") == "compat"

    def test_both_is_a_conflict(self):
        with pytest.raises(OutputModeConflictError):
            resolve_output_mode("1", "1")

    def test_strict_plus_non_truthy_compat_is_strict(self):
        assert resolve_output_mode("1", "0") == "strict"


class TestDumpModel:
    def test_compat_keeps_nulls(self):
        dumped = dump_model(_document(), "compat")
        assert "notes" in dumped and dumped["notes"] is None

    def test_strict_drops_nulls(self):
        """No DType in the official schema is nullable, so an echoed null is a
        type violation, not a harmless extra."""
        dumped = dump_model(_document(), "strict")
        assert not [k for k, v in dumped.items() if v is None]
        assert "notes" not in dumped

    def test_strict_drops_serializer_produced_nulls(self):
        """Date fields go through a field_serializer; they must drop too."""
        dumped = dump_model(_document(), "strict")
        assert "statusStartDate" not in dumped
        assert "statusEndDate" not in dumped

    def test_strict_keeps_present_dates(self):
        dumped = dump_model(_document(statusEndDate=date(2026, 3, 31)), "strict")
        assert dumped["statusEndDate"] == "2026-03-31"

    def test_strict_declares_case_version(self):
        """A server declaration, not fabricated source data: compeito serves the
        v1.1 shape even for a document imported from a v1.0 source."""
        assert dump_model(_document(caseVersion="1.0"), "strict")["caseVersion"] == CASE_VERSION_EMIT
        assert dump_model(_document(), "strict")["caseVersion"] == CASE_VERSION_EMIT

    def test_compat_keeps_stored_case_version(self):
        assert dump_model(_document(caseVersion="1.0"), "compat")["caseVersion"] == "1.0"

    def test_extensions_contents_are_user_data(self):
        """exclude_none drops fields whose value is None — never dict contents."""
        doc = _document(extensions={"k": None})
        assert dump_model(doc, "strict")["extensions"] == {"k": None}

    def test_empty_extensions_survive_in_both_modes(self):
        doc = _document(extensions={})
        assert dump_model(doc, "strict")["extensions"] == {}
        assert dump_model(doc, "compat")["extensions"] == {}

    def test_strict_recurses_into_nested_models(self):
        """A nested LinkGenURIDType has its own optional fields; pydantic has to
        apply exclude_none down there too.

        (CFPackageURI is a LinkURIType and has no optional field at all, so it
        cannot show this — asserting on it would pass with or without strict.)
        """
        assoc = CFAssociationDType(
            identifier=str(uuid.uuid4()),
            uri="https://example.com/assoc",
            associationType="isChildOf",
            originNodeURI={"identifier": str(uuid.uuid4()), "uri": "https://example.com/o"},
            destinationNodeURI={"identifier": str(uuid.uuid4()), "uri": "https://example.com/d"},
            CFDocumentURI=_link(),
            lastChangeDateTime=NOW,
        )
        compat = dump_model(assoc, "compat")["originNodeURI"]
        strict = dump_model(assoc, "strict")["originNodeURI"]
        assert compat["targetType"] is None and compat["title"] is None
        assert "targetType" not in strict and "title" not in strict


class TestDumpSingle:
    def test_compat_wraps(self):
        assert list(dump_single(_document(), "compat", compat_wrapper="CFDocument")) == ["CFDocument"]

    def test_strict_is_flat(self):
        dumped = dump_single(_document(), "strict", compat_wrapper="CFDocument")
        assert "CFDocument" not in dumped
        assert dumped["title"] == "Doc"


class TestDumpCollection:
    @pytest.mark.parametrize("mode", ["compat", "strict"])
    def test_wrapper_is_kept_in_both_modes(self, mode):
        """Set types are wrapped in the official schema too — removing the
        wrapper everywhere would break the ones that are already correct."""
        dumped = dump_collection([_document()], mode, wrapper="CFDocuments")
        assert list(dumped) == ["CFDocuments"]
        assert len(dumped["CFDocuments"]) == 1


class TestDumpPackage:
    @staticmethod
    def _package() -> CFPackageDType:
        doc_id = str(uuid.uuid4())
        return CFPackageDType(
            CFDocument=CFPckgDocumentDType(
                identifier=doc_id,
                uri="https://example.com/doc",
                title="Doc",
                creator="Creator",
                lastChangeDateTime=NOW,
                CFPackageURI=_link(),
            ),
            CFItems=[
                CFPckgItemDType(
                    identifier=str(uuid.uuid4()),
                    uri="https://example.com/item",
                    fullStatement="stmt",
                    lastChangeDateTime=NOW,
                    CFDocumentURI=_link(),
                )
            ],
            CFAssociations=[],
        )

    def test_compat_echoes_package_context_uris(self):
        content = dump_package(self._package(), "compat")
        assert "CFPackageURI" in content["CFDocument"]
        assert "CFDocumentURI" in content["CFItems"][0]

    def test_strict_strips_package_context_uris(self):
        """CFPckg*DType is additionalProperties:false and declares neither."""
        content = dump_package(self._package(), "strict")
        assert "CFPackageURI" not in content["CFDocument"]
        assert "CFDocumentURI" not in content["CFItems"][0]

    def test_strict_propagates_exclude_none_through_the_custom_serializer(self):
        """CFPackageDType has a custom model_serializer, which bypasses pydantic's
        dump options — the regression this guards is nested nulls surviving."""
        content = dump_package(self._package(), "strict")
        assert not [k for k, v in content["CFDocument"].items() if v is None]
        assert not [k for k, v in content["CFItems"][0].items() if v is None]

    def test_compat_keeps_nested_nulls(self):
        content = dump_package(self._package(), "compat")
        assert [k for k, v in content["CFItems"][0].items() if v is None]

    def test_strict_declares_case_version_on_the_package_document(self):
        content = dump_package(self._package(), "strict")
        assert content["CFDocument"]["caseVersion"] == CASE_VERSION_EMIT


def _walk_nulls(node, path="$") -> list[str]:
    """Every path in a JSON-ish structure whose value is None."""
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if v is None:
                found.append(f"{path}.{k}")
            else:
                found += _walk_nulls(v, f"{path}.{k}")
    elif isinstance(node, list):
        for n, v in enumerate(node):
            found += _walk_nulls(v, f"{path}[{n}]")
    return found


class TestStrictPackageNesting:
    """The custom serializer has to carry exclude_none into every nested level,
    including the ones the plain package fixture does not reach."""

    @staticmethod
    def _package_with_definitions_and_rubrics() -> CFPackageDType:
        from src.schemas.cf_item_type import CFItemTypeDType
        from src.schemas.cf_package import CFDefinitionsDType
        from src.schemas.cf_rubric import CFRubricCriterionDType, CFRubricCriterionLevelDType, CFRubricDType

        level = CFRubricCriterionLevelDType(
            identifier=str(uuid.uuid4()),
            uri="https://example.com/level",
            description="Level",
            lastChangeDateTime=NOW,
        )
        criterion = CFRubricCriterionDType(
            identifier=str(uuid.uuid4()),
            uri="https://example.com/criterion",
            category="Cat",
            lastChangeDateTime=NOW,
            CFRubricCriterionLevels=[level],
        )
        return CFPackageDType(
            CFDocument=CFPckgDocumentDType(
                identifier=str(uuid.uuid4()),
                uri="https://example.com/doc",
                title="Doc",
                creator="Creator",
                lastChangeDateTime=NOW,
                CFPackageURI=_link(),
            ),
            CFItems=[],
            CFAssociations=[],
            CFDefinitions=CFDefinitionsDType(
                CFItemTypes=[
                    CFItemTypeDType(
                        identifier=str(uuid.uuid4()),
                        uri="https://example.com/type",
                        title="Type",
                        lastChangeDateTime=NOW,
                    )
                ]
            ),
            CFRubrics=[
                CFRubricDType(
                    identifier=str(uuid.uuid4()),
                    uri="https://example.com/rubric",
                    title="Rubric",
                    lastChangeDateTime=NOW,
                    CFRubricCriteria=[criterion],
                )
            ],
        )

    def test_no_null_survives_anywhere_in_strict(self):
        content = dump_package(self._package_with_definitions_and_rubrics(), "strict")
        assert content["CFDefinitions"]["CFItemTypes"], "fixture must reach the definitions level"
        assert content["CFRubrics"][0]["CFRubricCriteria"][0]["CFRubricCriterionLevels"], "must reach the level level"
        assert _walk_nulls(content) == []

    def test_compat_keeps_them_at_the_same_depths(self):
        content = dump_package(self._package_with_definitions_and_rubrics(), "compat")
        nulls = _walk_nulls(content)
        assert any(".CFDefinitions." in p for p in nulls)
        assert any(".CFRubricCriterionLevels" in p for p in nulls)
