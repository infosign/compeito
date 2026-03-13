import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_rubric import CFRubric
from src.models.cf_rubric_criterion import CFRubricCriterion


async def get_by_identifier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFRubric | None:
    result = await session.execute(
        select(CFRubric)
        .options(
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.levels),
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.cf_item),
        )
        .where(CFRubric.tenant_id == tenant_id, CFRubric.identifier == identifier)
    )
    return result.scalars().unique().one_or_none()


async def list_by_document(
    session: AsyncSession,
    doc_id: uuid.UUID,
    limit: int | None = None,
    offset: int | None = None,
) -> list[CFRubric]:
    query = (
        select(CFRubric)
        .options(
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.levels),
            joinedload(CFRubric.criteria).joinedload(CFRubricCriterion.cf_item),
        )
        .where(CFRubric.cf_document_id == doc_id)
        .order_by(CFRubric.identifier)
    )
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().unique().all())
