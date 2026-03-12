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
from src.models.cf_subject import CFSubject


@dataclass
class UriResult:
    """Result of a URI lookup."""

    resource_type: str  # "CFItem", "CFDocument", "CFAssociation", or lookup type name
    resource: Any  # The ORM model instance
    doc: CFDocument | None = None  # Parent document (for CFItem/CFAssociation)


async def find_resource_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> UriResult | None:
    """Search for a resource by identifier across all resource types.

    Search order: CFItem -> CFDocument -> CFAssociation -> lookups.
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
        return UriResult("CFDocument", doc)

    # 3. CFAssociation
    result = await session.execute(
        select(CFAssociation)
        .options(
            joinedload(CFAssociation.association_grouping),
            joinedload(CFAssociation.cf_document),
        )
        .where(CFAssociation.tenant_id == tenant_id, CFAssociation.identifier == identifier)
    )
    assoc = result.scalars().unique().one_or_none()
    if assoc is not None:
        return UriResult("CFAssociation", assoc, doc=assoc.cf_document)

    # 4. Lookup resources
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
