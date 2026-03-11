import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings
from src.database import get_session
from src.main import app
from src.models.cf_document import CFDocument
from src.models.tenant import Tenant

# Dedicated test engine with NullPool to avoid connection pool issues
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Provide a DB session for integration tests. Cleans up after each test."""
    async with test_engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            # Clean up all test data in reverse FK order
            await conn.execute(text("DELETE FROM cf_rubric_criterion_levels"))
            await conn.execute(text("DELETE FROM cf_rubric_criteria"))
            await conn.execute(text("DELETE FROM cf_rubrics"))
            await conn.execute(text("DELETE FROM cf_associations"))
            await conn.execute(text("DELETE FROM cf_items"))
            await conn.execute(text("DELETE FROM cf_documents"))
            await conn.execute(text("DELETE FROM cf_association_groupings"))
            await conn.execute(text("DELETE FROM cf_concepts"))
            await conn.execute(text("DELETE FROM cf_subjects"))
            await conn.execute(text("DELETE FROM cf_item_types"))
            await conn.execute(text("DELETE FROM cf_licenses"))
            await conn.execute(text("DELETE FROM tenants"))
            await conn.commit()


@pytest.fixture
async def db_client(db_session: AsyncSession) -> AsyncClient:
    """HTTP client with DB session override for integration tests."""

    async def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    t = Tenant(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Test Tenant",
        is_private=False,
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def sample_document(db_session: AsyncSession, tenant: Tenant) -> CFDocument:
    """Create a sample CFDocument for testing."""
    doc = CFDocument(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        identifier=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        uri="https://example.com/uri/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        title="Test Document",
        creator="Test Creator",
        language="ja",
        last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    return doc
