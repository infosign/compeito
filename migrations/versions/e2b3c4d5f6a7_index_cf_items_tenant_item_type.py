"""add btree index on cf_items (tenant_id, cf_item_type_id)

Speeds up the CFItemType reverse lookup ("items of this type"):
``WHERE tenant_id = ? AND cf_item_type_id = ?``. PostgreSQL does not create an
index on FK columns automatically, so without this the tenant-wide list / count
would seq-scan. The (tenant_id, cf_item_type_id) prefix also serves the count;
the document-scoped pane query adds cf_document_id (covered by the existing
ix_cf_items_tenant_document_coding).

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_cf_items_tenant_item_type",
        "cf_items",
        ["tenant_id", "cf_item_type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cf_items_tenant_item_type", table_name="cf_items")
