"""CASE Server CLI — tenant/doc management, import/export, db migrate."""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console(stderr=True)
err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _detect_mode() -> str:
    """Detect execution mode from environment variables.

    Returns "docker" or raises SystemExit on misconfiguration.
    AWS mode is Phase 2 — currently only Docker mode is supported.
    """
    has_db = bool(os.environ.get("DATABASE_URL"))
    has_admin_url = bool(os.environ.get("CASE_ADMIN_URL"))
    has_admin_key = bool(os.environ.get("CASE_ADMIN_KEY"))

    if has_db:
        if has_admin_url or has_admin_key:
            console.print(
                "[yellow]Warning: DATABASE_URL and CASE_ADMIN_URL/KEY both set; "
                "using DATABASE_URL (Docker mode)[/yellow]",
            )
        return "docker"

    if has_admin_url and has_admin_key:
        err_console.print("AWS mode is not yet supported in Phase 1")
        raise SystemExit(1)

    if has_admin_url or has_admin_key:
        err_console.print(
            "CASE_ADMIN_URL and CASE_ADMIN_KEY must both be set",
        )
        raise SystemExit(1)

    err_console.print(
        "DATABASE_URL or CASE_ADMIN_URL+CASE_ADMIN_KEY must be set",
    )
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
        err_console.print(f"Invalid UUID format: '{value}'")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Click groups
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """CASE Server CLI."""
    pass


@cli.group()
def tenant():
    """Tenant management commands."""
    pass


@cli.group()
def doc():
    """Document management commands."""
    pass


@cli.group(name="import")
def import_group():
    """Import commands."""
    pass


@cli.group(name="export")
def export_group():
    """Export commands."""
    pass


@cli.group()
def db():
    """Database commands."""
    pass


@cli.group()
def cache():
    """Cache commands."""
    pass


# ---------------------------------------------------------------------------
# tenant create
# ---------------------------------------------------------------------------

@tenant.command("create")
@click.option("--name", required=True, help="Tenant name")
@click.option("--private", "is_private", is_flag=True, default=False, help="Make tenant private")
def tenant_create(name: str, is_private: bool):
    """Create a new tenant."""
    _detect_mode()

    async def _run_create():
        from src.models.tenant import Tenant

        async for session in _get_session():
            t = Tenant(name=name, is_private=is_private)
            session.add(t)
            await session.flush()
            visibility = "private" if t.is_private else "public"
            console.print(f"Created tenant: {t.id} ({t.name}, {visibility})")
            await session.commit()

    _run(_run_create())


# ---------------------------------------------------------------------------
# tenant list
# ---------------------------------------------------------------------------

@tenant.command("list")
@click.option("--with-docs", is_flag=True, default=False, help="Show documents under each tenant")
def tenant_list(with_docs: bool):
    """List all tenants."""
    _detect_mode()

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
                console.print("No tenants found.")
                return

            if not with_docs:
                table = Table()
                table.add_column("UUID")
                table.add_column("NAME")
                table.add_column("VISIBILITY")
                table.add_column("CREATED")
                for t in tenants:
                    table.add_row(
                        str(t.id),
                        t.name,
                        "private" if t.is_private else "public",
                        t.created_at.strftime("%Y-%m-%d") if t.created_at else "",
                    )
                console.print(table)
            else:
                # With docs: tree-style output
                for t in tenants:
                    visibility = "private" if t.is_private else "public"
                    console.print(f"{t.id}  {t.name}  {visibility}")
                    # Fetch documents with item counts
                    stmt = (
                        select(
                            CFDocument.identifier,
                            CFDocument.title,
                            func.count(CFItem.id).label("item_count"),
                        )
                        .outerjoin(CFItem, CFItem.cf_document_id == CFDocument.id)
                        .where(CFDocument.tenant_id == t.id)
                        .group_by(CFDocument.id)
                        .order_by(CFDocument.title.asc(), CFDocument.identifier.asc())
                    )
                    docs_result = await session.execute(stmt)
                    docs = list(docs_result.all())
                    for i, (doc_ident, doc_title, item_count) in enumerate(docs):
                        prefix = "└─" if i == len(docs) - 1 else "├─"
                        console.print(
                            f"  {prefix} {doc_ident}  {doc_title}  ({item_count} items)",
                        )

    _run(_run_list())


# ---------------------------------------------------------------------------
# tenant update
# ---------------------------------------------------------------------------

