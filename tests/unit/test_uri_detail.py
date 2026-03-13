"""Tests for Web UI: URI detail page (Issue #38)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_concept import CFConcept
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant
from src.services import uri_service

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestFindResource:
    async def test_finds_cf_item(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        ident = uuid.uuid4()
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ident,
            uri="u",
            full_statement="stmt",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result is not None
        assert result.resource_type == "CFItem"
        assert result.doc is not None

    async def test_finds_cf_document(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            sample_document.identifier,
        )
        assert result is not None
        assert result.resource_type == "CFDocument"

    async def test_finds_cf_association(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        ident = uuid.uuid4()
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ident,
            uri="u",
            association_type="isChildOf",
            origin_node_uri="ou",
            origin_node_identifier=str(uuid.uuid4()),
            destination_node_uri="du",
            destination_node_identifier=str(uuid.uuid4()),
            last_change_date_time=NOW,
        )
        db_session.add(assoc)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result is not None
        assert result.resource_type == "CFAssociation"
        assert result.doc is not None

    async def test_finds_lookup_item_type(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=ident,
            uri="u",
            title="Standard",
            last_change_date_time=NOW,
        )
        db_session.add(it)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result is not None
        assert result.resource_type == "CFItemType"

    async def test_finds_lookup_subject(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        db_session.add(
            CFSubject(
                tenant_id=tenant.id,
                identifier=ident,
                uri="u",
                title="Math",
                last_change_date_time=NOW,
            )
        )
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result.resource_type == "CFSubject"

    async def test_finds_lookup_concept(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        db_session.add(
            CFConcept(
                tenant_id=tenant.id,
                identifier=ident,
                uri="u",
                title="Algebra",
                last_change_date_time=NOW,
            )
        )
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result.resource_type == "CFConcept"

    async def test_finds_lookup_license(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        db_session.add(
            CFLicense(
                tenant_id=tenant.id,
                identifier=ident,
                uri="u",
                title="MIT",
                last_change_date_time=NOW,
            )
        )
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result.resource_type == "CFLicense"

    async def test_finds_lookup_grouping(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        db_session.add(
            CFAssociationGrouping(
                tenant_id=tenant.id,
                identifier=ident,
                uri="u",
                title="Group A",
                last_change_date_time=NOW,
            )
        )
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            ident,
        )
        assert result.resource_type == "CFAssociationGrouping"

    async def test_finds_cf_rubric(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        ident = uuid.uuid4()
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ident,
            uri="u",
            title="Test Rubric",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(db_session, tenant.id, ident)
        assert result is not None
        assert result.resource_type == "CFRubric"
        assert result.doc is not None

    async def test_finds_cf_rubric_criterion(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="R",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        crit_ident = uuid.uuid4()
        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=crit_ident,
            uri="u",
            category="Quality",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(db_session, tenant.id, crit_ident)
        assert result is not None
        assert result.resource_type == "CFRubricCriterion"
        assert result.doc is not None

    async def test_finds_cf_rubric_criterion_level(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="R",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="u",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        level_ident = uuid.uuid4()
        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=criterion.id,
            identifier=level_ident,
            uri="u",
            quality="Excellent",
            score=5.0,
            last_change_date_time=NOW,
        )
        db_session.add(level)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(db_session, tenant.id, level_ident)
        assert result is not None
        assert result.resource_type == "CFRubricCriterionLevel"
        assert result.doc is not None

    async def test_not_found(self, db_session: AsyncSession, tenant: Tenant):
        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert result is None

    async def test_item_priority_over_document(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """CFItem is found before CFDocument with the same identifier."""
        shared_ident = sample_document.identifier
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=shared_ident,
            uri="u",
            full_statement="item",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        result = await uri_service.find_resource_by_identifier(
            db_session,
            tenant.id,
            shared_ident,
        )
        assert result.resource_type == "CFItem"


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


class TestUriDetailPage:
    async def test_cf_item_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        ident = uuid.uuid4()
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ident,
            uri="https://example.com/item",
            full_statement="The full statement",
            human_coding_scheme="A-1",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{ident}")
        assert resp.status_code == 200
        assert "The full statement" in resp.text
        assert "A-1" in resp.text
        assert "ツリーで表示" in resp.text
        assert str(sample_document.identifier) in resp.text

    async def test_cf_document_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        assert resp.status_code == 200
        assert sample_document.title in resp.text
        assert "ツリーで表示" in resp.text
        assert "CFPackageURI" in resp.text

    async def test_cf_association_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        ident = uuid.uuid4()
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=ident,
            uri="https://example.com/assoc",
            association_type="isRelatedTo",
            origin_node_uri="https://example.com/origin",
            origin_node_identifier=str(uuid.uuid4()),
            origin_node_title="Origin Title",
            destination_node_uri="https://example.com/dest",
            destination_node_identifier=str(uuid.uuid4()),
            destination_node_title="Dest Title",
            destination_node_target_type="CFItem",
            last_change_date_time=NOW,
        )
        db_session.add(assoc)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{ident}")
        assert resp.status_code == 200
        assert "isRelatedTo" in resp.text
        assert "Origin Title" in resp.text
        assert "Dest Title" in resp.text
        assert "targetType" in resp.text

    async def test_lookup_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        ident = uuid.uuid4()
        it = CFItemType(
            tenant_id=tenant.id,
            identifier=ident,
            uri="https://example.com/type",
            title="Knowledge",
            type_code="KN",
            last_change_date_time=NOW,
        )
        db_session.add(it)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{ident}")
        assert resp.status_code == 200
        assert "Knowledge" in resp.text
        assert "KN" in resp.text
        assert "CFItemType" in resp.text  # badge

    async def test_html_title_item(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        stmt = "A" * 60
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            full_statement=stmt,
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert f"<title>{stmt[:50]} - COMPEITO</title>" in resp.text

    async def test_html_title_document(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        assert f"<title>{sample_document.title} - COMPEITO</title>" in resp.text

    async def test_cache_control(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        assert resp.headers["cache-control"] == "public, max-age=3600"

    async def test_breadcrumb(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        assert "テナント一覧" in resp.text
        assert tenant.name in resp.text

    async def test_cf_rubric_page_with_table(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """CFRubric page renders table format when levels have position."""
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/rubric",
            title="Test Rubric",
            description="A test rubric",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="u",
            category="Quality",
            description="Criterion desc",
            weight=1.5,
            position=1,
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=criterion.id,
            identifier=uuid.uuid4(),
            uri="u",
            quality="Excellent",
            score=5.0,
            description="Outstanding work",
            feedback="Great job",
            position=1,
            last_change_date_time=NOW,
        )
        db_session.add(level)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{rubric.identifier}")
        assert resp.status_code == 200
        assert "Test Rubric" in resp.text
        assert "CFRubric" in resp.text  # badge
        assert "Quality" in resp.text  # criterion category
        assert "Excellent" in resp.text  # level quality in header
        assert "Outstanding work" in resp.text  # level description in cell
        assert "<table" in resp.text  # table format rendered

    async def test_cf_rubric_page_list_fallback(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """CFRubric page renders list format when levels have no position."""
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/rubric",
            title="Rubric No Position",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="u",
            category="Cat",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=criterion.id,
            identifier=uuid.uuid4(),
            uri="u",
            quality="Good",
            position=None,
            last_change_date_time=NOW,
        )
        db_session.add(level)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{rubric.identifier}")
        assert resp.status_code == 200
        assert "Cat" in resp.text
        assert "Good" in resp.text
        assert "<table" not in resp.text  # list fallback, no table

    async def test_cf_rubric_criterion_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="Parent Rubric",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        crit_ident = uuid.uuid4()
        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=crit_ident,
            uri="https://example.com/crit",
            category="Knowledge",
            description="Criterion desc",
            weight=2.0,
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{crit_ident}")
        assert resp.status_code == 200
        assert "CFRubricCriterion" in resp.text  # badge
        assert "Knowledge" in resp.text
        assert "Parent Rubric" in resp.text  # parent rubric link

    async def test_cf_rubric_criterion_level_page(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="R",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=uuid.uuid4(),
            uri="u",
            category="ParentCrit",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        level_ident = uuid.uuid4()
        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=criterion.id,
            identifier=level_ident,
            uri="https://example.com/level",
            quality="Excellent",
            score=5.0,
            description="Level desc",
            feedback="Good feedback",
            last_change_date_time=NOW,
        )
        db_session.add(level)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{level_ident}")
        assert resp.status_code == 200
        assert "CFRubricCriterionLevel" in resp.text  # badge
        assert "Excellent" in resp.text
        assert "5.0" in resp.text
        assert "ParentCrit" in resp.text  # parent criterion link


class TestUriDetailErrors:
    async def test_invalid_tenant_400(self, db_client):
        resp = await db_client.get("/bad/uri/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert resp.status_code == 400

    async def test_missing_tenant_404(self, db_client):
        resp = await db_client.get(
            "/99999999-9999-9999-9999-999999999999/uri/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        assert resp.status_code == 404

    async def test_invalid_resource_uuid_400(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/not-uuid")
        assert resp.status_code == 400
        assert "リクエストが不正です" in resp.text

    async def test_resource_not_found_404(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/uri/99999999-9999-9999-9999-999999999999",
        )
        assert resp.status_code == 404

    async def test_error_no_cache_control(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/bad-uuid")
        assert "cache-control" not in resp.headers


class TestUriSecurityUrls:
    async def test_https_url_is_link(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        # The uri field should be rendered as a clickable link
        assert f'href="{sample_document.uri}"' in resp.text

    async def test_javascript_url_is_text(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """javascript: URLs should NOT be rendered as links."""
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="javascript:alert(1)",
            full_statement="test",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert 'href="javascript:' not in resp.text
        assert "javascript:alert(1)" in resp.text  # shown as text
