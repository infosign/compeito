"""Tests for CLI commands (Issue #39)."""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings
from src.models.cf_document import CFDocument
from src.models.tenant import Tenant


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOC_IDENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

_CLEANUP_TABLES = [
    "cf_rubric_criterion_levels", "cf_rubric_criteria", "cf_rubrics",
    "cf_associations", "cf_items", "cf_documents",
    "cf_association_groupings", "cf_concepts", "cf_subjects",
    "cf_item_types", "cf_licenses", "tenants",
]


# ---------------------------------------------------------------------------
# Sync DB helpers (CLI tests need sync fixtures because CLI uses asyncio.run)
# ---------------------------------------------------------------------------


async def _db_exec(callback):
    """Run an async callback with a committed DB session."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            await callback(session)
            await session.commit()
        finally:
            await session.close()
    await engine.dispose()


async def _db_cleanup():
    """Delete all test data from DB."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        for table in _CLEANUP_TABLES:
            await conn.execute(text(f"DELETE FROM {table}"))
        await conn.commit()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env_docker(monkeypatch):
    """Set DATABASE_URL environment variable for Docker mode."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://case:case@db:5432/case")


@pytest.fixture
def clean_db():
    """Ensure DB is clean before and after test."""
    asyncio.run(_db_cleanup())
    yield
    asyncio.run(_db_cleanup())


@pytest.fixture
def test_tenant(clean_db):
    """Create a test tenant committed to DB."""
    async def _create(session):
        session.add(Tenant(id=TENANT_ID, name="Test Tenant", is_private=False))

    asyncio.run(_db_exec(_create))
    return TENANT_ID


@pytest.fixture
def test_document(test_tenant):
    """Create a test document committed to DB."""
    async def _create(session):
        session.add(CFDocument(
            tenant_id=TENANT_ID,
            identifier=DOC_IDENT,
            uri=f"https://example.com/uri/{DOC_IDENT}",
            title="Test Document",
            creator="Test Creator",
            language="ja",
            last_change_date_time=NOW,
        ))

    asyncio.run(_db_exec(_create))
    return DOC_IDENT


# ---------------------------------------------------------------------------
# Environment detection tests
# ---------------------------------------------------------------------------


class TestEnvironmentDetection:
    def test_no_database_url(self, runner, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from cli import cli
        result = runner.invoke(cli, ["tenant", "list"])
        assert result.exit_code == 1
        assert "DATABASE_URL" in result.output


# ---------------------------------------------------------------------------
# Tenant CRUD tests
# ---------------------------------------------------------------------------


class TestTenantCreate:
    def test_create_public(self, runner, env_docker, clean_db):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "create", "--name", "Test Create"])
        assert result.exit_code == 0
        assert "Created tenant:" in result.output
        assert "Test Create" in result.output
        assert "public" in result.output

    def test_create_private(self, runner, env_docker, clean_db):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "create", "--name", "Private", "--private"])
        assert result.exit_code == 0
        assert "private" in result.output

    def test_create_missing_name(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "create"])
        assert result.exit_code != 0


class TestTenantList:
    def test_list_empty(self, runner, env_docker, clean_db):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "list"])
        assert result.exit_code == 0
        assert "No tenants found" in result.output

    def test_list_with_tenants(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "list"])
        assert result.exit_code == 0
        assert "Test Tenant" in result.output

    def test_list_with_docs(self, runner, env_docker, test_document):
        from cli import cli
        result = runner.invoke(cli, ["tenant", "list", "--with-docs"])
        assert result.exit_code == 0
        assert "Test Tenant" in result.output
        assert "Test Document" in result.output


class TestTenantUpdate:
    def test_update_name(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", str(TENANT_ID), "--name", "New Name"],
        )
        assert result.exit_code == 0
        assert "Updated tenant:" in result.output
        assert "New Name" in result.output

    def test_update_private(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", str(TENANT_ID), "--private"],
        )
        assert result.exit_code == 0
        assert "private" in result.output

    def test_update_public(self, runner, env_docker, test_tenant):
        from cli import cli
        # First make private
        runner.invoke(
            cli, ["tenant", "update", "--tenant", str(TENANT_ID), "--private"],
        )
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", str(TENANT_ID), "--public"],
        )
        assert result.exit_code == 0
        assert "public" in result.output

    def test_update_no_options(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", str(TENANT_ID)],
        )
        assert result.exit_code == 1
        assert "At least one of" in result.output

    def test_update_private_public_conflict(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli,
            ["tenant", "update", "--tenant", str(TENANT_ID), "--private", "--public"],
        )
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_update_not_found(self, runner, env_docker, clean_db):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", fake_uuid, "--name", "X"],
        )
        assert result.exit_code == 1
        assert "Tenant not found" in result.output

    def test_update_invalid_uuid(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", "bad-uuid", "--name", "X"],
        )
        assert result.exit_code == 1
        assert "Invalid UUID format" in result.output


class TestTenantDelete:
    def test_delete_with_force(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "delete", "--tenant", str(TENANT_ID), "--force"],
        )
        assert result.exit_code == 0
        assert "Deleted tenant:" in result.output
        assert "Test Tenant" in result.output

    def test_delete_confirm_yes(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "delete", "--tenant", str(TENANT_ID)],
            input="y\n",
        )
        assert result.exit_code == 0
        assert "Deleted tenant:" in result.output

    def test_delete_confirm_no(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "delete", "--tenant", str(TENANT_ID)],
            input="N\n",
        )
        assert result.exit_code == 2
        assert "Cancelled" in result.output

    def test_delete_not_found(self, runner, env_docker, clean_db):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli, ["tenant", "delete", "--tenant", fake_uuid, "--force"],
        )
        assert result.exit_code == 1
        assert "Tenant not found" in result.output


# ---------------------------------------------------------------------------
# Doc tests
# ---------------------------------------------------------------------------


class TestDocList:
    def test_list_docs(self, runner, env_docker, test_document):
        from cli import cli
        result = runner.invoke(
            cli, ["doc", "list", "--tenant", str(TENANT_ID)],
        )
        assert result.exit_code == 0
        assert "Test Document" in result.output

    def test_list_empty(self, runner, env_docker, test_tenant):
        from cli import cli
        result = runner.invoke(
            cli, ["doc", "list", "--tenant", str(TENANT_ID)],
        )
        assert result.exit_code == 0
        assert "No documents found" in result.output

    def test_list_tenant_not_found(self, runner, env_docker, clean_db):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(cli, ["doc", "list", "--tenant", fake_uuid])
        assert result.exit_code == 1
        assert "Tenant not found" in result.output


class TestDocDelete:
    def test_delete_with_force(self, runner, env_docker, test_document):
        from cli import cli
        result = runner.invoke(
            cli,
            [
                "doc", "delete",
                "--tenant", str(TENANT_ID),
                "--doc", str(DOC_IDENT),
                "--force",
            ],
        )
        assert result.exit_code == 0
        assert "Deleted document:" in result.output
        assert "Test Document" in result.output

    def test_delete_confirm_cancel(self, runner, env_docker, test_document):
        from cli import cli
        result = runner.invoke(
            cli,
            [
                "doc", "delete",
                "--tenant", str(TENANT_ID),
                "--doc", str(DOC_IDENT),
            ],
            input="N\n",
        )
        assert result.exit_code == 2
        assert "Cancelled" in result.output

    def test_delete_doc_not_found(self, runner, env_docker, test_tenant):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli,
            [
                "doc", "delete",
                "--tenant", str(TENANT_ID),
                "--doc", fake_uuid,
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "Document not found" in result.output


# ---------------------------------------------------------------------------
# Import CSV tests
# ---------------------------------------------------------------------------


class TestImportCsv:
    def test_file_not_found(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", "/nonexistent.csv"],
        )
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_invalid_utf8(self, runner, env_docker, tmp_path):
        from cli import cli
        bad_file = tmp_path / "bad.csv"
        bad_file.write_bytes(b"\xff\xfe invalid")
        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", str(bad_file)],
        )
        assert result.exit_code == 1
        assert "CSV file is not valid UTF-8" in result.output

    def test_import_success(self, runner, env_docker, test_tenant, tmp_path):
        from cli import cli
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "#title,Test Framework\n"
            "Identifier,Full Statement,Human Coding Scheme,Parent Identifier\n"
            ",Statement 1,A-1,\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", str(csv_file)],
        )
        assert result.exit_code == 0
        assert "Imported into" in result.output

    def test_import_tenant_not_found(self, runner, env_docker, clean_db, tmp_path):
        from cli import cli
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Identifier,Full Statement\n", encoding="utf-8")
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli, ["import", "csv", "--tenant", fake_uuid, "--file", str(csv_file)],
        )
        assert result.exit_code == 1
        assert "Tenant not found" in result.output

    def test_import_doc_not_found(self, runner, env_docker, test_tenant, tmp_path):
        from cli import cli
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Identifier,Full Statement\n", encoding="utf-8")
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli,
            [
                "import", "csv",
                "--tenant", str(TENANT_ID),
                "--doc", fake_uuid,
                "--file", str(csv_file),
            ],
        )
        assert result.exit_code == 1
        assert "Document not found" in result.output


# ---------------------------------------------------------------------------
# Export CSV tests
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_export_success(self, runner, env_docker, test_document, tmp_path):
        from cli import cli
        out_file = tmp_path / "out.csv"
        result = runner.invoke(
            cli,
            [
                "export", "csv",
                "--tenant", str(TENANT_ID),
                "--doc", str(DOC_IDENT),
                "--file", str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert "Exported" in result.output
        assert out_file.exists()

    def test_export_opensalt_not_supported(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli,
            [
                "export", "csv",
                "--tenant", str(TENANT_ID),
                "--doc", str(DOC_IDENT),
                "--file", "/tmp/out.csv",
                "--format", "opensalt",
            ],
        )
        assert result.exit_code == 1
        assert "opensalt format is not yet supported" in result.output

    def test_export_invalid_format(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli,
            [
                "export", "csv",
                "--tenant", str(TENANT_ID),
                "--doc", str(DOC_IDENT),
                "--file", "/tmp/out.csv",
                "--format", "xml",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid format: 'xml'" in result.output

    def test_export_tenant_not_found(self, runner, env_docker, clean_db, tmp_path):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli,
            [
                "export", "csv",
                "--tenant", fake_uuid,
                "--doc", str(DOC_IDENT),
                "--file", str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 1
        assert "Tenant not found" in result.output

    def test_export_doc_not_found(self, runner, env_docker, test_tenant, tmp_path):
        from cli import cli
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        result = runner.invoke(
            cli,
            [
                "export", "csv",
                "--tenant", str(TENANT_ID),
                "--doc", fake_uuid,
                "--file", str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 1
        assert "Document not found" in result.output


# ---------------------------------------------------------------------------
# DB migrate
# ---------------------------------------------------------------------------


class TestDbMigrate:
    def test_migrate_runs_alembic(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(cli, ["db", "migrate"])
        assert result.exit_code == 0
        assert "Migration complete" in result.output


# ---------------------------------------------------------------------------
# Cache invalidate
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# UUID validation
# ---------------------------------------------------------------------------


class TestUuidValidation:
    def test_invalid_tenant_uuid_on_update(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli, ["tenant", "update", "--tenant", "not-a-uuid", "--name", "X"],
        )
        assert result.exit_code == 1
        assert "Invalid UUID format" in result.output

    def test_invalid_doc_uuid_on_delete(self, runner, env_docker):
        from cli import cli
        result = runner.invoke(
            cli,
            [
                "doc", "delete",
                "--tenant", str(TENANT_ID),
                "--doc", "bad-uuid",
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid UUID format" in result.output
