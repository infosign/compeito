"""add indexes for the retired-item (tombstone) lookups

Two indexes for the Web UI's default hiding of retired items (B8-4, see
docs/dev/designs/retired-item-ui.md):

1. ``ix_cf_items_doc_retired`` — partial, for "which items of this document are
   retired?". That query runs once per tree page and once per lazy-expand
   fragment, and in the common case it finds nothing; without the partial index
   proving the absence means walking every entry of the document in
   ix_cf_items_document_depth. The index only contains tombstones, so it stays
   tiny.

2. ``ix_cf_items_identifier_text`` — expression index on ``identifier::text``.
   The tree joins cf_associations to cf_items on
   ``cast(cf_items.identifier AS text) = cf_associations.origin_node_identifier``
   (the cast has to go this way round: association identifiers are free-form
   strings and casting them to uuid would make one malformed row fail the whole
   query). A plain uuid index cannot serve that predicate, so without this each
   level expansion hash-joins the document's whole cf_items set.

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7
Create Date: 2026-08-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f3c4d5e6a7b8"
down_revision: Union[str, None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_cf_items_doc_retired",
        "cf_items",
        ["cf_document_id", "status_end_date"],
        unique=False,
        postgresql_where=sa.text("status_end_date IS NOT NULL"),
    )
    op.execute("CREATE INDEX ix_cf_items_identifier_text ON cf_items ((identifier::text))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cf_items_identifier_text")
    op.drop_index("ix_cf_items_doc_retired", table_name="cf_items")
