"""cf_rubric_criteria.cf_item_id FK ON DELETE SET NULL

Revision ID: 50f9646e2f71
Revises: b19858da31b6
Create Date: 2026-06-06 17:06:57.695479

The original constraint (created in b19858da31b6) had no ON DELETE clause,
which defaults to NO ACTION. That blocks tenant / document deletion whenever
a CFRubricCriterion references a CFItem (i.e., for any framework that has a
rubric whose criterion is linked to an item). Switch to ON DELETE SET NULL:
deleting the referenced CFItem should leave the criterion intact and just
clear the pointer.

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50f9646e2f71"
down_revision: Union[str, None] = "b19858da31b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "cf_rubric_criteria_cf_item_id_fkey"
_TABLE = "cf_rubric_criteria"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        _TABLE,
        "cf_items",
        ["cf_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        _TABLE,
        "cf_items",
        ["cf_item_id"],
        ["id"],
    )
