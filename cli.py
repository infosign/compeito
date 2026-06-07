"""COMPEITO CLI — tenant/doc management, import/export, db migrate."""

from __future__ import annotations

import asyncio
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.i18n import detect_lang_from_env, get_translator

console = Console(stderr=False)
err_console = Console(stderr=True, style="bold red")

# Module-level translator for Click decorator help texts (evaluated at import time)
t = get_translator(detect_lang_from_env(), cli=True)


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------


def _check_db():
    """Verify DATABASE_URL is provided (env var or `.env` file) or exit.

    Pydantic Settings reads `.env` at import time, so the actual DB connection
    works even when DATABASE_URL is only in `.env`. This check mirrors that to
    avoid a misleading "set DATABASE_URL" error in hybrid native dev setups.
    """
    import os
    from pathlib import Path

    if os.environ.get("DATABASE_URL"):
        return
    env_file = Path(".env")
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if line.startswith("DATABASE_URL=") and line.split("=", 1)[1].strip():
                return
    err_console.print(t("err_env_required"))
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


@asynccontextmanager
async def _get_session():
    """Create an async DB session for CLI use.

    Implemented as an async context manager (not a bare async generator) so that
    the connection/engine teardown happens deterministically inside the same
    asyncio.run() event loop. With a bare generator, finalization can be deferred
    until after the loop closes, which produces "non-checked-in connection" /
    "coroutine ignored GeneratorExit" warnings.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from src.config import settings

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
    finally:
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
# Tenant slug — character / length / format rules
# ---------------------------------------------------------------------------
# A slug is an OPTIONAL URL-friendly alias for a tenant. The canonical
# identifier is still the UUID (CASE API URIs always carry the UUID).
#
# Rules (mirrored by the `ck_tenants_slug_format` CHECK constraint at DB level
# and by `docs/spec/architecture.md`):
#
#   1. Length: 2-64 characters
#   2. Allowed characters: lowercase letters a-z, digits 0-9, hyphen `-`
#   3. Must START with an alphanumeric character (no leading hyphen)
#   4. Must END with an alphanumeric character (no trailing hyphen)
#   5. NOT a valid UUID string (would shadow the canonical-id path)
#   6. NOT one of the reserved tokens that collide with top-level mounts
#      (`/health`, `/static`, and a few defensive ones for future expansion)
#
# Examples of valid slugs:   `ikenohata-u`, `mext-curriculum-2025`, `acme`
# Examples of invalid slugs: `Ikenohata` (uppercase), `池之端大学` (non-ASCII),
#                            `-acme` (leading hyphen), `acme-` (trailing hyphen),
#                            `a` (too short), `health` (reserved).

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")

_RESERVED_SLUGS = frozenset(
    {
        "health",  # GET /health
        "static",  # /static/* (FastAPI StaticFiles)
        # Defensive reserves for likely future top-level expansion:
        "admin",
        "api",
        "assets",
        "favicon.ico",
        "robots.txt",
        "_",
    }
)


def _validate_slug(slug: str) -> str | None:
    """Return a translated error message if `slug` is unacceptable; else None.

    The same rules are enforced by the `ck_tenants_slug_format` DB constraint
    + the unique constraint, but we check here first so the user sees a
    friendly message instead of a Postgres IntegrityError traceback.
    """
    try:
        uuid.UUID(slug)
        return t("err_slug_uuid_shaped", value=slug)
    except (ValueError, AttributeError):
        pass
    if slug in _RESERVED_SLUGS:
        return t("err_slug_reserved", value=slug)
    if not _SLUG_RE.match(slug):
        return t("err_slug_invalid_format", value=slug)
    return None


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
@click.option("--id", "tenant_id", default=None, help=t("help_tenant_id"))
@click.option("--slug", default=None, help=t("help_tenant_slug"))
@click.option("--private", "is_private", is_flag=True, default=False, help=t("help_make_private"))
def tenant_create(name: str, tenant_id: str | None, slug: str | None, is_private: bool):
    """Create a new tenant."""
    _check_db()

    tid: uuid.UUID | None = None
    if tenant_id is not None:
        tid = _parse_uuid(tenant_id)

    if slug is not None:
        err = _validate_slug(slug)
        if err is not None:
            err_console.print(err)
            raise SystemExit(1)

    async def _run_create():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async with _get_session() as session:
            if tid is not None:
                # Pre-flight uniqueness check to give a friendly error instead of
                # leaving the user to decipher a Postgres UNIQUE-violation traceback.
                result = await session.execute(select(Tenant).where(Tenant.id == tid))
                if result.scalar_one_or_none() is not None:
                    err_console.print(t("err_tenant_id_in_use", value=str(tid)))
                    raise SystemExit(1)
            if slug is not None:
                result = await session.execute(select(Tenant).where(Tenant.slug == slug))
                if result.scalar_one_or_none() is not None:
                    err_console.print(t("err_tenant_slug_in_use", value=slug))
                    raise SystemExit(1)

            kwargs: dict = {"name": name, "is_private": is_private}
            if tid is not None:
                kwargs["id"] = tid
            if slug is not None:
                kwargs["slug"] = slug
            tenant_obj = Tenant(**kwargs)
            session.add(tenant_obj)
            await session.flush()
            console.print(
                t(
                    "msg_created_tenant",
                    id=str(tenant_obj.id),
                    name=tenant_obj.name,
                    visibility=_visibility(tenant_obj.is_private),
                ),
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

        async with _get_session() as session:
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
                table.add_column("SLUG")
                table.add_column("NAME")
                table.add_column("VISIBILITY")
                table.add_column("CREATED")
                for tenant_obj in tenants:
                    table.add_row(
                        str(tenant_obj.id),
                        tenant_obj.slug or "",
                        tenant_obj.name,
                        _visibility(tenant_obj.is_private),
                        tenant_obj.created_at.strftime("%Y-%m-%d") if tenant_obj.created_at else "",
                    )
                console.print(table)
            else:
                # With docs: tree-style output
                for tenant_obj in tenants:
                    visibility = _visibility(tenant_obj.is_private)
                    slug_part = f"  [{tenant_obj.slug}]" if tenant_obj.slug else ""
                    console.print(f"{tenant_obj.id}{slug_part}  {tenant_obj.name}  {visibility}")
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
                            f"  {prefix} {doc_ident}  {doc_title}  ({item_count} {t('items_suffix')})",
                        )

    _run(_run_list())


# ---------------------------------------------------------------------------
# tenant update
# ---------------------------------------------------------------------------


@tenant.command("update", help=t("cmd_tenant_update"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--name", default=None, help=t("help_new_name"))
@click.option("--slug", default=None, help=t("help_tenant_slug"))
@click.option("--clear-slug", "clear_slug", is_flag=True, default=False, help=t("help_tenant_clear_slug"))
@click.option("--private", "set_private", is_flag=True, default=False, help=t("help_set_private"))
@click.option("--public", "set_public", is_flag=True, default=False, help=t("help_set_public"))
def tenant_update(
    tenant_id: str,
    name: str | None,
    slug: str | None,
    clear_slug: bool,
    set_private: bool,
    set_public: bool,
):
    """Update a tenant."""
    _check_db()

    if set_private and set_public:
        err_console.print(t("err_private_public_exclusive"))
        raise SystemExit(1)

    if slug is not None and clear_slug:
        err_console.print(t("err_tenant_slug_clear_exclusive"))
        raise SystemExit(1)

    if not name and not set_private and not set_public and slug is None and not clear_slug:
        err_console.print(t("err_update_requires_option"))
        raise SystemExit(1)

    if slug is not None:
        err = _validate_slug(slug)
        if err is not None:
            err_console.print(err)
            raise SystemExit(1)

    tid = _parse_uuid(tenant_id)

    async def _run_update():
        from sqlalchemy import select

        from src.models.tenant import Tenant

        async with _get_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            tenant_obj = result.scalar_one_or_none()
            if tenant_obj is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            if slug is not None:
                # Uniqueness pre-flight (skip when reassigning the same slug to
                # the same tenant — that's a no-op, not a conflict).
                existing = await session.execute(select(Tenant).where(Tenant.slug == slug, Tenant.id != tid))
                if existing.scalar_one_or_none() is not None:
                    err_console.print(t("err_tenant_slug_in_use", value=slug))
                    raise SystemExit(1)

            if name is not None:
                tenant_obj.name = name
            if set_private:
                tenant_obj.is_private = True
            if set_public:
                tenant_obj.is_private = False
            if slug is not None:
                tenant_obj.slug = slug
            elif clear_slug:
                tenant_obj.slug = None

            await session.flush()
            console.print(
                t(
                    "msg_updated_tenant",
                    id=str(tenant_obj.id),
                    name=tenant_obj.name,
                    visibility=_visibility(tenant_obj.is_private),
                ),
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

        async with _get_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            tenant_obj = result.scalar_one_or_none()
            if tenant_obj is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            if not force:
                answer = click.prompt(
                    t("prompt_delete_tenant", name=tenant_obj.name, id=str(tenant_obj.id)),
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

        async with _get_session() as session:
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

        async with _get_session() as session:
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
                    t("prompt_delete_document", title=doc.title, id=str(doc.identifier), count=str(item_count)),
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
@click.option(
    "--profile",
    type=click.Choice(["auto", "custom", "opensalt", "simple"]),
    default="auto",
    help=t("help_import_profile"),
)
def import_csv_cmd(
    tenant_id: str,
    file_path: str,
    doc_id: str | None,
    doc_title: str | None,
    doc_version: str | None,
    profile: str,
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

        async with _get_session() as session:
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
                try:
                    report = await import_csv(
                        session,
                        tid,
                        csv_data,
                        doc_identifier=did,
                        doc_title=doc_title,
                        doc_version=doc_version,
                        profile=None if profile == "auto" else profile,
                    )
                except ValueError as e:
                    err_console.print(f"[red]{e}[/red]")
                    raise SystemExit(1) from e
                await session.commit()

            console.print(
                t("msg_imported_into", title=report.document_title, id=str(report.document_identifier)),
            )
            console.print(
                t(
                    "msg_items_summary",
                    created=str(report.items_created),
                    updated=str(report.items_updated),
                    skipped=str(report.items_skipped),
                ),
            )
            console.print(
                t("msg_assoc_summary_short", created=str(report.associations_created)),
            )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]{t('lbl_warning')} {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# import case
# ---------------------------------------------------------------------------


@import_group.command("case", help=t("cmd_import_case"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--url", default=None, help=t("help_case_url"))
@click.option(
    "--file",
    "file_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help=t("help_case_file"),
)
@click.option("--doc", "doc_id", default=None, help=t("help_doc_uuid_update"))
def import_case(tenant_id: str, url: str | None, file_path: str | None, doc_id: str | None):
    """Import a CASE CFPackage from a URL (--url) or a local JSON file (--file).

    Exactly one of --url / --file must be given. --file is useful when the
    source editor (OpenCASE / OpenSALT / any CASE-conformant tool) runs on a
    private network and its CFPackage URL is not reachable from this server.
    """
    _check_db()
    if bool(url) == bool(file_path):
        err_console.print(t("err_case_source"))
        raise SystemExit(1)
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id) if doc_id else None

    data = None
    if file_path:
        import json

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            err_console.print(f"[red]{t('err_invalid_json', value=str(e))}[/red]")
            raise SystemExit(1) from e

    async def _run_import():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.case_import_service import import_case_from_dict, import_case_package

        async with _get_session() as session:
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
                if data is not None:
                    report = await import_case_from_dict(
                        session,
                        tid,
                        data,
                        doc_identifier=did,
                    )
                else:
                    report = await import_case_package(
                        session,
                        tid,
                        url,
                        doc_identifier=did,
                    )
                await session.commit()

            console.print(
                t("msg_imported", title=report.document_title, id=str(report.document_identifier)),
            )
            console.print(
                t(
                    "msg_items_summary",
                    created=str(report.items_created),
                    updated=str(report.items_updated),
                    skipped=str(report.items_skipped),
                ),
            )
            console.print(
                t(
                    "msg_assoc_summary",
                    created=str(report.associations_created),
                    updated=str(report.associations_updated),
                    skipped=str(report.associations_skipped),
                ),
            )
            if report.rubrics_created or report.rubrics_updated or report.rubrics_skipped:
                console.print(
                    t(
                        "msg_rubrics_summary",
                        created=str(report.rubrics_created),
                        updated=str(report.rubrics_updated),
                        skipped=str(report.rubrics_skipped),
                    ),
                )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]{t('lbl_warning')} {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# export csv
# ---------------------------------------------------------------------------


@export_group.command("csv", help=t("cmd_export_csv"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(), help=t("help_output_file"))
@click.option(
    "--profile",
    default="custom",
    help=t("help_export_profile"),
)
def export_csv_cmd(tenant_id: str, doc_id: str, file_path: str, profile: str):
    """Export a document to CSV."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    # Validate profile
    if profile not in ("custom", "opensalt"):
        err_console.print(t("err_invalid_profile", value=profile))
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
        from src.services.csv_export_service import export_csv, export_opensalt_csv

        async with _get_session() as session:
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
                if profile == "opensalt":
                    csv_str = await export_opensalt_csv(session, tid, did)
                else:
                    csv_str = await export_csv(session, tid, did)

            out.write_text(csv_str, encoding="utf-8")
            # Count actual data rows (exclude meta lines starting with #, and header rows)
            lines = csv_str.strip().split("\n")
            data_lines = [
                line for line in lines if line and not line.startswith("#") and not line.startswith("Identifier,")
            ]
            console.print(
                t("msg_exported", count=str(len(data_lines)), path=file_path),
            )

    _run(_run_export())


