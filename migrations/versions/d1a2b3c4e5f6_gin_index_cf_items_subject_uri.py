"""add GIN index on cf_items.subject_uri (jsonb_path_ops)

Enables fast reverse lookup "which items set this subject" via the JSONB
containment query ``subject_uri @> '[{"identifier": "<subject-id>"}]'``.
``jsonb_path_ops`` is the smaller / faster GIN operator class for ``@>``.

Revision ID: d1a2b3c4e5f6
Revises: c704faa62b4f
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, None] = "c704faa62b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_cf_items_subject_uri_gin",
        "cf_items",
        ["subject_uri"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"subject_uri": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_cf_items_subject_uri_gin", table_name="cf_items")
