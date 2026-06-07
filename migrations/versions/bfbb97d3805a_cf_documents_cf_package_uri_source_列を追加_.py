"""cf_documents.cf_package_uri_source 列を追加 (round-trip cat G)

Revision ID: bfbb97d3805a
Revises: 0054ee62f823
Create Date: 2026-06-07 14:53:31.247291

CFDocument が source CFPackage で持っていた CFPackageURI.uri を verbatim
保存するための nullable な Text 列。OpenCASE → compeito → OpenCASE round-trip
で source の denormalized LinkURI 値を失わないために必要。NULL の場合は
emit 時に `_build_cf_package_uri()` でフォールバックする。

cat F (`cf_rubric_criteria.cf_item_uri_source`) と同じパターン。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bfbb97d3805a"
down_revision: Union[str, None] = "0054ee62f823"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cf_documents",
        sa.Column("cf_package_uri_source", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cf_documents", "cf_package_uri_source")
