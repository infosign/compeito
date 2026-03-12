"""Rubric CSV Export Service — exports CFRubrics for a document to CSV.

See docs/spec/csv-format.md "Rubric CSV Format" section for the specification.
"""

from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_document import CFDocument
from src.repositories import cf_rubric_repository

RUBRIC_CSV_HEADER = [
    "Type",
    "Identifier",
    "RubricIdentifier",
    "CriterionIdentifier",
    "Title",
    "Description",
    "Category",
    "Weight",
    "Position",
    "Quality",
    "Score",
    "Feedback",
    "CFItemIdentifier",
]


def _position_sort_key(position: int | None, identifier) -> tuple:
    """Sort by position (NULL last), then identifier."""
    return (
        0 if position is not None else 1,
        position if position is not None else 0,
        str(identifier),
    )


async def export_rubric_csv(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc_identifier: uuid.UUID,
) -> tuple[str, int, int, int]:
    """Export rubrics for a document to CSV.

    Returns:
        (csv_string, rubric_count, criterion_count, level_count)

    Raises:
        ValueError: If document not found.
    """
    # Load document
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

    # Load rubrics with criteria and levels
    rubrics = await cf_rubric_repository.list_by_document(session, doc.id)

    # Sort rubrics by title (NULL last), then identifier
    rubrics.sort(
        key=lambda r: (
            0 if r.title else 1,
            r.title or "",
            str(r.identifier),
        )
    )

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Header
    writer.writerow(RUBRIC_CSV_HEADER)

    rubric_count = 0
    criterion_count = 0
    level_count = 0

    for rubric in rubrics:
        rubric_ident = str(rubric.identifier)
        rubric_count += 1

        # Rubric row
        writer.writerow(
            [
                "Rubric",
                rubric_ident,
                "",  # RubricIdentifier (N/A for rubric row)
                "",  # CriterionIdentifier (N/A)
                rubric.title or "",
                rubric.description or "",
                "",  # Category
                "",  # Weight
                "",  # Position
                "",  # Quality
                "",  # Score
                "",  # Feedback
                "",  # CFItemIdentifier
            ]
        )

        # Sort criteria
        criteria = sorted(
            rubric.criteria,
            key=lambda c: _position_sort_key(c.position, c.identifier),
        )

        for criterion in criteria:
            crit_ident = str(criterion.identifier)
            criterion_count += 1

            # CFItem identifier
            cf_item_ident = str(criterion.cf_item.identifier) if criterion.cf_item else ""

            # Criterion row
            writer.writerow(
                [
                    "Criterion",
                    crit_ident,
                    rubric_ident,
                    "",  # CriterionIdentifier (N/A)
                    "",  # Title (N/A)
                    criterion.description or "",
                    criterion.category or "",
                    str(criterion.weight) if criterion.weight is not None else "",
                    str(criterion.position) if criterion.position is not None else "",
                    "",  # Quality
                    "",  # Score
                    "",  # Feedback
                    cf_item_ident,
                ]
            )

            # Sort levels
            levels = sorted(
                criterion.levels,
                key=lambda lv: _position_sort_key(lv.position, lv.identifier),
            )

            for level in levels:
                level_count += 1

                writer.writerow(
                    [
                        "Level",
                        str(level.identifier),
                        "",  # RubricIdentifier (N/A)
                        crit_ident,
                        "",  # Title (N/A)
                        level.description or "",
                        "",  # Category
                        "",  # Weight
                        str(level.position) if level.position is not None else "",
                        level.quality or "",
                        str(level.score) if level.score is not None else "",
                        level.feedback or "",
                        "",  # CFItemIdentifier
                    ]
                )

    return output.getvalue(), rubric_count, criterion_count, level_count