@tenant.command("update")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--name", default=None, help="New tenant name")
@click.option("--private", "set_private", is_flag=True, default=False, help="Set tenant to private")
@click.option("--public", "set_public", is_flag=True, default=False, help="Set tenant to public")
def tenant_update(tenant_id: str, name: str | None, set_private: bool, set_public: bool):
    """Update a tenant."""
    _detect_mode()

    if set_private and set_public:
        err_console.print("--private and --public are mutually exclusive")
        raise SystemExit(1)

    if not name and not set_private and not set_public:
        err_console.print(
            "At least one of --name, --private, or --public is required",
        )
        raise SystemExit(1)

    tid = _parse_uuid(tenant_id)

    async def _run_update():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async for session in _get_session():
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            t = result.scalar_one_or_none()
            if t is None:
                err_console.print(f"Tenant not found: '{tid}'")
                raise SystemExit(1)

            if name is not None:
                t.name = name
            if set_private:
                t.is_private = True
            if set_public:
                t.is_private = False

            await session.flush()
            visibility = "private" if t.is_private else "public"
            console.print(f"Updated tenant: {t.id} ({t.name}, {visibility})")
            await session.commit()

    _run(_run_update())


# ---------------------------------------------------------------------------
# tenant delete
# ---------------------------------------------------------------------------

@tenant.command("delete")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation prompt")
def tenant_delete(tenant_id: str, force: bool):
    """Delete a tenant and all its data."""
    _detect_mode()
    tid = _parse_uuid(tenant_id)

    async def _run_delete():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async for session in _get_session():
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            t = result.scalar_one_or_none()
            if t is None:
                err_console.print(f"Tenant not found: '{tid}'")
                raise SystemExit(1)

            if not force:
                answer = click.prompt(
                    f"Delete tenant '{t.name}' ({t.id})? "
                    "This will delete all documents and items. [y/N]",
                    default="N",
                    show_default=False,
                )
                if answer.lower() not in ("y", "yes"):
                    console.print("Cancelled.")
                    raise SystemExit(2)

            name = t.name
            tid_str = str(t.id)
            await session.delete(t)
            await session.commit()
            console.print(f"Deleted tenant: {tid_str} ({name})")

    _run(_run_delete())


# ---------------------------------------------------------------------------
# doc list
# ---------------------------------------------------------------------------

@doc.command("list")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
def doc_list(tenant_id: str):
    """List documents in a tenant."""
    _detect_mode()
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
                err_console.print(f"Tenant not found: '{tid}'")
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
                console.print("No documents found.")
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

@doc.command("delete")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--doc", "doc_id", required=True, help="Document UUID")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation prompt")
def doc_delete(tenant_id: str, doc_id: str, force: bool):
    """Delete a document and its items/associations."""
    _detect_mode()
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
                err_console.print(f"Tenant not found: '{tid}'")
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
                err_console.print(f"Document not found: '{did}'")
                raise SystemExit(1)

            # Get item count for prompt
            count_result = await session.execute(
                select(func.count(CFItem.id)).where(CFItem.cf_document_id == doc.id),
            )
            item_count = count_result.scalar()

            if not force:
                answer = click.prompt(
                    f"Delete document '{doc.title}' ({doc.identifier}, "
                    f"{item_count} items)? [y/N]",
                    default="N",
                    show_default=False,
                )
                if answer.lower() not in ("y", "yes"):
                    console.print("Cancelled.")
                    raise SystemExit(2)

            title = doc.title
            ident_str = str(doc.identifier)
            await session.delete(doc)
            await session.commit()
            console.print(f"Deleted document: {ident_str} ({title})")

    _run(_run_delete())


# ---------------------------------------------------------------------------
# import csv
# ---------------------------------------------------------------------------

