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


async def _list_items_where(session: AsyncSession, conditions: list, offset: int, limit: int) -> list[dict]:
    """Shared body of the reverse-lookup list queries (items using a definition).

    Selects the label/link columns, joins the owning document, and applies a
    stable order for offset pagination. Returns
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
        .where(*conditions)
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


async def _count_items_where(session: AsyncSession, conditions: list) -> int:
    result = await session.execute(select(func.count()).select_from(CFItem).where(*conditions))
    return int(result.scalar_one())


def _subject_conditions(tenant_id: uuid.UUID, subject_identifier: str, document_id: uuid.UUID | None) -> list:
    conditions = [CFItem.tenant_id == tenant_id, _subject_uri_contains(subject_identifier)]
    if document_id is not None:
        conditions.append(CFItem.cf_document_id == document_id)
    return conditions


def _item_type_conditions(tenant_id: uuid.UUID, item_type_id: uuid.UUID, document_id: uuid.UUID | None) -> list:
    conditions = [CFItem.tenant_id == tenant_id, CFItem.cf_item_type_id == item_type_id]
    if document_id is not None:
        conditions.append(CFItem.cf_document_id == document_id)
    return conditions


async def list_items_by_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    subject_identifier: str,
    *,
    document_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """CFItems in this tenant whose ``subject_uri`` references the given subject.

    Reverse lookup for the CFSubject detail page ("items setting this subject").
    Matches via JSONB containment ``subject_uri @> '[{"identifier": <id>}]'``
    (GIN-indexed). Tenant-scoped. When ``document_id`` is given, additionally
    restricts to that one document (the tree right pane is document-scoped; the
    standalone /uri/ page passes None for the tenant-wide list)."""
    conditions = _subject_conditions(tenant_id, subject_identifier, document_id)
    return await _list_items_where(session, conditions, offset, limit)


async def count_items_by_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    subject_identifier: str,
    *,
    document_id: uuid.UUID | None = None,
) -> int:
    """Total CFItems referencing the given subject (for the count label).
    Same scoping as ``list_items_by_subject``."""
    return await _count_items_where(session, _subject_conditions(tenant_id, subject_identifier, document_id))


async def list_items_by_item_type(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_type_id: uuid.UUID,
    *,
    document_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """CFItems of the given CFItemType ("items of this type").

    Reverse lookup for the CFItemType detail page. Matches the FK
    ``cf_item.cf_item_type_id`` (indexed via the FK) — ``item_type_id`` is the
    CFItemType's internal PK (``CFItemType.id``), not its CASE identifier.
    Tenant-scoped; ``document_id`` restricts to one document (pane scope)."""
    return await _list_items_where(session, _item_type_conditions(tenant_id, item_type_id, document_id), offset, limit)


async def count_items_by_item_type(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_type_id: uuid.UUID,
    *,
    document_id: uuid.UUID | None = None,
) -> int:
    """Total CFItems of the given CFItemType (count label). Same scoping as
    ``list_items_by_item_type``."""
    return await _count_items_where(session, _item_type_conditions(tenant_id, item_type_id, document_id))
