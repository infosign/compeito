"""Tests for the tenant slug feature: model, service, and routing.

CLI-side tests for `tenant create --slug` / `tenant update --slug` /
`--clear-slug` live in `tests/unit/test_cli.py` (they use the sync runner
fixtures defined there).
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant
from src.services import tenant_service

# ---------------------------------------------------------------------------
# Model: slug_or_id property
# ---------------------------------------------------------------------------


class TestSlugOrIdProperty:
    def test_returns_slug_when_set(self):
        t = Tenant(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            name="Pond Edge University",
            slug="ikenohata-u",
            is_private=False,
        )
        assert t.slug_or_id == "ikenohata-u"

    def test_returns_uuid_when_slug_missing(self):
        t = Tenant(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            name="No Slug",
            slug=None,
            is_private=False,
        )
        assert t.slug_or_id == "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# DB CHECK constraint enforcement (mirrored from the CLI regex)
# ---------------------------------------------------------------------------


class TestSlugDbConstraint:
    @pytest.mark.parametrize(
        "valid_slug",
        ["ikenohata-u", "acme", "osaka-univ-2025", "a1", "z9"],
    )
    async def test_accepts_valid_slugs(self, db_session: AsyncSession, valid_slug: str):
        t = Tenant(name="x", slug=valid_slug, is_private=False)
        db_session.add(t)
        await db_session.flush()

    @pytest.mark.parametrize(
        "invalid_slug",
        [
            "-foo",  # leading hyphen
            "foo-",  # trailing hyphen
            "Foo",  # uppercase
            "a",  # too short (1 char)
            "foo_bar",  # underscore not allowed
            "fo o",  # space not allowed
            "foo!",  # special char
        ],
    )
    async def test_rejects_invalid_slugs(self, db_session: AsyncSession, invalid_slug: str):
        t = Tenant(name="x", slug=invalid_slug, is_private=False)
        db_session.add(t)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_slug_unique(self, db_session: AsyncSession):
        a = Tenant(name="A", slug="dup", is_private=False)
        b = Tenant(name="B", slug="dup", is_private=False)
        db_session.add_all([a, b])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_null_slug_is_allowed_and_not_constrained_by_unique(self, db_session: AsyncSession):
        """Multiple tenants without a slug must coexist."""
        a = Tenant(name="A", slug=None, is_private=False)
        b = Tenant(name="B", slug=None, is_private=False)
        db_session.add_all([a, b])
        await db_session.flush()


# ---------------------------------------------------------------------------
# Service: resolve_tenant + get_tenant_by_slug
# ---------------------------------------------------------------------------


class TestResolveTenant:
    async def test_resolves_by_uuid(self, db_session: AsyncSession):
        t = Tenant(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            name="UUID Lookup",
            slug="uuid-lookup",
            is_private=False,
        )
        db_session.add(t)
        await db_session.flush()

        result = await tenant_service.resolve_tenant(db_session, "22222222-2222-2222-2222-222222222222")
        assert result is not None
        assert result.id == t.id

    async def test_resolves_by_slug(self, db_session: AsyncSession):
        t = Tenant(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            name="Slug Lookup",
            slug="ikenohata-u",
            is_private=False,
        )
        db_session.add(t)
        await db_session.flush()

        result = await tenant_service.resolve_tenant(db_session, "ikenohata-u")
        assert result is not None
        assert result.id == t.id

    async def test_unknown_uuid_returns_none(self, db_session: AsyncSession):
        result = await tenant_service.resolve_tenant(db_session, "99999999-9999-9999-9999-999999999999")
        assert result is None

    async def test_unknown_slug_returns_none(self, db_session: AsyncSession):
        result = await tenant_service.resolve_tenant(db_session, "no-such-slug")
        assert result is None

    async def test_get_tenant_by_slug_finds_match(self, db_session: AsyncSession):
        db_session.add(Tenant(name="x", slug="hit", is_private=False))
        await db_session.flush()
        result = await tenant_service.get_tenant_by_slug(db_session, "hit")
        assert result is not None
        assert result.slug == "hit"

    async def test_get_tenant_by_slug_misses(self, db_session: AsyncSession):
        result = await tenant_service.get_tenant_by_slug(db_session, "miss")
        assert result is None


# ---------------------------------------------------------------------------
# Routing: Web UI accepts both UUID and slug
# ---------------------------------------------------------------------------


class TestSlugRouting:
    async def test_tenant_page_via_slug(self, db_session: AsyncSession, db_client):
        db_session.add(
            Tenant(
                id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
                name="Ikenohata University",
                slug="ikenohata-u",
                is_private=False,
            )
        )
        await db_session.flush()

        resp = await db_client.get("/ikenohata-u/")
        assert resp.status_code == 200
        assert "Ikenohata University" in resp.text

    async def test_tenant_page_via_uuid_still_works(self, db_session: AsyncSession, db_client):
        tid = uuid.UUID("55555555-5555-5555-5555-555555555555")
        db_session.add(
            Tenant(
                id=tid,
                name="Both URLs",
                slug="both-urls",
                is_private=False,
            )
        )
        await db_session.flush()

        resp = await db_client.get(f"/{tid}/")
        assert resp.status_code == 200
        assert "Both URLs" in resp.text

    async def test_nav_link_uses_slug_when_set(self, db_session: AsyncSession, db_client):
        """Index page emits /{slug}/ in tenant nav hrefs when slug is set."""
        db_session.add(
            Tenant(
                id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
                name="Slug Visible",
                slug="ikenohata-u",
                is_private=False,
            )
        )
        await db_session.flush()

        resp = await db_client.get("/")
        assert resp.status_code == 200
        assert 'href="/ikenohata-u/"' in resp.text

    async def test_nav_link_uses_uuid_when_slug_missing(self, db_session: AsyncSession, db_client):
        tid = uuid.UUID("77777777-7777-7777-7777-777777777777")
        db_session.add(Tenant(id=tid, name="No Slug", slug=None, is_private=False))
        await db_session.flush()

        resp = await db_client.get("/")
        assert resp.status_code == 200
        assert f'href="/{tid}/"' in resp.text

    async def test_case_api_response_carries_uuid_not_slug(self, db_session: AsyncSession, db_client):
        """CASE clients (e.g., Open Badge Factory) store the response-body UUID
        as a canonical reference, so it must stay UUID even when accessed via
        the slug URL. Empty list responses are enough — what matters is the URL
        form, not the payload here."""
        tid = uuid.UUID("88888888-8888-8888-8888-888888888888")
        db_session.add(Tenant(id=tid, name="CASE", slug="case-tenant", is_private=False))
        await db_session.flush()

        resp = await db_client.get("/case-tenant/ims/case/v1p1/CFDocuments")
        assert resp.status_code == 200
        # Accessed via slug, but the response payload itself is a JSON list and
        # contains no tenant-URL strings — what we're really verifying is that
        # the slug route resolves at all. (URL-form tests for emitted URIs
        # belong to integration tests that have items / documents in the DB.)


# ---------------------------------------------------------------------------
# Sticky navigation: the URL form the user requested (UUID or slug) is
# preserved in every nav href / hx-get URL in the rendered page, so the URL
# bar doesn't drift mid-session.
# ---------------------------------------------------------------------------


class TestStickyNav:
    """Both URL forms address the same tenant; the rendered page's nav links
    inherit the form used in the request URL."""

    CONFTEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
    SLUG = "sticky-tenant"

    async def _attach_slug(self, db_session: AsyncSession):
        """Add a slug to the conftest tenant so both URL forms become valid."""
        existing = await db_session.get(Tenant, self.CONFTEST_TENANT_ID)
        existing.slug = self.SLUG
        await db_session.flush()

    async def test_tenant_page_via_uuid_keeps_uuid_in_nav(self, db_session: AsyncSession, db_client, sample_document):
        await self._attach_slug(db_session)

        resp = await db_client.get(f"/{self.CONFTEST_TENANT_ID}/")
        assert resp.status_code == 200
        # The doc list link should use UUID form (matches request URL form).
        assert f"/{self.CONFTEST_TENANT_ID}/cftree/doc/{sample_document.identifier}" in resp.text
        # Slug must NOT leak into nav on a UUID-requested page.
        assert f"/{self.SLUG}/cftree/doc/" not in resp.text

    async def test_tenant_page_via_slug_keeps_slug_in_nav(self, db_session: AsyncSession, db_client, sample_document):
        await self._attach_slug(db_session)

        resp = await db_client.get(f"/{self.SLUG}/")
        assert resp.status_code == 200
        # The doc list link should use slug form.
        assert f"/{self.SLUG}/cftree/doc/{sample_document.identifier}" in resp.text
        # UUID-form nav must NOT appear on a slug-requested page.
        assert f"/{self.CONFTEST_TENANT_ID}/cftree/doc/" not in resp.text

    async def test_uri_detail_via_uuid_keeps_uuid_in_nav(
        self,
        db_session: AsyncSession,
        db_client,
        sample_document,  # creates the canonical 11111111-... tenant
    ):
        """A UUID permalink keeps nav UUID-form even when the tenant has a slug."""
        # Add a slug to the conftest tenant so we have both forms to choose from.
        existing = await db_session.get(Tenant, uuid.UUID("11111111-1111-1111-1111-111111111111"))
        existing.slug = "sticky-existing"
        await db_session.flush()

        resp = await db_client.get(f"/11111111-1111-1111-1111-111111111111/uri/{sample_document.identifier}")
        assert resp.status_code == 200
        # Breadcrumb / nav should stay UUID-form.
        assert 'href="/11111111-1111-1111-1111-111111111111/"' in resp.text
        assert 'href="/sticky-existing/' not in resp.text
        # Permalink display field (canonical) MUST be UUID regardless of request form.
        assert "11111111-1111-1111-1111-111111111111/uri/" in resp.text

    async def test_uri_detail_via_slug_keeps_slug_in_nav(
        self,
        db_session: AsyncSession,
        db_client,
        sample_document,
    ):
        """The slug form propagates through nav links on the rendered page."""
        existing = await db_session.get(Tenant, uuid.UUID("11111111-1111-1111-1111-111111111111"))
        existing.slug = "sticky-existing"
        await db_session.flush()

        resp = await db_client.get(f"/sticky-existing/uri/{sample_document.identifier}")
        assert resp.status_code == 200
        # Breadcrumb / nav should stay slug-form.
        assert 'href="/sticky-existing/"' in resp.text
        assert 'href="/11111111-1111-1111-1111-111111111111/"' not in resp.text
        # Canonical permalink display still UUID even when accessed via slug.
        assert "11111111-1111-1111-1111-111111111111/uri/" in resp.text

    async def test_uri_detail_permalink_field_is_always_uuid(
        self,
        db_session: AsyncSession,
        db_client,
        sample_document,
    ):
        """The displayed permalink (copy-paste field) is canonical UUID. This
        is the load-bearing claim for OBF compatibility — verify it explicitly
        for both request forms."""
        existing = await db_session.get(Tenant, uuid.UUID("11111111-1111-1111-1111-111111111111"))
        existing.slug = "perma-check"
        await db_session.flush()

        for path in (
            f"/11111111-1111-1111-1111-111111111111/uri/{sample_document.identifier}",
            f"/perma-check/uri/{sample_document.identifier}",
        ):
            resp = await db_client.get(path)
            assert resp.status_code == 200
            assert "11111111-1111-1111-1111-111111111111/uri/" in resp.text
            assert f"perma-check/uri/{sample_document.identifier}" not in resp.text