@import_group.command("csv")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--file", "file_path", required=True, type=click.Path(), help="CSV file path")
@click.option("--doc", "doc_id", default=None, help="Document UUID (for update)")
@click.option("--doc-title", default=None, help="Document title")
@click.option("--doc-version", default=None, help="Document version")
def import_csv_cmd(
    tenant_id: str, file_path: str, doc_id: str | None,
    doc_title: str | None, doc_version: str | None,
):
    """Import items from a CSV file."""
    _detect_mode()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id) if doc_id else None

    # Validate file
    p = Path(file_path)
    if not p.exists():
        err_console.print(f"File not found: '{file_path}'")
        raise SystemExit(1)
    try:
        csv_data = p.read_bytes()
    except PermissionError:
        err_console.print(f"Cannot read file: '{file_path}'")
        raise SystemExit(1)

    # Check UTF-8
    try:
        csv_data.decode("utf-8")
    except UnicodeDecodeError:
        err_console.print("CSV file is not valid UTF-8")
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
                err_console.print(f"Tenant not found: '{tid}'")
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
                    err_console.print(f"Document not found: '{did}'")
                    raise SystemExit(1)

            with console.status("Importing CSV..."):
                report = await import_csv(
                    session, tid, csv_data,
                    doc_identifier=did,
                    doc_title=doc_title,
                    doc_version=doc_version,
                )
                await session.commit()

            console.print(
                f"Imported into '{report.document_title}' "
                f"({report.document_identifier})",
            )
            console.print(
                f"  Items: {report.items_created} created, "
                f"{report.items_updated} updated, "
                f"{report.items_skipped} skipped",
            )
            console.print(f"  Associations: {report.associations_created} created")
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]Warning: {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# import case-url
# ---------------------------------------------------------------------------

@import_group.command("case-url")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--url", required=True, help="CASE API URL or CFPackage URL")
@click.option("--doc", "doc_id", default=None, help="Document UUID (for update)")
def import_case_url(tenant_id: str, url: str, doc_id: str | None):
    """Import from an external CASE source."""
    _detect_mode()
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
                err_console.print(f"Tenant not found: '{tid}'")
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
                    err_console.print(f"Document not found: '{did}'")
                    raise SystemExit(1)

            with console.status("Importing from CASE source..."):
                report = await import_case_package(
                    session, tid, url,
                    doc_identifier=did,
                )
                await session.commit()

            console.print(
                f"Imported '{report.document_title}' "
                f"({report.document_identifier})",
            )
            console.print(
                f"  Items: {report.items_created} created, "
                f"{report.items_updated} updated, "
                f"{report.items_skipped} skipped",
            )
            console.print(
                f"  Associations: {report.associations_created} created, "
                f"{report.associations_updated} updated, "
                f"{report.associations_skipped} skipped",
            )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]Warning: {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# export csv
# ---------------------------------------------------------------------------

@export_group.command("csv")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--doc", "doc_id", required=True, help="Document UUID")
@click.option("--file", "file_path", required=True, type=click.Path(), help="Output file path")
@click.option(
    "--format", "fmt", default="custom",
    help="Export format: custom (default) or opensalt",
)
def export_csv_cmd(tenant_id: str, doc_id: str, file_path: str, fmt: str):
    """Export a document to CSV."""
    _detect_mode()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    # Validate format
    if fmt not in ("custom", "opensalt"):
        err_console.print(
            f"Invalid format: '{fmt}'. Valid values: custom, opensalt",
        )
        raise SystemExit(1)

    if fmt == "opensalt":
        err_console.print("opensalt format is not yet supported")
        raise SystemExit(1)

    # Check output path is writable
    out = Path(file_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        # Test writability
        out.touch()
        out.unlink()
    except (PermissionError, OSError):
        err_console.print(f"Cannot write file: '{file_path}'")
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
                err_console.print(f"Tenant not found: '{tid}'")
                raise SystemExit(1)

            # Check document
            result = await session.execute(
                select(CFDocument).where(
                    CFDocument.tenant_id == tid,
                    CFDocument.identifier == did,
                ),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(f"Document not found: '{did}'")
                raise SystemExit(1)

            with console.status("Exporting CSV..."):
                csv_str = await export_csv(session, tid, did)

            out.write_text(csv_str, encoding="utf-8")
            item_count = csv_str.count("\n") - 1  # rough estimate: lines minus header
            # Count actual data rows (exclude meta lines starting with #)
            lines = csv_str.strip().split("\n")
            data_lines = [
                l for l in lines
                if l and not l.startswith("#") and not l.startswith("Identifier,")
            ]
            console.print(f"Exported {len(data_lines)} items to {file_path}")

    _run(_run_export())


# ---------------------------------------------------------------------------
# db migrate
# ---------------------------------------------------------------------------

@db.command("migrate")
def db_migrate():
    """Run database migrations (alembic upgrade head)."""
    _detect_mode()

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
    console.print("[green]Migration complete.[/green]")


# ---------------------------------------------------------------------------
# cache invalidate
# ---------------------------------------------------------------------------

@cache.command("invalidate")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID")
@click.option("--doc", "doc_id", default=None, help="Document UUID (optional)")
def cache_invalidate(tenant_id: str, doc_id: str | None):
    """Invalidate CloudFront cache (AWS only)."""
    mode = _detect_mode()
    _parse_uuid(tenant_id)
    if doc_id:
        _parse_uuid(doc_id)

    if mode == "docker":
        err_console.print("This command requires AWS environment")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
