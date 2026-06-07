"""URI resource lookup service for the /uri/{uuid} page."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

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
