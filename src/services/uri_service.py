"""URI resource lookup service for the /uri/{uuid} page."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config import settings
from src.models.cf_association import CFAssociation
from src.models.cf_association_grouping import CFAssociationGrouping
from src.models.cf_concept import CFConcept
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_item_type import CFItemType
from src.models.cf_license import CFLicense
from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion
from src.models.cf_rubric_criterion_level import CFRubricCriterionLevel
from src.models.cf_subject import CFSubject


def self_uri_tenant_mismatch(uri: str | None, tenant_id: uuid.UUID) -> str | None:
    """Classify a resource's own ``uri`` that points at THIS instance but not at
    ``tenant_id``. Returns ``"slug"``, ``"other-tenant"``, or None when fine.

    Import stores the source ``uri`` verbatim (FR-7.2), which is right for
    external URIs but means a wrong one is kept forever: nothing rewrites it
    later. The two ways to get one wrong on this instance:

    - ``slug``: the tenant segment is a slug rather than the UUID. The slug is a
      renameable UI alias — CASE responses never emit it — so the stored URI
      stops resolving the day the slug changes.
    - ``other-tenant``: it addresses a different tenant on this instance.

    A URI on another host is a legitimate external reference and returns None.
    So is any other path on this host: an instance often serves an ordinary web
    site next to compeito, and a CFDocument may well point its `uri` at a page
    there. Only the tenant-addressed shapes this app actually routes
    (``/{tenant}/uri/{id}`` and ``/{tenant}/ims/...``) are judged.
    """
    if not uri:
        return None
    prefix = settings.base_url.rstrip("/") + "/"
    if not uri.startswith(prefix):
        return None  # external host: not ours to judge
    parts = [p for p in uri[len(prefix) :].split("/") if p]
    if len(parts) < 2 or parts[1] not in ("uri", "ims"):
        return None  # some other page on this host, not a tenant-addressed URI
    try:
        return None if uuid.UUID(parts[0]) == tenant_id else "other-tenant"
    except (ValueError, AttributeError):
        return "slug"


def parse_internal_tenant_id(uri: str | None) -> uuid.UUID | None:
    """If `uri` is a compeito-internal CFItem permalink on THIS instance, return
    the tenant UUID it points at; otherwise None.

    A compeito permalink looks like ``{base_url}/{tenant-uuid}/uri/{item-uuid}``
    (see `case_import_service._build_uri`). This recognizes that shape so a
    CFAssociation endpoint URI stored against another tenant on the same
    instance can be resolved to that tenant. Anything else — an external host, a
    different path shape, an invalid tenant UUID, empty — returns None and is
    treated as a true external reference by callers.
    """
    if not uri:
        return None
    prefix = settings.base_url.rstrip("/") + "/"
    if not uri.startswith(prefix):
        return None
    rest = uri[len(prefix) :]
    parts = rest.split("/")
    # Expect exactly {tenant-uuid}/uri/{item-uuid}: first segment a valid UUID,
    # second literally "uri". (We don't require the 3rd to parse — the tenant id
    # is all callers need; item resolution happens later against that tenant.)
    if len(parts) < 3 or parts[1] != "uri":
        return None
    try:
        return uuid.UUID(parts[0])
    except (ValueError, AttributeError):
        return None


@dataclass
class UriResult:
    """Result of a URI lookup."""

    resource_type: str  # "CFItem", "CFDocument", "CFAssociation", "CFRubric", etc.
    resource: Any  # The ORM model instance
    doc: CFDocument | None = None  # Parent document (for CFItem/CFAssociation/CFRubric)


async def find_resource_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> UriResult | None:
    """Search for a resource by identifier across all resource types.

    Search order: CFItem -> CFDocument -> CFAssociation -> CFRubric ->
                  CFRubricCriterion -> CFRubricCriterionLevel -> lookups.
    """
    # 1. CFItem
    result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
            joinedload(CFItem.cf_document).joinedload(CFDocument.license),
        )
        .where(CFItem.tenant_id == tenant_id, CFItem.identifier == identifier)
    )
    item = result.scalars().unique().one_or_none()
    if item is not None:
        return UriResult("CFItem", item, doc=item.cf_document)

    # 2. CFDocument
    result = await session.execute(
        select(CFDocument)
        .options(joinedload(CFDocument.license))
        .where(CFDocument.tenant_id == tenant_id, CFDocument.identifier == identifier)
    )
    doc = result.scalar_one_or_none()
    if doc is not None:
        return UriResult("CFDocument", doc, doc=doc)

    # 3. CFAssociation
    result = await session.execute(
        select(CFAssociation)
        .options(
            joinedload(CFAssociation.association_grouping),
            joinedload(CFAssociation.cf_document).joinedload(CFDocument.license),
        )
        .where(CFAssociation.tenant_id == tenant_id, CFAssociation.identifier == identifier)
    )
    assoc = result.scalars().unique().one_or_none()
    if assoc is not None:
        return UriResult("CFAssociation", assoc, doc=assoc.cf_document)

    # 4. CFRubric
    result = await session.execute(
        select(CFRubric)
        .options(
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.levels),
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.cf_item),
            joinedload(CFRubric.cf_document).joinedload(CFDocument.license),
        )
        .where(CFRubric.tenant_id == tenant_id, CFRubric.identifier == identifier)
    )
    rubric = result.scalars().unique().one_or_none()
    if rubric is not None:
        return UriResult("CFRubric", rubric, doc=rubric.cf_document)

    # 5. CFRubricCriterion
    result = await session.execute(
        select(CFRubricCriterion)
        .options(
            joinedload(CFRubricCriterion.cf_rubric).joinedload(CFRubric.cf_document).joinedload(CFDocument.license),
            joinedload(CFRubricCriterion.cf_item),
            joinedload(CFRubricCriterion.levels),
        )
        .where(CFRubricCriterion.identifier == identifier)
    )
    # criterion has no tenant_id; its identifier is only unique per rubric
    # (uq cf_rubric_id, identifier), so the same identifier can exist across
    # tenants. Pick the one owned by this tenant (don't assume a single row).
    # Known limitation: the same identifier could also be reused across multiple
    # rubrics within one tenant — then /uri returns the first match. Identifiers
    # are UUIDs so this is effectively nonexistent (CASE assumes id uniqueness).
    criterion = next(
        (c for c in result.scalars().unique().all() if c.cf_rubric.tenant_id == tenant_id),
        None,
    )
    if criterion is not None:
        return UriResult("CFRubricCriterion", criterion, doc=criterion.cf_rubric.cf_document)

    # 6. CFRubricCriterionLevel
    result = await session.execute(
        select(CFRubricCriterionLevel)
        .options(
            joinedload(CFRubricCriterionLevel.cf_rubric_criterion)
            .joinedload(CFRubricCriterion.cf_rubric)
            .joinedload(CFRubric.cf_document)
            .joinedload(CFDocument.license),
            joinedload(CFRubricCriterionLevel.cf_rubric_criterion).joinedload(CFRubricCriterion.cf_item),
        )
        .where(CFRubricCriterionLevel.identifier == identifier)
    )
    # level has no tenant_id; its identifier is only unique per criterion, so
    # the same identifier can exist across tenants. Pick this tenant's row.
    # Same first-match caveat as the criterion lookup above (UUIDs → moot).
    level = next(
        (lv for lv in result.scalars().unique().all() if lv.cf_rubric_criterion.cf_rubric.tenant_id == tenant_id),
        None,
    )
    if level is not None:
        return UriResult(
            "CFRubricCriterionLevel",
            level,
            doc=level.cf_rubric_criterion.cf_rubric.cf_document,
        )

    # 7. Lookup resources
    for model, type_name in [
        (CFItemType, "CFItemType"),
        (CFSubject, "CFSubject"),
        (CFConcept, "CFConcept"),
        (CFLicense, "CFLicense"),
        (CFAssociationGrouping, "CFAssociationGrouping"),
    ]:
        result = await session.execute(
            select(model).where(model.tenant_id == tenant_id, model.identifier == identifier)
        )
        obj = result.scalar_one_or_none()
        if obj is not None:
            return UriResult(type_name, obj)

    return None
