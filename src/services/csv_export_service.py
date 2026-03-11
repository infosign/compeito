"""CSV Export Service — exports a CFDocument to custom format CSV.

See docs/csv-format.md and docs/import-logic.md (ソート順序 / 独自形式エクスポート)
for the full specification.
"""
from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict

import natsort
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem


# ---------------------------------------------------------------------------
# Data structures for export
# ---------------------------------------------------------------------------

class _ExportItem:
    """Internal representation of an item to export."""
    __slots__ = (
        "identifier", "full_statement", "human_coding_scheme",
        "parent_identifier", "sequence_number", "cf_item_type_title",
        "education_level", "concept_keywords", "abbreviated_statement",
        "language", "list_enumeration", "license_title",
        "status_start_date", "status_end_date",
    )

    def __init__(self, item: CFItem, parent_ident: str | None, seq: int | None):
        self.identifier = str(item.identifier)
        self.full_statement = item.full_statement
        self.human_coding_scheme = item.human_coding_scheme or ""
        self.parent_identifier = parent_ident or ""
        self.sequence_number = str(seq) if seq is not None else ""
        self.cf_item_type_title = item.item_type.title if item.item_type else ""
        self.education_level = _jsonb_list_to_csv(item.education_level)
        self.concept_keywords = _jsonb_list_to_csv(item.concept_keywords)
        self.abbreviated_statement = item.abbreviated_statement or ""
        self.language = item.language or ""
        self.list_enumeration = item.list_enumeration or ""
        self.license_title = item.license.title if item.license else ""
        self.status_start_date = str(item.status_start_date) if item.status_start_date else ""
        self.status_end_date = str(item.status_end_date) if item.status_end_date else ""


def _jsonb_list_to_csv(val: list | None) -> str:
    """Convert JSONB array to comma-separated string. None/[] → empty."""
    if not val:
        return ""
    return ",".join(str(v) for v in val)


# ---------------------------------------------------------------------------
# Sort key for natsort
# ---------------------------------------------------------------------------

def _sort_key(hcs: str | None, identifier: str) -> tuple:
    """Build a sort key: (has_hcs, natsort_key(hcs), identifier).

    NULL hcs sorts after non-NULL.
    """
    if hcs:
        return (0, natsort.natsort_keygen()(hcs), identifier)
    return (1, (), identifier)


# ---------------------------------------------------------------------------
# Tree sort (depth-first)
# ---------------------------------------------------------------------------

def _build_tree_order(
    items: list[CFItem],
    assocs: list[CFAssociation],
    doc_identifier: str,
) -> list[tuple[CFItem, str | None, int | None]]:
    """Sort items in depth-first order based on isChildOf associations.

    Returns list of (item, parent_identifier_str_or_None, sequence_number).
    """
    item_by_ident: dict[str, CFItem] = {str(i.identifier): i for i in items}

    # Build parent info from isChildOf associations
    # item_ident -> list of (parent_ident, sequence_number, assoc for tiebreaking)
    child_to_parents: dict[str, list[tuple[str, int | None, str]]] = defaultdict(list)
    for a in assocs:
        if a.association_type == "isChildOf":
            child_ident = a.origin_node_identifier
            parent_ident = a.destination_node_identifier
            child_to_parents[child_ident].append(
                (parent_ident, a.sequence_number, a.destination_node_identifier)
            )

    # For each child, pick the primary parent (min sequence_number, then dest_ident)
    primary_parent: dict[str, tuple[str, int | None]] = {}
    for child_ident, parents in child_to_parents.items():
        # Sort: non-NULL seq first, then seq ascending, then dest_ident
        parents.sort(key=lambda p: (
            0 if p[1] is not None else 1,  # NULL last
            p[1] if p[1] is not None else 0,
            p[2],
        ))
        best = parents[0]
        primary_parent[child_ident] = (best[0], best[1])

    # Build children map: parent_ident -> [(child_item, seq)]
    children_of: dict[str, list[tuple[CFItem, int | None]]] = defaultdict(list)
    orphans: list[CFItem] = []

    for item in items:
        ident = str(item.identifier)
        if ident in primary_parent:
            parent_ident, seq = primary_parent[ident]
            children_of[parent_ident].append((item, seq))
        else:
            orphans.append(item)

    # Sort children of each parent
    def sort_children(child_list: list[tuple[CFItem, int | None]]) -> list[tuple[CFItem, int | None]]:
        return sorted(child_list, key=lambda c: (
            0 if c[1] is not None else 1,  # NULL seq last
            c[1] if c[1] is not None else 0,
            *_sort_key(c[0].human_coding_scheme, str(c[0].identifier)),
        ))

    # DFS traversal
    result: list[tuple[CFItem, str | None, int | None]] = []

    def dfs(parent_ident: str):
        for item, seq in sort_children(children_of.get(parent_ident, [])):
            item_ident = str(item.identifier)
            # parent_ident for export: None if parent is document
            export_parent = None if parent_ident == doc_identifier else parent_ident
            result.append((item, export_parent, seq))
            dfs(item_ident)

    # Start with document's children (root items)
    dfs(doc_identifier)

    # Append orphans (no isChildOf)
    orphans_sorted = sorted(orphans, key=lambda i: _sort_key(
        i.human_coding_scheme, str(i.identifier),
    ))
    for item in orphans_sorted:
        ident = str(item.identifier)
        if not any(r[0] is item for r in result):
            result.append((item, None, None))

    return result


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

