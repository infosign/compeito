import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_concept import CFConcept
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_subject import CFSubject
from src.models.tenant import Tenant

TENANT_ID = "11111111-1111-1111-1111-111111111111"
CASE_PATH = f"/{TENANT_ID}/ims/case/v1p1"
LCT = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


# ---- Fixtures ----


@pytest.fixture
async def sample_item_type(db_session: AsyncSession, tenant: Tenant) -> CFItemType:
    obj = CFItemType(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("aaaaaaaa-1111-1111-1111-111111111111"),
        uri="https://example.com/uri/item-type",
        title="Knowledge",
        type_code="K",
        hierarchy_code="1",
        last_change_date_time=LCT,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def sample_concept(db_session: AsyncSession, tenant: Tenant) -> CFConcept:
    obj = CFConcept(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("bbbbbbbb-1111-1111-1111-111111111111"),
        uri="https://example.com/uri/concept",
        title="Language",
        keywords="words|expression",
        last_change_date_time=LCT,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def sample_subject(db_session: AsyncSession, tenant: Tenant) -> CFSubject:
    obj = CFSubject(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("cccccccc-1111-1111-1111-111111111111"),
        uri="https://example.com/uri/subject",
        title="Japanese",
        last_change_date_time=LCT,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def sample_license(db_session: AsyncSession, tenant: Tenant) -> CFLicense:
    obj = CFLicense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("dddddddd-1111-1111-1111-111111111111"),
        uri="https://example.com/uri/license",
        title="CC BY 4.0",
        description="Creative Commons",
        last_change_date_time=LCT,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def sample_grouping(db_session: AsyncSession, tenant: Tenant) -> CFAssociationGrouping:
    obj = CFAssociationGrouping(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("eeeeeeee-1111-1111-1111-111111111111"),
        uri="https://example.com/uri/grouping",
        title="Cross-Subject",
        last_change_date_time=LCT,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


# ---- CFItemTypes (Set type) ----


class TestCFItemTypes:
    async def test_list_empty(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes")
        assert response.status_code == 200
        assert response.json() == {"CFItemTypes": []}

    async def test_list_returns_items(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item_type: CFItemType,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes")
        assert response.status_code == 200
        items = response.json()["CFItemTypes"]
        assert len(items) == 1
        assert items[0]["title"] == "Knowledge"
        assert items[0]["typeCode"] == "K"
        assert items[0]["hierarchyCode"] == "1"
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_get_single_returns_array(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item_type: CFItemType,
    ) -> None:
        """Set type: GET returns array with the requested item type when no descendants exist."""
        ident = "aaaaaaaa-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert "CFItemTypes" in body
        assert len(body["CFItemTypes"]) == 1
        assert body["CFItemTypes"][0]["identifier"] == ident

    async def test_get_returns_descendants_by_hierarchy_code(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
        sample_item_type: CFItemType,
    ) -> None:
        """CFItemTypeSetDType: requested item type first, descendants by hierarchyCode follow."""
        # sample_item_type has hierarchy_code="1"
        # Add descendants "1.1", "1.2", "1.1.1" and an unrelated "2"
        descendants = [
            ("1.2", "aaaaaaaa-3333-3333-3333-333333333302"),
            ("1.1", "aaaaaaaa-3333-3333-3333-333333333301"),
            ("1.1.1", "aaaaaaaa-3333-3333-3333-333333333311"),
        ]
        for code, ident_str in descendants:
            db_session.add(
                CFItemType(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    identifier=uuid.UUID(ident_str),
                    uri=f"https://example.com/it-{code}",
                    title=f"Type {code}",
                    hierarchy_code=code,
                    last_change_date_time=LCT,
                )
            )
        # Unrelated sibling at the same depth
        db_session.add(
            CFItemType(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=uuid.UUID("aaaaaaaa-4444-4444-4444-444444444402"),
                uri="https://example.com/it-2",
                title="Type 2",
                hierarchy_code="2",
                last_change_date_time=LCT,
            )
        )
        await db_session.flush()

        ident = "aaaaaaaa-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes/{ident}")
        assert response.status_code == 200
        items = response.json()["CFItemTypes"]
        # Root first, then descendants ordered by hierarchy_code
        codes = [i["hierarchyCode"] for i in items]
        assert codes == ["1", "1.1", "1.1.1", "1.2"]
        assert items[0]["identifier"] == ident
        # Sibling "2" must not be included
        assert "2" not in codes[1:]

    async def test_get_not_found(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_get_invalid_uuid(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes/bad")
        assert response.status_code == 400

    async def test_pagination(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
    ) -> None:
        for i in range(3):
            db_session.add(
                CFItemType(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    identifier=uuid.UUID(f"aaaaaaaa-2222-2222-2222-22222222{i:04d}"),
                    uri=f"https://example.com/it-{i}",
                    title=f"Type {i}",
                    last_change_date_time=LCT,
                )
            )
        await db_session.flush()
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes?limit=2")
        assert len(response.json()["CFItemTypes"]) == 2

    async def test_negative_limit(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFItemTypes?limit=-1")
        assert response.status_code == 400


# ---- CFConcepts (Set type) ----


class TestCFConcepts:
    async def test_list_returns_items(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_concept: CFConcept,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFConcepts")
        assert response.status_code == 200
        items = response.json()["CFConcepts"]
        assert len(items) == 1
        assert items[0]["title"] == "Language"
        assert items[0]["keywords"] == "words|expression"

    async def test_get_single_returns_array(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_concept: CFConcept,
    ) -> None:
        """sample_concept has no hierarchy_code, so only the requested concept is returned."""
        ident = "bbbbbbbb-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFConcepts/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert "CFConcepts" in body
        assert len(body["CFConcepts"]) == 1
        assert body["CFConcepts"][0]["identifier"] == ident

    async def test_get_returns_descendants_by_hierarchy_code(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
    ) -> None:
        """CFConceptSetDType: requested concept first, descendants by hierarchyCode follow."""
        root_ident = uuid.UUID("bbbbbbbb-2222-2222-2222-222222222200")
        db_session.add(
            CFConcept(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=root_ident,
                uri="https://example.com/concept-root",
                title="Root",
                hierarchy_code="1",
                last_change_date_time=LCT,
            )
        )
        descendants = [
            ("1.2", "bbbbbbbb-2222-2222-2222-222222222202"),
            ("1.1", "bbbbbbbb-2222-2222-2222-222222222201"),
        ]
        for code, ident_str in descendants:
            db_session.add(
                CFConcept(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    identifier=uuid.UUID(ident_str),
                    uri=f"https://example.com/concept-{code}",
                    title=f"Concept {code}",
                    hierarchy_code=code,
                    last_change_date_time=LCT,
                )
            )
        # Sibling at the same depth (must be excluded)
        db_session.add(
            CFConcept(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=uuid.UUID("bbbbbbbb-3333-3333-3333-333333333302"),
                uri="https://example.com/concept-sibling",
                title="Sibling",
                hierarchy_code="2",
                last_change_date_time=LCT,
            )
        )
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFConcepts/{root_ident}")
        assert response.status_code == 200
        items = response.json()["CFConcepts"]
        codes = [i["hierarchyCode"] for i in items]
        assert codes == ["1", "1.1", "1.2"]

    async def test_get_not_found(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFConcepts/{uuid.uuid4()}")
        assert response.status_code == 404


# ---- CFSubjects (Set type) ----


class TestCFSubjects:
    async def test_list_returns_items(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_subject: CFSubject,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFSubjects")
        assert response.status_code == 200
        items = response.json()["CFSubjects"]
        assert len(items) == 1
        assert items[0]["title"] == "Japanese"

    async def test_get_single_returns_array(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_subject: CFSubject,
    ) -> None:
        """sample_subject has no hierarchy_code, so only the requested subject is returned."""
        ident = "cccccccc-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFSubjects/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert "CFSubjects" in body
        assert len(body["CFSubjects"]) == 1
        assert body["CFSubjects"][0]["identifier"] == ident

    async def test_get_returns_descendants_by_hierarchy_code(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,
        tenant: Tenant,
    ) -> None:
        """CFSubjectSetDType: requested subject first, descendants by hierarchyCode follow."""
        root_ident = uuid.UUID("cccccccc-2222-2222-2222-222222222200")
        db_session.add(
            CFSubject(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                identifier=root_ident,
                uri="https://example.com/subject-root",
                title="Root",
                hierarchy_code="1",
                last_change_date_time=LCT,
            )
        )
        descendants = [
            ("1.10", "cccccccc-2222-2222-2222-222222222210"),
            ("1.2", "cccccccc-2222-2222-2222-222222222202"),
            ("1.1", "cccccccc-2222-2222-2222-222222222201"),
        ]
        for code, ident_str in descendants:
            db_session.add(
                CFSubject(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    identifier=uuid.UUID(ident_str),
                    uri=f"https://example.com/subject-{code}",
                    title=f"Subject {code}",
                    hierarchy_code=code,
                    last_change_date_time=LCT,
                )
            )
        await db_session.flush()

        response = await db_client.get(f"{CASE_PATH}/CFSubjects/{root_ident}")
        assert response.status_code == 200
        items = response.json()["CFSubjects"]
        codes = [i["hierarchyCode"] for i in items]
        # Lexicographic: "1.1" < "1.10" < "1.2"
        assert codes == ["1", "1.1", "1.10", "1.2"]

    async def test_get_not_found(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFSubjects/{uuid.uuid4()}")
        assert response.status_code == 404


# ---- CFLicenses (single object type) ----


class TestCFLicenses:
    async def test_list_returns_items(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_license: CFLicense,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFLicenses")
        assert response.status_code == 200
        items = response.json()["CFLicenses"]
        assert len(items) == 1
        assert items[0]["title"] == "CC BY 4.0"
        assert items[0]["description"] == "Creative Commons"

    async def test_get_single_returns_object(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_license: CFLicense,
    ) -> None:
        """Single object type: returns {"CFLicense": {...}}, not array."""
        ident = "dddddddd-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFLicenses/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert "CFLicense" in body
        assert isinstance(body["CFLicense"], dict)
        assert body["CFLicense"]["identifier"] == ident

    async def test_get_not_found(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFLicenses/{uuid.uuid4()}")
        assert response.status_code == 404


# ---- CFAssociationGroupings (single object type) ----


class TestCFAssociationGroupings:
    async def test_list_returns_items(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_grouping: CFAssociationGrouping,
    ) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFAssociationGroupings")
        assert response.status_code == 200
        items = response.json()["CFAssociationGroupings"]
        assert len(items) == 1
        assert items[0]["title"] == "Cross-Subject"

    async def test_get_single_returns_object(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_grouping: CFAssociationGrouping,
    ) -> None:
        """Single object type: returns {"CFAssociationGrouping": {...}}, not array."""
        ident = "eeeeeeee-1111-1111-1111-111111111111"
        response = await db_client.get(f"{CASE_PATH}/CFAssociationGroupings/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert "CFAssociationGrouping" in body
        assert isinstance(body["CFAssociationGrouping"], dict)
        assert body["CFAssociationGrouping"]["identifier"] == ident

    async def test_get_not_found(self, db_client: AsyncClient, tenant: Tenant) -> None:
        response = await db_client.get(f"{CASE_PATH}/CFAssociationGroupings/{uuid.uuid4()}")
        assert response.status_code == 404


# ---- Tenant isolation (shared) ----


class TestLookupTenantIsolation:
    async def test_item_type_not_visible(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_item_type: CFItemType,
    ) -> None:
        other = str(uuid.uuid4())
        response = await db_client.get(f"/{other}/ims/case/v1p1/CFItemTypes")
        assert response.status_code == 404

    async def test_license_not_visible(
        self,
        db_client: AsyncClient,
        tenant: Tenant,
        sample_license: CFLicense,
    ) -> None:
        other = str(uuid.uuid4())
        ident = "dddddddd-1111-1111-1111-111111111111"
        response = await db_client.get(f"/{other}/ims/case/v1p1/CFLicenses/{ident}")
        assert response.status_code == 404
