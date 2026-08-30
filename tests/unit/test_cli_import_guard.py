"""dry-run, the destructive-change guard, and the validation report (B6).

The guard exists because of a specific accident: re-importing a CSV that omits
some items silently deletes those items' links (the document-level rebuild
deletes every association of the present types and re-creates only what the file
still mentions). Nothing stopped that before; the report merely counted the
deletions, which happen on every update anyway.

Design: docs/dev/designs/import-dry-run-and-ai-guide.md.
"""

import asyncio
import json
import uuid

import pytest
from sqlalchemy import func, select

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from tests.unit.test_cli import (  # noqa: F401
    _db_exec,
    clean_db,
    env_docker,
    runner,
    test_tenant,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

HEADER = (
    "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,"
    "educationLevel,conceptKeywords,abbreviatedStatement,alternativeLabel,notes,language,"
    "listEnumeration,license,statusStartDate,statusEndDate\n"
)
DOC_IDENT = uuid.UUID("eeee0000-0000-0000-0000-00000000000a")
PARENT = uuid.UUID("eeee0000-0000-0000-0000-00000000000b")
CHILD = uuid.UUID("eeee0000-0000-0000-0000-00000000000c")


def _csv(rows: str) -> str:
    return f"#identifier,{DOC_IDENT}\n#title,Guard\n{HEADER}{rows}"


FULL = _csv(f"{PARENT},Parent,,,,,,,,,,,,,,\n{CHILD},Child,,{PARENT},10,,,,,,,,,,,\n")
# The child is gone: its isChildOf will be deleted and never re-created.
PARTIAL = _csv(f"{PARENT},Parent,,,,,,,,,,,,,,\n")


def _write(tmp_path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def _assoc_count() -> int:
    found = []

    async def _count(session):
        doc = (await session.execute(select(CFDocument).where(CFDocument.identifier == DOC_IDENT))).scalar_one()
        found.append(
            (
                await session.execute(
                    select(func.count(CFAssociation.id)).where(CFAssociation.cf_document_id == doc.id)
                )
            ).scalar()
        )

    asyncio.run(_db_exec(_count))
    return found[0]


@pytest.fixture
def seeded(runner, env_docker, test_tenant, tmp_path):  # noqa: F811
    """A document with a parent and a child, so a partial re-import loses a link."""
    from cli import cli

    result = runner.invoke(
        cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(tmp_path, "full.csv", FULL)]
    )
    assert result.exit_code == 0, result.output
    assert _assoc_count() == 2  # parent + child, both isChildOf
    return tmp_path


class TestDryRun:
    def test_nothing_is_committed(self, runner, seeded):  # noqa: F811
        from cli import cli

        before = _assoc_count()
        result = runner.invoke(
            cli,
            [
                "import",
                "csv",
                "--tenant",
                str(TENANT_ID),
                "--file",
                _write(seeded, "partial.csv", PARTIAL),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert _assoc_count() == before, "a dry run must leave the database untouched"

    def test_reports_what_would_change(self, runner, seeded):  # noqa: F811
        """The numbers come from a real run, not an estimate."""
        from cli import cli

        report_path = seeded / "report.json"
        runner.invoke(
            cli,
            [
                "import",
                "csv",
                "--tenant",
                str(TENANT_ID),
                "--file",
                _write(seeded, "partial.csv", PARTIAL),
                "--dry-run",
                "--report",
                str(report_path),
            ],
        )
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["dryRun"] is True
        assert payload["destructive"]["lostAssociations"] == 1
        assert payload["destructive"]["lostAssociationsSample"][0]["associationType"] == "isChildOf"
        assert "lost_associations" in [i["code"] for i in payload["issues"]]


class TestDestructiveGuard:
    def test_non_interactive_refuses(self, runner, seeded):  # noqa: F811
        """CliRunner has no tty, which is exactly the automation case."""
        from cli import cli

        before = _assoc_count()
        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(seeded, "p.csv", PARTIAL)]
        )
        assert result.exit_code == 1
        # Not just any failure: falling through to the prompt would abort on EOF
        # with the same exit code but no explanation of what to do next.
        assert "--yes" in result.output and "--dry-run" in result.output
        assert _assoc_count() == before, "refusing must roll back, not half-apply"

    def test_yes_approves(self, runner, seeded):  # noqa: F811
        from cli import cli

        result = runner.invoke(
            cli,
            ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(seeded, "p.csv", PARTIAL), "--yes"],
        )
        assert result.exit_code == 0
        assert _assoc_count() == 1, "the child's link is gone, as approved"

    def test_sample_of_lost_links_is_shown(self, runner, seeded):  # noqa: F811
        """Approving blind is not much better than not asking."""
        from cli import cli

        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(seeded, "p.csv", PARTIAL)]
        )
        assert "isChildOf" in result.output
        assert str(CHILD) in result.output

    def test_reordering_is_not_destructive(self, runner, seeded):  # noqa: F811
        """The rebuild deletes and re-creates every link on each update, so a
        raw delete count would fire here. Only the net loss counts."""
        from cli import cli

        reordered = _csv(f"{PARENT},Parent,,,,,,,,,,,,,,\n{CHILD},Child renamed,,{PARENT},20,,,,,,,,,,,\n")
        result = runner.invoke(
            cli,
            ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(seeded, "re.csv", reordered)],
        )
        assert result.exit_code == 0, result.output
        assert _assoc_count() == 2

    def test_unchanged_reimport_is_not_destructive(self, runner, seeded):  # noqa: F811
        from cli import cli

        result = runner.invoke(
            cli, ["import", "csv", "--tenant", str(TENANT_ID), "--file", _write(seeded, "again.csv", FULL)]
        )
        assert result.exit_code == 0, result.output
        assert _assoc_count() == 2


class TestReportContents:
    def test_written_on_a_real_import_too(self, runner, seeded):  # noqa: F811
        from cli import cli

        report_path = seeded / "ok.json"
        runner.invoke(
            cli,
            [
                "import",
                "csv",
                "--tenant",
                str(TENANT_ID),
                "--file",
                _write(seeded, "again.csv", FULL),
                "--report",
                str(report_path),
            ],
        )
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["dryRun"] is False
        assert payload["counts"]["itemsUpdated"] == 2
        assert payload["destructive"]["total"] == 0

    def test_warnings_are_never_dropped(self, runner, seeded):  # noqa: F811
        """Unclassified warnings still reach the file, or the report would be a
        lossy view of the run."""
        from cli import cli

        report_path = seeded / "warn.json"
        broken = _csv(f"{PARENT},Parent,,,,,,,,,,,,,,not-a-date\n")
        runner.invoke(
            cli,
            [
                "import",
                "csv",
                "--tenant",
                str(TENANT_ID),
                "--file",
                _write(seeded, "broken.csv", broken),
                "--dry-run",
                "--report",
                str(report_path),
            ],
        )
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert any("Invalid statusEndDate" in w for w in payload["warnings"])
        assert len(payload["issues"]) == len(set(i["message"] for i in payload["issues"]))
