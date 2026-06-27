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


def _parse_link(header: str) -> dict[str, dict[str, str]]:
    """Parse an RFC 8288 Link header into {rel: {query param: value}}.

    Asserting on parsed rel/query pairs (rather than exact URL strings) keeps
    these tests robust to parameter ordering.
    """
    from urllib.parse import parse_qs, urlsplit

    out: dict[str, dict[str, str]] = {}
    for part in header.split(","):
        part = part.strip()
        url, _, relseg = part.partition(";")
        url = url.strip()[1:-1]  # strip < >
        rel = relseg.split("=", 1)[1].strip().strip('"')
        q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        out[rel] = q
    return out


class TestBuildLinkHeader:
    """Pure unit tests for build_link_header (no DB). See design-notes.md C5."""

    BASE = "https://h/t/ims/case/v1p1/CFDocuments"

    def test_middle_page_all_four_rels(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(build_link_header(self.BASE, limit=10, offset=20, total=100))
        assert set(rels) == {"first", "prev", "next", "last"}
        assert rels["first"]["offset"] == "0"
        assert rels["prev"]["offset"] == "10"
        assert rels["next"]["offset"] == "30"
        assert rels["last"]["offset"] == "90"
        assert all(r["limit"] == "10" for r in rels.values())

    def test_first_page_no_prev_first(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(build_link_header(self.BASE, limit=10, offset=0, total=100))
        assert set(rels) == {"next", "last"}

    def test_last_page_no_next_last(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(build_link_header(self.BASE, limit=10, offset=90, total=100))
        assert set(rels) == {"first", "prev"}

    def test_single_page_returns_none(self):
        from src.services.case_query_params import build_link_header

        assert build_link_header(self.BASE, limit=100, offset=0, total=50) is None

    def test_total_zero_returns_none(self):
        from src.services.case_query_params import build_link_header

        assert build_link_header(self.BASE, limit=10, offset=0, total=0) is None
        # offset > 0 with empty series still yields no Link.
        assert build_link_header(self.BASE, limit=10, offset=50, total=0) is None

    def test_limit_zero_returns_none(self):
        from src.services.case_query_params import build_link_header

        assert build_link_header(self.BASE, limit=0, offset=0, total=100) is None

    def test_extra_params_carried_and_none_omitted(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(
            build_link_header(
                self.BASE,
                limit=10,
                offset=20,
                total=100,
                extra_params={"sort": "title", "orderBy": "asc", "filter": None, "fields": None},
            )
        )
        assert rels["next"]["sort"] == "title"
        assert rels["next"]["orderBy"] == "asc"
        assert "filter" not in rels["next"]
        assert "fields" not in rels["next"]

    def test_filter_special_chars_encoded(self):
        from src.services.case_query_params import build_link_header

        header = build_link_header(
            self.BASE, limit=10, offset=20, total=100, extra_params={"filter": "creator='Al ice'"}
        )
        # Raw special chars must be percent-encoded in the header.
        assert "Al ice" not in header
        rels = _parse_link(header)
        assert rels["next"]["filter"] == "creator='Al ice'"  # round-trips when parsed

    def test_last_offset_on_ragged_total(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(build_link_header(self.BASE, limit=100, offset=0, total=250))
        assert rels["last"]["offset"] == "200"

    def test_prev_not_negative(self):
        from src.services.case_query_params import build_link_header

        rels = _parse_link(build_link_header(self.BASE, limit=100, offset=50, total=300))
        assert rels["prev"]["offset"] == "0"

    def test_offset_out_of_range_emits_first_prev_last(self):
        from src.services.case_query_params import build_link_header

        # offset beyond total: empty page, but caller can rewind.
        rels = _parse_link(build_link_header(self.BASE, limit=10, offset=500, total=100))
        assert "next" not in rels
        assert set(rels) >= {"first", "prev", "last"}
        assert rels["last"]["offset"] == "90"  # last_offset < offset

    # --- offset cap boundary (regression for must-fix #1: no self-loop) ---

    def test_next_omitted_at_offset_cap(self):
        from src.services.case_query_params import OFFSET_CAP, build_link_header

        # At the cap with more data: next_offset would exceed the cap and be
        # re-clamped by the router to OFFSET_CAP (the current page) -> omit it.
        rels = _parse_link(
            build_link_header(self.BASE, limit=500, offset=OFFSET_CAP, total=OFFSET_CAP + 2000)
        )
        assert "next" not in rels

    def test_last_clamped_not_self_loop_at_cap(self):
        from src.services.case_query_params import OFFSET_CAP, build_link_header

        # True last page is beyond the cap; last must clamp to OFFSET_CAP and,
        # since that equals the current offset, be omitted (no self-loop).
        rels = _parse_link(
            build_link_header(self.BASE, limit=500, offset=OFFSET_CAP, total=OFFSET_CAP + 2000)
        )
        assert "last" not in rels


class TestLinkHeaderEndpoint:
    """Integration: Link header on GET /CFDocuments."""

    async def test_link_header_present_with_rels(self, db_session: AsyncSession, db_client):
        await _seed(db_session)  # 3 docs
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?limit=1&offset=1")
        assert r.status_code == 200
        rels = _parse_link(r.headers["Link"])
        assert set(rels) == {"first", "prev", "next", "last"}
        assert rels["next"]["offset"] == "2"

    async def test_link_tenant_is_uuid_even_via_slug(self, db_session: AsyncSession, db_client):
        # Seed tenant with a slug, address via slug, expect UUID in Link URLs.
        db_session.add(
            Tenant(id=uuid.UUID("22222222-2222-2222-2222-222222222222"), name="S", slug="myslug", is_private=False)
        )
        await db_session.flush()
        for i in range(3):
            db_session.add(
                CFDocument(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    identifier=uuid.uuid4(),
                    uri=f"https://example.com/s/{i}",
                    title=f"Doc {i}",
                    last_change_date_time=LCT,
                )
            )
        await db_session.flush()
        r = await db_client.get("/myslug/ims/case/v1p1/CFDocuments?limit=1&offset=1")
        assert "22222222-2222-2222-2222-222222222222" in r.headers["Link"]
        assert "myslug" not in r.headers["Link"]

    async def test_link_preserves_filter_and_sort(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(
            f"/{TENANT_ID}/ims/case/v1p1/CFDocuments?limit=1&offset=1&sort=title&filter=creator='Alice'"
        )
        rels = _parse_link(r.headers["Link"])
        assert rels["next"]["sort"] == "title"
        assert rels["next"]["filter"] == "creator='Alice'"

    async def test_no_link_header_single_page(self, db_session: AsyncSession, db_client):
        await _seed(db_session)
        r = await db_client.get(f"/{TENANT_ID}/ims/case/v1p1/CFDocuments")
        assert "Link" not in r.headers
        assert r.headers["X-Total-Count"] == "3"
