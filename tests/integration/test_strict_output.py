"""Strict output mode across every CASE GET endpoint (C16 / C1 / C2 / C8).

Two invariants are being pinned here:

1. **compat is unchanged.** Existing clients and the static-publish snapshots
   read today's shape; strict is opt-in for whoever asks for schema conformance.
2. **strict is the official shape**: single resources flat, no nulls, no
   package-context URIs, ``caseVersion`` declared as "1.1".

Design: docs/dev/designs/strict-output.md.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_concept import CFConcept
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_rubric import CFRubric
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant
from src.services.case_serializer import CASE_VERSION_EMIT

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

ITEM_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ASSOC_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _has_null(payload: dict) -> bool:
    return any(v is None for v in payload.values())


@pytest.fixture
async def populated(db_session: AsyncSession, tenant: Tenant, sample_document: CFDocument):
    """One of each resource type, so every route has something to serialize."""
    item = CFItem(
        tenant_id=tenant.id,
        cf_document_id=sample_document.id,
        identifier=ITEM_ID,
        uri=f"https://example.com/uri/{ITEM_ID}",
        full_statement="stmt",
        depth=0,
        last_change_date_time=LCT,
    )
    grouping = CFAssociationGrouping(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/grouping",
        title="Grouping",
        last_change_date_time=LCT,
    )
    item_type = CFItemType(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/type",
        title="Type",
        last_change_date_time=LCT,
    )
    concept = CFConcept(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/concept",
        title="Concept",
        last_change_date_time=LCT,
    )
    subject = CFSubject(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/subject",
        title="Subject",
        last_change_date_time=LCT,
    )
    license_ = CFLicense(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/license",
        title="License",
        last_change_date_time=LCT,
    )
    rubric = CFRubric(
        tenant_id=tenant.id,
        cf_document_id=sample_document.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/rubric",
        title="Rubric",
        last_change_date_time=LCT,
    )
    # A second document: with only one, `limit=1` yields no next/last rel and the
    # Link header is absent — a conditional assertion on it would never run.
    second_document = CFDocument(
        tenant_id=tenant.id,
        identifier=uuid.uuid4(),
        uri="https://example.com/uri/doc2",
        title="Second",
        creator="Creator",
        last_change_date_time=LCT,
    )
    db_session.add_all([item, grouping, item_type, concept, subject, license_, rubric, second_document])
    await db_session.flush()
    db_session.add(
        CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ASSOC_ID,
            uri=f"https://example.com/uri/{ASSOC_ID}",
            association_type="isChildOf",
            origin_node_uri=f"https://example.com/uri/{ITEM_ID}",
            origin_node_identifier=str(ITEM_ID),
            destination_node_uri=f"https://example.com/uri/{DOC_IDENTIFIER}",
            destination_node_identifier=DOC_IDENTIFIER,
            last_change_date_time=LCT,
        )
    )
    await db_session.flush()
    return {
        "item": item,
        "grouping": grouping,
        "item_type": item_type,
        "concept": concept,
        "subject": subject,
        "license": license_,
        "rubric": rubric,
    }


class TestWrapperRemoval:
    """C1: only the six single-resource routes lose their wrapper."""

    @pytest.mark.parametrize(
        "path_key,wrapper",
        [
            ("CFDocuments/" + DOC_IDENTIFIER, "CFDocument"),
            ("CFItems/" + str(ITEM_ID), "CFItem"),
            ("CFAssociations/" + str(ASSOC_ID), "CFAssociation"),
        ],
    )
    async def test_flat_in_strict_wrapped_in_compat(self, db_client: AsyncClient, populated, path_key, wrapper):
        compat = await db_client.get(f"{CASE_PATH}/{path_key}")
        strict = await db_client.get(f"{CASE_PATH}/{path_key}?strict=1")
        assert compat.status_code == strict.status_code == 200
        assert list(compat.json()) == [wrapper]
        assert wrapper not in strict.json()
        assert "identifier" in strict.json()

    async def test_lookup_singles_are_flat_in_strict(self, db_client: AsyncClient, populated):
        for key, wrapper in (("license", "CFLicense"), ("grouping", "CFAssociationGrouping"), ("rubric", "CFRubric")):
            ident = populated[key].identifier
            route = {"license": "CFLicenses", "grouping": "CFAssociationGroupings", "rubric": "CFRubrics"}[key]
            compat = await db_client.get(f"{CASE_PATH}/{route}/{ident}")
            strict = await db_client.get(f"{CASE_PATH}/{route}/{ident}?strict=1")
            assert list(compat.json()) == [wrapper], route
            assert wrapper not in strict.json(), route

    @pytest.mark.parametrize(
        "route,wrapper", [("CFItemTypes", "CFItemTypes"), ("CFConcepts", "CFConcepts"), ("CFSubjects", "CFSubjects")]
    )
    async def test_set_types_keep_their_wrapper(self, db_client: AsyncClient, populated, route, wrapper):
        """These are Set types in the official schema — the wrapper IS correct."""
        key = {"CFItemTypes": "item_type", "CFConcepts": "concept", "CFSubjects": "subject"}[route]
        ident = populated[key].identifier
        strict = await db_client.get(f"{CASE_PATH}/{route}/{ident}?strict=1")
        assert list(strict.json()) == [wrapper]

    async def test_item_associations_keep_their_wrapper(self, db_client: AsyncClient, populated):
        """CFAssociationSetDType is {"CFItem": ..., "CFAssociations": [...]}."""
        strict = await db_client.get(f"{CASE_PATH}/CFItemAssociations/{ITEM_ID}?strict=1")
        assert set(strict.json()) == {"CFItem", "CFAssociations"}

    async def test_document_list_keeps_its_wrapper(self, db_client: AsyncClient, populated):
        strict = await db_client.get(f"{CASE_PATH}/CFDocuments?strict=1")
        assert list(strict.json()) == ["CFDocuments"]


class TestNullRemoval:
    """C16: the largest source of schema-invalid output."""

    async def test_single_resource(self, db_client: AsyncClient, populated):
        compat = (await db_client.get(f"{CASE_PATH}/CFItems/{ITEM_ID}")).json()["CFItem"]
        strict = (await db_client.get(f"{CASE_PATH}/CFItems/{ITEM_ID}?strict=1")).json()
        assert _has_null(compat)
        assert not _has_null(strict)

    async def test_list_elements(self, db_client: AsyncClient, populated):
        strict = (await db_client.get(f"{CASE_PATH}/CFDocuments?strict=1")).json()["CFDocuments"]
        assert strict and not any(_has_null(d) for d in strict)

    async def test_package_nested_levels(self, db_client: AsyncClient, populated):
        """CFPackageDType has a custom serializer that used to swallow the flag."""
        strict = (await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}?strict=1")).json()
        assert not _has_null(strict["CFDocument"])
        assert strict["CFItems"] and not any(_has_null(i) for i in strict["CFItems"])
        assert strict["CFAssociations"] and not any(_has_null(a) for a in strict["CFAssociations"])

    async def test_compat_still_echoes_nulls(self, db_client: AsyncClient, populated):
        compat = (await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")).json()
        assert _has_null(compat["CFItems"][0])


class TestPackageUriStripping:
    """C2: CFPckg*DType is additionalProperties:false."""

    async def test_strict_strips_compat_keeps(self, db_client: AsyncClient, populated):
        compat = (await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")).json()
        strict = (await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}?strict=1")).json()
        assert "CFPackageURI" in compat["CFDocument"]
        assert "CFPackageURI" not in strict["CFDocument"]
        assert "CFDocumentURI" in compat["CFItems"][0]
        assert "CFDocumentURI" not in strict["CFItems"][0]


class TestCaseVersion:
    """C8: what the server declares, not what the source happened to say."""

    async def test_strict_declares_v11(self, db_client: AsyncClient, populated):
        strict = (await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}?strict=1")).json()
        assert strict["caseVersion"] == CASE_VERSION_EMIT

    async def test_package_document_too(self, db_client: AsyncClient, populated):
        strict = (await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}?strict=1")).json()
        assert strict["CFDocument"]["caseVersion"] == CASE_VERSION_EMIT


class TestModeSelection:
    async def test_conflict_is_a_400(self, db_client: AsyncClient, populated):
        resp = await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}?strict=1&compat=1")
        assert resp.status_code == 400
        body = resp.json()
        assert body["imsx_codeMajor"] == "failure"
        # The field name is what tells the caller which parameter to fix.
        field = body["imsx_codeMinor"]["imsx_codeMinorField"][0]
        assert field["imsx_codeMinorFieldName"] == "strict"
        assert field["imsx_codeMinorFieldValue"] == "invalid_selection_field"

    async def test_config_default_applies_through_the_router(self, db_client: AsyncClient, populated, monkeypatch):
        """The planned default flip has to work end to end, not just in the
        resolver: this is the rehearsal for that one-setting change."""
        from src.config import settings

        monkeypatch.setattr(settings, "case_output_default", "strict")
        resp = await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}")
        assert "CFDocument" not in resp.json()
        assert resp.json()["caseVersion"] == CASE_VERSION_EMIT

    @pytest.mark.parametrize(
        "route",
        ["CFItemTypes", "CFConcepts", "CFSubjects", "CFLicenses", "CFAssociationGroupings"],
    )
    async def test_extension_lists_honour_strict(self, db_client: AsyncClient, populated, route):
        """The compeito-only list routes take the mode too — strict has to be
        uniform across all 18 CASE GET routes, not just the official ones."""
        resp = await db_client.get(f"{CASE_PATH}/{route}?strict=1")
        assert resp.status_code == 200
        payload = resp.json()[route]
        assert payload and not any(_has_null(entry) for entry in payload)

    async def test_explicit_compat_matches_the_default(self, db_client: AsyncClient, populated):
        default = await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}")
        explicit = await db_client.get(f"{CASE_PATH}/CFDocuments/{DOC_IDENTIFIER}?compat=1")
        assert default.json() == explicit.json()

    async def test_link_header_carries_the_mode(self, db_client: AsyncClient, populated):
        """Otherwise paging silently drops back to the default mode."""
        resp = await db_client.get(f"{CASE_PATH}/CFDocuments?strict=1&limit=1&offset=0")
        link = resp.headers["Link"]
        assert "strict=1" in link

    async def test_no_link_params_when_mode_not_requested(self, db_client: AsyncClient, populated):
        resp = await db_client.get(f"{CASE_PATH}/CFDocuments?limit=1&offset=0")
        link = resp.headers["Link"]
        assert "strict" not in link and "compat" not in link