HEADER = [
    "Identifier", "fullStatement", "humanCodingScheme", "parentIdentifier",
    "sequenceNumber", "CFItemType", "educationLevel", "conceptKeywords",
    "abbreviatedStatement", "language", "listEnumeration", "license",
    "statusStartDate", "statusEndDate",
]


async def export_csv(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc_identifier: uuid.UUID,
) -> str:
    """Export a document to custom format CSV.

    Args:
        session: Async database session.
        tenant_id: Tenant UUID.
        doc_identifier: CFDocument identifier to export.

    Returns:
        CSV string (UTF-8, LF line endings, no BOM).

    Raises:
        ValueError: If document not found.
    """
    # Load document with license
    result = await session.execute(
        select(CFDocument)
        .options(joinedload(CFDocument.license))
        .where(
            CFDocument.tenant_id == tenant_id,
            CFDocument.identifier == doc_identifier,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document not found: '{doc_identifier}'")

    # Load all items with joinedloads
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
        )
        .where(CFItem.cf_document_id == doc.id)
    )
    items = list(result.scalars().unique().all())

    # Load all isChildOf associations for this document
    result = await session.execute(
        select(CFAssociation).where(
            CFAssociation.cf_document_id == doc.id,
            CFAssociation.association_type == "isChildOf",
        )
    )
    assocs = list(result.scalars().all())

    # Build tree-ordered export list
    doc_ident_str = str(doc.identifier)
    ordered = _build_tree_order(items, assocs, doc_ident_str)

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Metadata rows
    _write_metadata(writer, doc)

    # Header
    writer.writerow(HEADER)

    # Data rows
    for item, parent_ident, seq in ordered:
        ei = _ExportItem(item, parent_ident, seq)
        writer.writerow([
            ei.identifier,
            ei.full_statement,
            ei.human_coding_scheme,
            ei.parent_identifier,
            ei.sequence_number,
            ei.cf_item_type_title,
            ei.education_level,
            ei.concept_keywords,
            ei.abbreviated_statement,
            ei.language,
            ei.list_enumeration,
            ei.license_title,
            ei.status_start_date,
            ei.status_end_date,
        ])

    return output.getvalue()


def _write_metadata(writer: csv.writer, doc: CFDocument) -> None:
    """Write metadata rows in the specified order."""
    # Order: title, version, creator, publisher, description, language,
    # adoption_status, status_start_date, status_end_date, license,
    # official_source_url, subject

    if doc.title:
        writer.writerow(["#title", doc.title])
    if doc.version:
        writer.writerow(["#version", doc.version])
    if doc.creator:
        writer.writerow(["#creator", doc.creator])
    if doc.publisher:
        writer.writerow(["#publisher", doc.publisher])
    if doc.description:
        writer.writerow(["#description", doc.description])
    if doc.language:
        writer.writerow(["#language", doc.language])
    if doc.adoption_status:
        writer.writerow(["#adoption_status", doc.adoption_status])
    if doc.status_start_date:
        writer.writerow(["#status_start_date", str(doc.status_start_date)])
    if doc.status_end_date:
        writer.writerow(["#status_end_date", str(doc.status_end_date)])
    if doc.license:
        writer.writerow(["#license", doc.license.title])
    if doc.official_source_url:
        writer.writerow(["#official_source_url", doc.official_source_url])
    if doc.subject and isinstance(doc.subject, list) and len(doc.subject) > 0:
        writer.writerow(["#subject"] + list(doc.subject))
