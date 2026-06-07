"""tenants.slug column (URL-friendly alias)

Revision ID: 1dc700ad80d5
Revises: 50f9646e2f71
Create Date: 2026-06-07 09:01:44.331945

Adds an optional URL-friendly short alias for tenants. Public URLs can use
either the tenant's UUID or the slug; UUID stays canonical (CASE API responses
keep emitting UUID-based URIs, so OBF and other clients are unaffected).

Constraints:
- Nullable (existing tenants stay slug-less until explicitly set).
- Unique across the table.
- Format: 2-64 chars, lowercase a-z / 0-9 / hyphens; must start AND end with
  an alphanumeric character (no leading/trailing hyphen).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1dc700ad80d5"
down_revision: Union[str, None] = "50f9646e2f71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("slug", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_tenants_slug", "tenants", ["slug"])
    op.create_check_constraint(
        "ck_tenants_slug_format",
        "tenants",
        "slug IS NULL OR slug ~ '^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenants_slug_format", "tenants", type_="check")
    op.drop_constraint("uq_tenants_slug", "tenants", type_="unique")
    op.drop_column("tenants", "slug")
