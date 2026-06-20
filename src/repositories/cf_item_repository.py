import uuid

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem


def _subject_uri_contains(subject_identifier: str):
    """JSONB containment predicate: subject_uri @> '[{"identifier": <id>}]'.

    The operand is cast to JSONB explicitly so the GIN index
    (ix_cf_items_subject_uri_gin, jsonb_path_ops) is used rather than a seq scan.
    """
    return CFItem.subject_uri.contains(cast([{"identifier": subject_identifier}], JSONB))


async def map_identifiers_to_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifiers: set[str],
) -> dict[str, dict]:
    """Map CFItem identifiers (as strings) to their owning document.

    Used to classify related-association destinations: an identifier present in
    the result is a CFItem in this tenant (possibly in another document); an
    absent one is external / unresolvable. Non-UUID strings are skipped.
    Returns ``{identifier: {"doc_identifier": str, "doc_title": str}}``.
    """
    uuids: list[uuid.UUID] = []
    for ident in identifiers:
        try:
            uuids.append(uuid.UUID(ident))
        except (ValueError, AttributeError, TypeError):
            continue
    if not uuids:
        return {}
    rows = await session.execute(
        select(CFItem.identifier, CFDocument.identifier, CFDocument.title)
        .join(CFDocument, CFItem.cf_document_id == CFDocument.id)
        .where(CFItem.tenant_id == tenant_id, CFItem.identifier.in_(uuids))
    )
    return {
        str(item_ident): {"doc_identifier": str(doc_ident), "doc_title": doc_title}
        for item_ident, doc_ident, doc_title in rows.all()
    }


async def map_identifiers_to_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifiers: set[str],
) -> dict[str, dict]:
    """Like `map_identifiers_to_documents` but also returns the item's own label
    fields. Used by the cross-document hierarchy sections (上位/下位 別FW) which
    need both the item's display label and its owning document. Returns
    ``{identifier: {full_statement, human_coding_scheme, doc_identifier, doc_title}}``.
    """
    uuids: list[uuid.UUID] = []
    for ident in identifiers:
        try:
            uuids.append(uuid.UUID(ident))
        except (ValueError, AttributeError, TypeError):
            continue
    if not uuids:
        return {}
    rows = await session.execute(
        select(
            CFItem.identifier,
            CFItem.full_statement,
            CFItem.human_coding_scheme,
            CFDocument.identifier,
            CFDocument.title,
        )
        .join(CFDocument, CFItem.cf_document_id == CFDocument.id)
        .where(CFItem.tenant_id == tenant_id, CFItem.identifier.in_(uuids))
    )
    return {
        str(item_ident): {
            "full_statement": full_statement,
            "human_coding_scheme": hcs,
            "doc_identifier": str(doc_ident),
            "doc_title": doc_title,
        }
        for item_ident, full_statement, hcs, doc_ident, doc_title in rows.all()
    }


async def get_cf_item_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFItem | None:
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.cf_document),
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
        )
        .where(CFItem.tenant_id == tenant_id, CFItem.identifier == identifier)
    )
    return result.scalar_one_or_none()


async def list_items_by_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    subject_identifier: str,
    *,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """CFItems in this tenant whose ``subject_uri`` references the given subject.

    Reverse lookup for the CFSubject detail page ("items setting this subject").
    Matches via JSONB containment ``subject_uri @> '[{"identifier": <id>}]'``
    (GIN-indexed). Tenant-scoped. Ordered by human_coding_scheme → full_statement
    → identifier for a stable offset-pagination boundary. Returns
    ``[{identifier, human_coding_scheme, full_statement, doc_identifier, doc_title}]``.
    """
    rows = await session.execute(
        select(
            CFItem.identifier,
            CFItem.human_coding_scheme,
            CFItem.full_statement,
            CFDocument.identifier,
            CFDocument.title,
        )
        .join(CFDocument, CFItem.cf_document_id == CFDocument.id)
        .where(CFItem.tenant_id == tenant_id, _subject_uri_contains(subject_identifier))
        .order_by(
            CFItem.human_coding_scheme.nullslast(),
            CFItem.full_statement,
            CFItem.identifier,
        )
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "identifier": str(item_ident),
            "human_coding_scheme": hcs,
            "full_statement": full_statement,
            "doc_identifier": str(doc_ident),
            "doc_title": doc_title,
        }
        for item_ident, hcs, full_statement, doc_ident, doc_title in rows.all()
    ]


async def count_items_by_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    subject_identifier: str,
) -> int:
    """Total CFItems in this tenant referencing the given subject (for the count
    label). Call once on the SSR page; the "load more" fragment derives has_more
    from a limit+1 fetch instead of recounting."""
    result = await session.execute(
        select(func.count())
        .select_from(CFItem)
        .where(CFItem.tenant_id == tenant_id, _subject_uri_contains(subject_identifier))
    )
    return int(result.scalar_one())
