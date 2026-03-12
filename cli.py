"""COMPEITO CLI — tenant/doc management, import/export, db migrate."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.i18n import detect_lang_from_env, get_translator

console = Console(stderr=True)
err_console = Console(stderr=True, style="bold red")

# Module-level translator for Click decorator help texts (evaluated at import time)
t = get_translator(detect_lang_from_env(), cli=True)


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _check_db():
    """Verify DATABASE_URL is set or exit."""
    import os

    if not os.environ.get("DATABASE_URL"):
        err_console.print(t("err_env_required"))
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


async def _get_session():
    """Create an async DB session for CLI use."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from src.config import settings

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
    await engine.dispose()


# ---------------------------------------------------------------------------
# UUID validation helper
# ---------------------------------------------------------------------------

def _parse_uuid(value: str, label: str = "UUID") -> uuid.UUID:
    """Parse a UUID string or exit with error."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        err_console.print(t("err_invalid_uuid", value=value))
        raise SystemExit(1)


def _visibility(is_private: bool) -> str:
    """Return localized visibility label."""
    return t("visibility_private") if is_private else t("visibility_public")


# ---------------------------------------------------------------------------
# Click groups
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """COMPEITO CLI."""
    pass


cli.help = t("cli_description")


@cli.group()
def tenant():
    """Tenant management commands."""
    pass


tenant.help = t("tenant_group")


@cli.group()
def doc():
    """Document management commands."""
    pass


doc.help = t("doc_group")


@cli.group(name="import")
def import_group():
    """Import commands."""
    pass


import_group.help = t("import_group")


@cli.group(name="export")
def export_group():
    """Export commands."""
    pass


export_group.help = t("export_group")


@cli.group()
def db():
    """Database commands."""
    pass


db.help = t("db_group")




# ---------------------------------------------------------------------------
# tenant create
# ---------------------------------------------------------------------------

@tenant.command("create", help=t("cmd_tenant_create"))
@click.option("--name", required=True, help=t("help_tenant_name"))
@click.option("--private", "is_private", is_flag=True, default=False, help=t("help_make_private"))
def tenant_create(name: str, is_private: bool):
    """Create a new tenant."""
    _check_db()

    async def _run_create():
        from src.models.tenant import Tenant

        async for session in _get_session():
            tenant_obj = Tenant(name=name, is_private=is_private)
            session.add(tenant_obj)
            await session.flush()
            console.print(
                t("msg_created_tenant",
                  id=str(tenant_obj.id), name=tenant_obj.name,
                  visibility=_visibility(tenant_obj.is_private)),
            )
            await session.commit()

    _run(_run_create())


# ---------------------------------------------------------------------------
# tenant list
# ---------------------------------------------------------------------------

@tenant.command("list", help=t("cmd_tenant_list"))
@click.option("--with-docs", is_flag=True, default=False, help=t("help_show_docs"))
def tenant_list(with_docs: bool):
    """List all tenants."""
    _check_db()

    async def _run_list():
        from sqlalchemy import func, select

        from src.models.cf_document import CFDocument
        from src.models.cf_item import CFItem
        from src.models.tenant import Tenant

        async for session in _get_session():
            result = await session.execute(
                select(Tenant).order_by(Tenant.name.asc(), Tenant.id.asc()),
            )
            tenants = list(result.scalars().all())

            if not tenants:
                console.print(t("msg_no_tenants"))
                return

            if not with_docs:
                table = Table()
                table.add_column("UUID")
                table.add_column("NAME")
                table.add_column("VISIBILITY")
                table.add_column("CREATED")
                for tenant_obj in tenants:
                    table.add_row(
                        str(tenant_obj.id),
                        tenant_obj.name,
                        _visibility(tenant_obj.is_private),
                        tenant_obj.created_at.strftime("%Y-%m-%d") if tenant_obj.created_at else "",
                    )
                console.print(table)
            else:
                # With docs: tree-style output
                for tenant_obj in tenants:
                    visibility = _visibility(tenant_obj.is_private)
                    console.print(f"{tenant_obj.id}  {tenant_obj.name}  {visibility}")
                    # Fetch documents with item counts
                    stmt = (
                        select(
                            CFDocument.identifier,
                            CFDocument.title,
                            func.count(CFItem.id).label("item_count"),
                        )
                        .outerjoin(CFItem, CFItem.cf_document_id == CFDocument.id)
                        .where(CFDocument.tenant_id == tenant_obj.id)
                        .group_by(CFDocument.id)
                        .order_by(CFDocument.title.asc(), CFDocument.identifier.asc())
                    )
                    docs_result = await session.execute(stmt)
                    docs = list(docs_result.all())
                    for i, (doc_ident, doc_title, item_count) in enumerate(docs):
                        prefix = "└─" if i == len(docs) - 1 else "├─"
                        console.print(
                            f"  {prefix} {doc_ident}  {doc_title}  "
                            f"({item_count} {t('items_suffix')})",
                        )

    _run(_run_list())


# ---------------------------------------------------------------------------
# tenant update
# ---------------------------------------------------------------------------

@tenant.command("update", help=t("cmd_tenant_update"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--name", default=None, help=t("help_new_name"))
@click.option("--private", "set_private", is_flag=True, default=False, help=t("help_set_private"))
@click.option("--public", "set_public", is_flag=True, default=False, help=t("help_set_public"))
def tenant_update(tenant_id: str, name: str | None, set_private: bool, set_public: bool):
    """Update a tenant."""
    _check_db()

    if set_private and set_public:
        err_console.print(t("err_private_public_exclusive"))
        raise SystemExit(1)

    if not name and not set_private and not set_public:
        err_console.print(t("err_update_requires_option"))
        raise SystemExit(1)

    tid = _parse_uuid(tenant_id)

    async def _run_update():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async for session in _get_session():
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            tenant_obj = result.scalar_one_or_none()
            if tenant_obj is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            if name is not None:
                tenant_obj.name = name
            if set_private:
                tenant_obj.is_private = True
            if set_public:
                tenant_obj.is_private = False

            await session.flush()
            console.print(
                t("msg_updated_tenant",
                  id=str(tenant_obj.id), name=tenant_obj.name,
                  visibility=_visibility(tenant_obj.is_private)),
            )
            await session.commit()

    _run(_run_update())


# ---------------------------------------------------------------------------
# tenant delete
# ---------------------------------------------------------------------------

@tenant.command("delete", help=t("cmd_tenant_delete"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--force", is_flag=True, default=False, help=t("help_skip_confirm"))
def tenant_delete(tenant_id: str, force: bool):
    """Delete a tenant and all its data."""
    _check_db()
    tid = _parse_uuid(tenant_id)

    async def _run_delete():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async for session in _get_session():
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            tenant_obj = result.scalar_one_or_none()
            if tenant_obj is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            if not force:
                answer = click.prompt(
                    t("prompt_delete_tenant",
                      name=tenant_obj.name, id=str(tenant_obj.id)),
                    default="N",
                    show_default=False,
                )
                if answer.lower() not in ("y", "yes"):
                    console.print(t("msg_cancelled"))
                    raise SystemExit(2)

            name = tenant_obj.name
            tid_str = str(tenant_obj.id)
            await session.delete(tenant_obj)
            await session.commit()
            console.print(t("msg_deleted_tenant", id=tid_str, name=name))

    _run(_run_delete())


# ---------------------------------------------------------------------------
# doc list
# ---------------------------------------------------------------------------

@doc.command("list", help=t("cmd_doc_list"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
def doc_list(tenant_id: str):
    """List documents in a tenant."""
    _check_db()
    tid = _parse_uuid(tenant_id)

    async def _run_list():
        from sqlalchemy import func, select

        from src.models.cf_document import CFDocument
        from src.models.cf_item import CFItem
        from src.models.tenant import Tenant

        async for session in _get_session():
            # Check tenant exists
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            stmt = (
                select(
                    CFDocument.identifier,
                    CFDocument.title,
                    func.count(CFItem.id).label("item_count"),
                    CFDocument.last_change_date_time,
                )
                .outerjoin(CFItem, CFItem.cf_document_id == CFDocument.id)
                .where(CFDocument.tenant_id == tid)
                .group_by(CFDocument.id)
                .order_by(CFDocument.title.asc(), CFDocument.identifier.asc())
            )
            docs_result = await session.execute(stmt)
            docs = list(docs_result.all())

            if not docs:
                console.print(t("msg_no_documents"))
                return

            table = Table()
            table.add_column("UUID")
            table.add_column("TITLE")
            table.add_column("ITEMS", justify="right")
            table.add_column("UPDATED")
            for doc_ident, doc_title, item_count, last_change in docs:
                table.add_row(
                    str(doc_ident),
                    doc_title,
                    str(item_count),
                    last_change.strftime("%Y-%m-%d") if last_change else "",
                )
            console.print(table)

    _run(_run_list())


# ---------------------------------------------------------------------------
# doc delete
# ---------------------------------------------------------------------------

@doc.command("delete", help=t("cmd_doc_delete"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--force", is_flag=True, default=False, help=t("help_skip_confirm"))
def doc_delete(tenant_id: str, doc_id: str, force: bool):
    """Delete a document and its items/associations."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    async def _run_delete():
        from sqlalchemy import func, select

        from src.models.cf_document import CFDocument
        from src.models.cf_item import CFItem
        from src.models.tenant import Tenant

        async for session in _get_session():
            # Check tenant
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            # Find document
            result = await session.execute(
                select(CFDocument).where(
                    CFDocument.tenant_id == tid,
                    CFDocument.identifier == did,
                ),
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                err_console.print(t("err_doc_not_found", value=str(did)))
                raise SystemExit(1)

            # Get item count for prompt
            count_result = await session.execute(
                select(func.count(CFItem.id)).where(CFItem.cf_document_id == doc.id),
            )
            item_count = count_result.scalar()

            if not force:
                answer = click.prompt(
                    t("prompt_delete_document",
                      title=doc.title, id=str(doc.identifier),
                      count=str(item_count)),
                    default="N",
                    show_default=False,
                )
                if answer.lower() not in ("y", "yes"):
                    console.print(t("msg_cancelled"))
                    raise SystemExit(2)

            title = doc.title
            ident_str = str(doc.identifier)
            await session.delete(doc)
            await session.commit()
            console.print(t("msg_deleted_document", id=ident_str, title=title))

    _run(_run_delete())


# ---------------------------------------------------------------------------
# import csv
# ---------------------------------------------------------------------------

@import_group.command("csv", help=t("cmd_import_csv"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(), help=t("help_csv_file"))
@click.option("--doc", "doc_id", default=None, help=t("help_doc_uuid_update"))
@click.option("--doc-title", default=None, help=t("help_doc_title"))
@click.option("--doc-version", default=None, help=t("help_doc_version"))
def import_csv_cmd(
    tenant_id: str, file_path: str, doc_id: str | None,
    doc_title: str | None, doc_version: str | None,
):
    """Import items from a CSV file."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id) if doc_id else None

    # Validate file
    p = Path(file_path)
    if not p.exists():
        err_console.print(t("err_file_not_found", value=file_path))
        raise SystemExit(1)
    try:
        csv_data = p.read_bytes()
    except PermissionError:
        err_console.print(t("err_file_unreadable", value=file_path))
        raise SystemExit(1)

    # Check UTF-8
    try:
        csv_data.decode("utf-8")
    except UnicodeDecodeError:
        err_console.print(t("err_csv_not_utf8"))
        raise SystemExit(1)

    async def _run_import():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.csv_import_service import import_csv

        async for session in _get_session():
            # Check tenant
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            # Check doc if specified
            if did is not None:
                result = await session.execute(
                    select(CFDocument).where(
                        CFDocument.tenant_id == tid,
                        CFDocument.identifier == did,
                    ),
                )
                if result.scalar_one_or_none() is None:
                    err_console.print(t("err_doc_not_found", value=str(did)))
                    raise SystemExit(1)

            with console.status(t("msg_importing_csv")):
                report = await import_csv(
                    session, tid, csv_data,
                    doc_identifier=did,
                    doc_title=doc_title,
                    doc_version=doc_version,
                )
                await session.commit()

            console.print(
                t("msg_imported_into",
                  title=report.document_title,
                  id=str(report.document_identifier)),
            )
            console.print(
                t("msg_items_summary",
                  created=str(report.items_created),
                  updated=str(report.items_updated),
                  skipped=str(report.items_skipped)),
            )
            console.print(
                t("msg_assoc_summary_short",
                  created=str(report.associations_created)),
            )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]Warning: {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# import case-url
# ---------------------------------------------------------------------------

@import_group.command("case-url", help=t("cmd_import_case_url"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--url", required=True, help=t("help_case_url"))
@click.option("--doc", "doc_id", default=None, help=t("help_doc_uuid_update"))
def import_case_url(tenant_id: str, url: str, doc_id: str | None):
    """Import from an external CASE source."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id) if doc_id else None

    async def _run_import():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.case_import_service import import_case_package

        async for session in _get_session():
            # Check tenant
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            # Check doc if specified
            if did is not None:
                result = await session.execute(
                    select(CFDocument).where(
                        CFDocument.tenant_id == tid,
                        CFDocument.identifier == did,
                    ),
                )
                if result.scalar_one_or_none() is None:
                    err_console.print(t("err_doc_not_found", value=str(did)))
                    raise SystemExit(1)

            with console.status(t("msg_importing_case")):
                report = await import_case_package(
                    session, tid, url,
                    doc_identifier=did,
                )
                await session.commit()

            console.print(
                t("msg_imported",
                  title=report.document_title,
                  id=str(report.document_identifier)),
            )
            console.print(
                t("msg_items_summary",
                  created=str(report.items_created),
                  updated=str(report.items_updated),
                  skipped=str(report.items_skipped)),
            )
            console.print(
                t("msg_assoc_summary",
                  created=str(report.associations_created),
                  updated=str(report.associations_updated),
                  skipped=str(report.associations_skipped)),
            )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]Warning: {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# export csv
# ---------------------------------------------------------------------------

@export_group.command("csv", help=t("cmd_export_csv"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(), help=t("help_output_file"))
@click.option(
    "--format", "fmt", default="custom",
    help=t("help_export_format"),
)
def export_csv_cmd(tenant_id: str, doc_id: str, file_path: str, fmt: str):
    """Export a document to CSV."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    # Validate format
    if fmt not in ("custom", "opensalt"):
        err_console.print(t("err_invalid_format", value=fmt))
        raise SystemExit(1)

    if fmt == "opensalt":
        err_console.print(t("err_opensalt_not_supported"))
        raise SystemExit(1)

    # Check output path is writable
    out = Path(file_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        # Test writability
        out.touch()
        out.unlink()
    except (PermissionError, OSError):
        err_console.print(t("err_file_unwritable", value=file_path))
        raise SystemExit(1)

    async def _run_export():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.csv_export_service import export_csv

        async for session in _get_session():
            # Check tenant
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            # Check document
            result = await session.execute(
                select(CFDocument).where(
                    CFDocument.tenant_id == tid,
                    CFDocument.identifier == did,
                ),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_doc_not_found", value=str(did)))
                raise SystemExit(1)

            with console.status(t("msg_exporting_csv")):
                csv_str = await export_csv(session, tid, did)

            out.write_text(csv_str, encoding="utf-8")
            # Count actual data rows (exclude meta lines starting with #)
            lines = csv_str.strip().split("\n")
            data_lines = [
                l for l in lines
                if l and not l.startswith("#") and not l.startswith("Identifier,")
            ]
            console.print(
                t("msg_exported", count=str(len(data_lines)), path=file_path),
            )

    _run(_run_export())


# ---------------------------------------------------------------------------
# db migrate
# ---------------------------------------------------------------------------

@db.command("migrate", help=t("cmd_db_migrate"))
def db_migrate():
    """Run database migrations (alembic upgrade head)."""
    _check_db()

    import subprocess

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        console.print(result.stdout.rstrip())
    if result.stderr:
        console.print(result.stderr.rstrip())
    if result.returncode != 0:
        raise SystemExit(1)
    console.print(f"[green]{t('msg_migration_complete')}[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
