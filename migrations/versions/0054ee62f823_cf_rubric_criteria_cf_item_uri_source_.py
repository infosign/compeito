"""cf_rubric_criteria.cf_item_uri_source 列を追加 (round-trip cat F)

Revision ID: 0054ee62f823
Revises: 1dc700ad80d5
Create Date: 2026-06-07 14:41:03.906022

CFRubricCriterion が source CFPackage で持っていた CFItemURI.uri を verbatim
保存するための nullable な Text 列。OpenCASE → compeito → OpenCASE round-trip
で、source の denormalized LinkURI 値を失わないために必要。NULL の場合は
emit 時に被リンク CFItem.uri にフォールバックする。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054ee62f823"
down_revision: Union[str, None] = "1dc700ad80d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cf_rubric_criteria",
        sa.Column("cf_item_uri_source", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cf_rubric_criteria", "cf_item_uri_source")
