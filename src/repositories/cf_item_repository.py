import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem


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
