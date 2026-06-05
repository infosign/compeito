import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
from src.models.tenant import Tenant

TENANT_ID = "11111111-1111-1111-1111-111111111111"
DOC_IDENTIFIER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
RUBRIC_IDENTIFIER = "aabbcc01-0000-0000-0000-000000000001"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def sample_rubric(
    db_session: AsyncSession,
    tenant: Tenant,
    sample_document: CFDocument,
) -> CFRubric:
    """Create a rubric with criteria and levels."""
    rubric = CFRubric(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=sample_document.id,
        identifier=uuid.UUID(RUBRIC_IDENTIFIER),
        uri=f"https://example.com/uri/{RUBRIC_IDENTIFIER}",
        title="Test Rubric",
        description="A rubric for testing",
        last_change_date_time=LCT,
    )
    db_session.add(rubric)
    await db_session.flush()

    # Item referenced by criterion
    item = CFItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        cf_document_id=sample_document.id,
        identifier=uuid.UUID("aabbcc02-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/item1",
        full_statement="Referenced Item",
        last_change_date_time=LCT,
    )
    db_session.add(item)
    await db_session.flush()

    criterion = CFRubricCriterion(
        id=uuid.uuid4(),
        cf_rubric_id=rubric.id,
        identifier=uuid.UUID("aabbcc03-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/criterion1",
        cf_item_id=item.id,
        rubric_id=rubric.identifier,
        category="Quality",
        description="Criterion description",
        weight=1.5,
        position=1,
        last_change_date_time=LCT,
    )
    db_session.add(criterion)
    await db_session.flush()

    level = CFRubricCriterionLevel(
        id=uuid.uuid4(),
        cf_rubric_criterion_id=criterion.id,
        rubric_criterion_id=criterion.identifier,
        identifier=uuid.UUID("aabbcc04-0000-0000-0000-000000000001"),
        uri="https://example.com/uri/level1",
        description="Excellent",
        quality="High",
        score=5.0,
        feedback="Outstanding work",
        position=1,
        last_change_date_time=LCT,
    )
    db_session.add(level)
    await db_session.flush()

    return rubric


class TestGetCFRubric:
    async def test_get_existing_rubric(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{RUBRIC_IDENTIFIER}")
        assert response.status_code == 200
        body = response.json()
        assert "CFRubric" in body
        rubric = body["CFRubric"]
        assert rubric["identifier"] == RUBRIC_IDENTIFIER
        assert rubric["title"] == "Test Rubric"
        assert rubric["description"] == "A rubric for testing"
        assert "lastChangeDateTime" in rubric

    async def test_rubric_contains_criteria(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{RUBRIC_IDENTIFIER}")
        rubric = response.json()["CFRubric"]
        assert "CFRubricCriteria" in rubric
        criteria = rubric["CFRubricCriteria"]
        assert len(criteria) == 1
        c = criteria[0]
        assert c["identifier"] == "aabbcc03-0000-0000-0000-000000000001"
        assert c["category"] == "Quality"
        assert c["weight"] == 1.5
        assert c["position"] == 1
        assert c["rubricId"] == RUBRIC_IDENTIFIER

    async def test_criterion_contains_levels(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{RUBRIC_IDENTIFIER}")
        criterion = response.json()["CFRubric"]["CFRubricCriteria"][0]
        assert "CFRubricCriterionLevels" in criterion
        levels = criterion["CFRubricCriterionLevels"]
        assert len(levels) == 1
        lv = levels[0]
        assert lv["identifier"] == "aabbcc04-0000-0000-0000-000000000001"
        assert lv["quality"] == "High"
        assert lv["score"] == 5.0
        assert lv["feedback"] == "Outstanding work"
        assert lv["position"] == 1
        assert lv["rubricCriterionId"] == "aabbcc03-0000-0000-0000-000000000001"

    async def test_criterion_cf_item_uri(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{RUBRIC_IDENTIFIER}")
        criterion = response.json()["CFRubric"]["CFRubricCriteria"][0]
        assert "CFItemURI" in criterion
        item_uri = criterion["CFItemURI"]
        assert item_uri["title"] == "Referenced Item"
        assert item_uri["identifier"] == "aabbcc02-0000-0000-0000-000000000001"

    async def test_rubric_without_criteria(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """Rubric with no criteria → CFRubricCriteria absent."""
        rubric = CFRubric(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("aabbcc01-0000-0000-0000-000000000002"),
            uri="https://example.com/uri/rubric2",
            title="Empty Rubric",
            last_change_date_time=LCT,
        )
        db_session.add(rubric)
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFRubrics/aabbcc01-0000-0000-0000-000000000002")
        body = response.json()["CFRubric"]
        assert body["title"] == "Empty Rubric"
        assert body.get("CFRubricCriteria") is None

    async def test_nonexistent_rubric_returns_404(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["imsx_codeMajor"] == "failure"

    async def test_invalid_uuid_returns_400(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/not-a-uuid")
        assert response.status_code == 400

    async def test_cache_control(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics/{RUBRIC_IDENTIFIER}")
        assert response.headers["cache-control"] == "public, max-age=3600"


class TestListCFRubrics:
    async def test_list_requires_doc_parameter(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics")
        assert response.status_code == 400

    async def test_list_invalid_doc_uuid(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc=not-a-uuid")
        assert response.status_code == 400
        body = response.json()
        assert body["imsx_codeMinor"]["imsx_codeMinorField"][0]["imsx_codeMinorFieldValue"] == "invalid_uuid"

    async def test_list_doc_not_found(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
    ) -> None:
        fake_doc = str(uuid.uuid4())
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={fake_doc}")
        assert response.status_code == 404

    async def test_list_empty(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}")
        assert response.status_code == 200
        assert response.json() == {"CFRubrics": []}

    async def test_list_returns_rubrics(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}")
        assert response.status_code == 200
        rubrics = response.json()["CFRubrics"]
        assert len(rubrics) == 1
        assert rubrics[0]["identifier"] == RUBRIC_IDENTIFIER
        assert rubrics[0]["title"] == "Test Rubric"
        assert "CFRubricCriteria" in rubrics[0]

    async def test_list_pagination(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_document: CFDocument,
        sample_rubric: CFRubric,
    ) -> None:
        # Add a second rubric
        rubric2 = CFRubric(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            cf_document_id=sample_document.id,
            identifier=uuid.UUID("aabbcc01-0000-0000-0000-000000000099"),
            uri="https://example.com/uri/rubric99",
            title="Second Rubric",
            last_change_date_time=LCT,
        )
        db_session.add(rubric2)
        await db_session.flush()

        # limit=1 should return only 1
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}&limit=1")
        assert response.status_code == 200
        assert len(response.json()["CFRubrics"]) == 1

        # offset=1&limit=1 should return the other
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}&offset=1&limit=1")
        assert response.status_code == 200
        assert len(response.json()["CFRubrics"]) == 1

        # No limit should return both
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}")
        assert response.status_code == 200
        assert len(response.json()["CFRubrics"]) == 2

    async def test_list_cache_control(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFRubrics?doc={DOC_IDENTIFIER}")
        assert response.headers["cache-control"] == "public, max-age=3600"


class TestCFPackageWithRubrics:
    async def test_package_includes_empty_rubrics(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
    ) -> None:
        """CFPackage always includes CFRubrics as empty array."""
        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        pkg = response.json()
        assert "CFRubrics" in pkg
        assert pkg["CFRubrics"] == []

    async def test_package_includes_rubrics_with_data(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_document: CFDocument,
        sample_rubric: CFRubric,
    ) -> None:
        """CFPackage includes rubrics with nested criteria and levels."""
        response = await db_client.get(f"{CASE_PATH}/CFPackages/{DOC_IDENTIFIER}")
        pkg = response.json()
        assert len(pkg["CFRubrics"]) == 1
        rubric = pkg["CFRubrics"][0]
        assert rubric["identifier"] == RUBRIC_IDENTIFIER
        assert rubric["title"] == "Test Rubric"
        assert len(rubric["CFRubricCriteria"]) == 1
        assert len(rubric["CFRubricCriteria"][0]["CFRubricCriterionLevels"]) == 1


class TestTenantIsolation:
    async def test_rubric_not_visible_across_tenants(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_rubric: CFRubric,
    ) -> None:
        other_tenant_id = str(uuid.uuid4())
        response = await db_client.get(f"/{other_tenant_id}/ims/case/v1p1/CFRubrics/{RUBRIC_IDENTIFIER}")
        assert response.status_code == 404
