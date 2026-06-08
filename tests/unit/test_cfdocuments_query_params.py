"""Tests for GET /CFDocuments sort / orderBy / filter / fields (CASE v1.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cf_document import CFDocument
from src.models.tenant import Tenant

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
LCT = datetime(2025, 1, 1, tzinfo=timezone.utc)


async def _seed(db_session: AsyncSession) -> None:
    db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
    await db_session.flush()
    docs = [
        ("aaaa0000-0000-0000-0000-000000000001", "Banana Framework", "Alice", "Adopted"),
        ("aaaa0000-0000-0000-0000-000000000002", "Apple Framework", "Bob", "Draft"),
        ("aaaa0000-0000-0000-0000-000000000003", "Cherry Framework", "Alice", "Adopted"),
    ]
    for ident, title, creator, status in docs:
        db_session.add(
            CFDocument(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                identifier=uuid.UUID(ident),
                uri=f"https://example.com/uri/{ident}",
                title=title,
                creator=creator,
                adoption_status=status,
                last_change_date_time=LCT,
            )
        )
    await db_session.flush()


class TestSort:
    async def test_sort_title_asc(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?sort=title&orderBy=asc")
        assert r.status_code == 200
        titles = [d["title"] for d in r.json()["CFDocuments"]]
        assert titles == ["Apple Framework", "Banana Framework", "Cherry Framework"]

    async def test_sort_title_desc(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?sort=title&orderBy=desc")
        titles = [d["title"] for d in r.json()["CFDocuments"]]
        assert titles == ["Cherry Framework", "Banana Framework", "Apple Framework"]

    async def test_invalid_sort_field(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?sort=bogus")
        assert r.status_code == 400
        body = r.json()
        assert body["imsx_codeMinor"]["imsx_codeMinorField"][0]["imsx_codeMinorFieldValue"] == "invalid_sort_field"

    async def test_invalid_orderby(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?sort=title&orderBy=sideways")
        assert r.status_code == 400


class TestFilter:
    async def test_filter_equals(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='Alice'")
        titles = sorted(d["title"] for d in r.json()["CFDocuments"])
        assert titles == ["Banana Framework", "Cherry Framework"]

    async def test_filter_contains(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=title~'Apple'")
        titles = [d["title"] for d in r.json()["CFDocuments"]]
        assert titles == ["Apple Framework"]

    async def test_filter_and(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(
            f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='Alice' AND adoptionStatus='Adopted'"
        )
        titles = sorted(d["title"] for d in r.json()["CFDocuments"])
        assert titles == ["Banana Framework", "Cherry Framework"]

    async def test_filter_or(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(
            f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=title='Apple Framework' OR title='Cherry Framework'"
        )
        titles = sorted(d["title"] for d in r.json()["CFDocuments"])
        assert titles == ["Apple Framework", "Cherry Framework"]

    async def test_filter_invalid_field(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=bogus='x'")
        assert r.status_code == 400
        assert (
            r.json()["imsx_codeMinor"]["imsx_codeMinorField"][0]["imsx_codeMinorFieldValue"]
            == "invalid_selection_field"
        )

    async def test_filter_mixed_and_or_rejected(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='A' AND title='B' OR uri='c'")
        assert r.status_code == 400


class TestFields:
    async def test_fields_projection(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?fields=identifier,title")
        docs = r.json()["CFDocuments"]
        assert all(set(d.keys()) == {"identifier", "title"} for d in docs)

    async def test_fields_invalid(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?fields=identifier,bogus")
        assert r.status_code == 400
        assert (
            r.json()["imsx_codeMinor"]["imsx_codeMinorField"][0]["imsx_codeMinorFieldValue"]
            == "invalid_selection_field"
        )

    async def test_combined_filter_sort_fields(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(
            f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='Alice'&sort=title&orderBy=desc&fields=title"
        )
        docs = r.json()["CFDocuments"]
        assert [d["title"] for d in docs] == ["Cherry Framework", "Banana Framework"]
        assert all(set(d.keys()) == {"title"} for d in docs)


class TestTotalCountAndExtras:
    async def test_x_total_count_unfiltered(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?limit=1")
        assert r.status_code == 200
        assert len(r.json()["CFDocuments"]) == 1
        assert r.headers["X-Total-Count"] == "3"

    async def test_x_total_count_filtered(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='Alice'")
        assert r.headers["X-Total-Count"] == "2"

    async def test_equality_case_insensitive(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        # lowercase value matches the stored 'Alice' (binding: case-insensitive).
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=creator='alice'")
        assert {d["title"] for d in r.json()["CFDocuments"]} == {"Banana Framework", "Cherry Framework"}
        assert r.headers["X-Total-Count"] == "2"

    async def test_subject_filter(self, db_session: AsyncSession, db_client):
        db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
        await db_session.flush()
        db_session.add(
            CFDocument(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                identifier=uuid.UUID("aaaa0000-0000-0000-0000-0000000000ff"),
                uri="https://example.com/uri/ff",
                title="Science Doc",
                subject=["Science", "Mathematics"],
                last_change_date_time=LCT,
            )
        )
        await db_session.flush()
        # contains (case-insensitive)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=subject~'science'")
        assert [d["title"] for d in r.json()["CFDocuments"]] == ["Science Doc"]
        # exact element
        r2 = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=subject='Mathematics'")
        assert [d["title"] for d in r2.json()["CFDocuments"]] == ["Science Doc"]
        # non-match
        r3 = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?filter=subject='History'")
        assert r3.json()["CFDocuments"] == []

    async def test_sort_by_subject_rejected(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?sort=subject")
        assert r.status_code == 400