# ---------------------------------------------------------------------------
# import rubric
# ---------------------------------------------------------------------------


@import_group.command("rubric", help=t("cmd_import_rubric"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help=t("help_csv_file"))
def import_csv_rubric_cmd(tenant_id: str, doc_id: str, file_path: str):
    """Import rubrics from a CSV file."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)
    csv_data = Path(file_path).read_bytes()

    async def _run_import():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.csv_rubric_import_service import import_rubric_csv

        async with _get_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            result = await session.execute(
                select(CFDocument).where(
                    CFDocument.tenant_id == tid,
                    CFDocument.identifier == did,
                ),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_doc_not_found", value=str(did)))
                raise SystemExit(1)

            with console.status(t("msg_importing_rubric_csv")):
                report = await import_rubric_csv(session, tid, did, csv_data)
                await session.commit()

            console.print(
                t("msg_imported_into", title=report.document_title, id=str(report.document_identifier)),
            )
            console.print(
                t(
                    "msg_rubric_import_rubrics",
                    created=str(report.rubrics_created),
                    updated=str(report.rubrics_updated),
                    skipped=str(report.rubrics_skipped),
                ),
            )
            console.print(
                t(
                    "msg_rubric_import_criteria",
                    created=str(report.criteria_created),
                    updated=str(report.criteria_updated),
                    skipped=str(report.criteria_skipped),
                ),
            )
            console.print(
                t(
                    "msg_rubric_import_levels",
                    created=str(report.levels_created),
                    updated=str(report.levels_updated),
                    skipped=str(report.levels_skipped),
                ),
            )
            if report.warnings:
                for w in report.warnings:
                    console.print(f"  [yellow]{t('lbl_warning')} {w}[/yellow]")

    _run(_run_import())


# ---------------------------------------------------------------------------
# export case (JSON)
# ---------------------------------------------------------------------------


@export_group.command("case", help=t("cmd_export_case"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(), help=t("help_output_file"))
def export_case_cmd(tenant_id: str, doc_id: str, file_path: str):
    """Export a document as a CASE v1.1 CFPackage JSON file.

    The output has the same payload shape as `GET /ims/case/v1p1/CFPackages/{id}`
    (pretty-printed for readability; the API serves compact JSON) and can be
    imported into any CASE-conformant tool (OpenCASE, OpenSALT, etc.) via their
    respective import endpoints, or back into COMPEITO via `import case --file`.
    """
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    out = Path(file_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        out.unlink()
    except (PermissionError, OSError):
        err_console.print(t("err_file_unwritable", value=file_path))
        raise SystemExit(1) from None

    async def _run_export():
        import json

        from sqlalchemy import select

        from src.models.tenant import Tenant
        from src.services.cf_view_service import get_cf_package

        async with _get_session() as session:
            result = await session.execute(select(Tenant).where(Tenant.id == tid))
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            with console.status(t("msg_exporting_case")):
                pkg = await get_cf_package(session, tid, did)
                if pkg is None:
                    err_console.print(t("err_doc_not_found", value=str(did)))
                    raise SystemExit(1)
                payload = pkg.model_dump(by_alias=True, exclude_none=False)
                out.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

            item_count = len(payload.get("CFItems") or [])
            console.print(t("msg_exported", count=str(item_count), path=str(out)))

    _run(_run_export())


# ---------------------------------------------------------------------------
# export rubric
# ---------------------------------------------------------------------------


@export_group.command("rubric", help=t("cmd_export_rubric"))
@click.option("--tenant", "tenant_id", required=True, help=t("help_tenant_uuid"))
@click.option("--doc", "doc_id", required=True, help=t("help_doc_uuid"))
@click.option("--file", "file_path", required=True, type=click.Path(), help=t("help_output_file"))
def export_csv_rubric_cmd(tenant_id: str, doc_id: str, file_path: str):
    """Export rubrics to CSV."""
    _check_db()
    tid = _parse_uuid(tenant_id)
    did = _parse_uuid(doc_id)

    out = Path(file_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        out.unlink()
    except (PermissionError, OSError):
        err_console.print(t("err_file_unwritable", value=file_path))
        raise SystemExit(1)

    async def _run_export():
        from sqlalchemy import select

        from src.models.cf_document import CFDocument
        from src.models.tenant import Tenant
        from src.services.csv_rubric_export_service import export_rubric_csv

        async with _get_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tid),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_tenant_not_found", value=str(tid)))
                raise SystemExit(1)

            result = await session.execute(
                select(CFDocument).where(
                    CFDocument.tenant_id == tid,
                    CFDocument.identifier == did,
                ),
            )
            if result.scalar_one_or_none() is None:
                err_console.print(t("err_doc_not_found", value=str(did)))
                raise SystemExit(1)

            with console.status(t("msg_exporting_rubric_csv")):
                csv_str, r_count, c_count, l_count = await export_rubric_csv(session, tid, did)

            out.write_text(csv_str, encoding="utf-8")
            console.print(
                t(
                    "msg_exported_rubrics",
                    rubrics=str(r_count),
                    criteria=str(c_count),
                    levels=str(l_count),
                    path=file_path,
                ),
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
