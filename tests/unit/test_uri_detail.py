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
        assert "CFPackage API" in resp.text

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
        assert "CFItem" in resp.text  # targetType value

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
    async def test_non_uuid_tenant_falls_back_to_slug_404(self, db_client):
        """A non-UUID tenant segment is interpreted as a slug; unknown slug → 404."""
        resp = await db_client.get("/bad/uri/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert resp.status_code == 404

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
    async def test_https_url_is_code(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(f"/{tenant.id}/uri/{sample_document.identifier}")
        # URLs should be rendered as <code> text (not clickable links)
        # Check that permalink and API URLs are present (labels are i18n'd)
        assert f"/uri/{sample_document.identifier}" in resp.text
        assert f"/ims/case/v1p1/CFPackages/{sample_document.identifier}" in resp.text

    async def test_javascript_url_not_rendered(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """DB uri with javascript: should NOT appear in rendered page (Permalink is constructed from base_url)."""
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
        assert "javascript:alert(1)" not in resp.text


class TestUriContentNegotiation:
    """Accept-based content negotiation on /uri/{uuid} (Issue #151)."""

    async def test_json_accept_redirects_document(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/uri/{sample_document.identifier}",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == (f"/{tenant.id}/ims/case/v1p1/CFDocuments/{sample_document.identifier}")

    async def test_json_accept_redirects_item(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/item",
            full_statement="Some statement",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/uri/{item.identifier}",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == (f"/{tenant.id}/ims/case/v1p1/CFItems/{item.identifier}")

    async def test_jsonld_accept_redirects(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/uri/{sample_document.identifier}",
            headers={"Accept": "application/ld+json"},
        )
        assert resp.status_code == 303

    async def test_lookup_resource_redirects(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        item_type = CFItemType(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/type",
            title="Knowledge",
            type_code="KN",
            last_change_date_time=NOW,
        )
        db_session.add(item_type)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/uri/{item_type.identifier}",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == (f"/{tenant.id}/ims/case/v1p1/CFItemTypes/{item_type.identifier}")

    async def test_html_accept_returns_html(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/uri/{sample_document.identifier}",
            headers={"Accept": "text/html"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_browser_accept_returns_html(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """A typical browser Accept (text/html + */*) MUST return HTML."""
        resp = await db_client.get(
            f"/{tenant.id}/uri/{sample_document.identifier}",
            headers={
                "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            },
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_wildcard_accept_returns_html(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        resp = await db_client.get(
            f"/{tenant.id}/uri/{sample_document.identifier}",
            headers={"Accept": "*/*"},
        )
        assert resp.status_code == 200

    async def test_rubric_criterion_falls_through_to_html(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        """CFRubricCriterion has no individual CASE API endpoint — keep HTML."""
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
            category="C",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()

        resp = await db_client.get(
            f"/{tenant.id}/uri/{criterion.identifier}",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_missing_resource_with_json_accept_returns_404(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
    ):
        """Unknown UUID with JSON Accept MUST 404, not 303 to a dead URL."""
        resp = await db_client.get(
            f"/{tenant.id}/uri/99999999-9999-9999-9999-999999999999",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 404


class TestLicenseInheritance:
    """Effective license display: own license takes precedence, otherwise inherit from document."""

    async def _make_license(self, db_session: AsyncSession, tenant: Tenant, title: str) -> CFLicense:
        lic = CFLicense(
            tenant_id=tenant.id,
            identifier=uuid.uuid4(),
            uri="https://example.com/license/x",
            title=title,
            description=f"{title} desc",
            license_text=f"{title} full text",
            last_change_date_time=NOW,
        )
        db_session.add(lic)
        await db_session.flush()
        return lic

    async def test_cf_item_inherits_doc_license_when_no_own(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        lic = await self._make_license(db_session, tenant, "Doc-CC-BY")
        sample_document.cf_license_id = lic.id
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            full_statement="An item",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert resp.status_code == 200
        assert "Doc-CC-BY" in resp.text
        assert "ドキュメントから継承" in resp.text  # inheritance badge (Japanese)

    async def test_cf_item_uses_own_license_without_badge(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        doc_lic = await self._make_license(db_session, tenant, "Doc-CC-BY")
        item_lic = await self._make_license(db_session, tenant, "Item-CC-BY-NC")
        sample_document.cf_license_id = doc_lic.id
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            full_statement="An item",
            cf_license_id=item_lic.id,
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert resp.status_code == 200
        assert "Item-CC-BY-NC" in resp.text
        # Doc license is NOT shown when item has its own
        assert "Doc-CC-BY" not in resp.text
        assert "ドキュメントから継承" not in resp.text

    async def test_cf_association_inherits_doc_license(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        lic = await self._make_license(db_session, tenant, "Doc-CC-BY")
        sample_document.cf_license_id = lic.id
        assoc = CFAssociation(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
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

        resp = await db_client.get(f"/{tenant.id}/uri/{assoc.identifier}")
        assert resp.status_code == 200
        assert "Doc-CC-BY" in resp.text
        assert "ドキュメントから継承" in resp.text

    async def test_cf_rubric_inherits_doc_license(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        lic = await self._make_license(db_session, tenant, "Doc-CC-BY")
        sample_document.cf_license_id = lic.id
        rubric = CFRubric(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="Test Rubric",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{rubric.identifier}")
        assert resp.status_code == 200
        assert "Doc-CC-BY" in resp.text
        assert "ドキュメントから継承" in resp.text

    async def test_no_license_anywhere_renders_nothing(
        self,
        db_session: AsyncSession,
        db_client,
        tenant: Tenant,
        sample_document: CFDocument,
    ):
        item = CFItem(
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.uuid4(),
            uri="u",
            full_statement="An item",
            last_change_date_time=NOW,
            depth=0,
        )
        db_session.add(item)
        await db_session.flush()

        resp = await db_client.get(f"/{tenant.id}/uri/{item.identifier}")
        assert resp.status_code == 200
        # No license label/badge anywhere
        assert "ライセンス URI" not in resp.text
        assert "ドキュメントから継承" not in resp.text


class TestUriCrossTenantCriterion:
    """After relaxing the criterion/level unique constraint to be parent-scoped,
    the same criterion identifier can exist in multiple tenants. /uri resolution
    must still return THIS tenant's resource and must not raise
    MultipleResultsFound."""

    async def _make_rubric_with_criterion(self, db_session, tenant_id, crit_ident, level_ident):
        doc = CFDocument(
            tenant_id=tenant_id,
            identifier=uuid.uuid4(),
            uri=f"https://example.com/{tenant_id}/doc",
            title="Doc",
            last_change_date_time=NOW,
        )
        db_session.add(doc)
        await db_session.flush()
        rubric = CFRubric(
            tenant_id=tenant_id,
            cf_document_id=doc.id,
            identifier=uuid.uuid4(),
            uri="u",
            title="R",
            last_change_date_time=NOW,
        )
        db_session.add(rubric)
        await db_session.flush()
        criterion = CFRubricCriterion(
            cf_rubric_id=rubric.id,
            identifier=crit_ident,
            uri="u",
            category="Quality",
            last_change_date_time=NOW,
        )
        db_session.add(criterion)
        await db_session.flush()
        level = CFRubricCriterionLevel(
            cf_rubric_criterion_id=criterion.id,
            identifier=level_ident,
            uri="u",
            last_change_date_time=NOW,
        )
        db_session.add(level)
        await db_session.flush()
        return criterion, level

    async def test_same_identifier_resolves_per_tenant(self, db_session: AsyncSession, tenant: Tenant):
        TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
        db_session.add(Tenant(id=TENANT_B, name="Tenant B", is_private=False))
        await db_session.flush()

        crit_ident = uuid.uuid4()
        level_ident = uuid.uuid4()
        crit_a, level_a = await self._make_rubric_with_criterion(db_session, tenant.id, crit_ident, level_ident)
        crit_b, level_b = await self._make_rubric_with_criterion(db_session, TENANT_B, crit_ident, level_ident)
        assert crit_a.id != crit_b.id  # two distinct rows, same identifier

        # Tenant A resolves to A's criterion (no MultipleResultsFound).
        res_a = await uri_service.find_resource_by_identifier(db_session, tenant.id, crit_ident)
        assert res_a is not None and res_a.resource_type == "CFRubricCriterion"
        assert res_a.resource.id == crit_a.id

        # Tenant B resolves to B's criterion.
        res_b = await uri_service.find_resource_by_identifier(db_session, TENANT_B, crit_ident)
        assert res_b is not None and res_b.resource.id == crit_b.id

        # Same for levels.
        lvl_a = await uri_service.find_resource_by_identifier(db_session, tenant.id, level_ident)
        assert lvl_a is not None and lvl_a.resource_type == "CFRubricCriterionLevel"
        assert lvl_a.resource.id == level_a.id
        lvl_b = await uri_service.find_resource_by_identifier(db_session, TENANT_B, level_ident)
        assert lvl_b is not None and lvl_b.resource.id == level_b.id
