"""CASE v1.1 notes / alternativeLabel / extensions 列を追加

Revision ID: 5389de18d5e7
Revises: cb3b9a162d76
Create Date: 2026-06-08 23:42:56.336298

CASE v1.1 情報モデルに存在するが compeito が未保存だった標準フィールドを追加する。

- notes (TEXT): CFItem / CFDocument / CFAssociation（各 DType の標準フィールド）
- alternativeLabel (TEXT): CFItem
- extensions (JSONB): 全エンティティ（v1.1 で "added to all classes"）。
  CFRubricCriterionLevel の extensions は仕様上 array だが、object/array 双方を
  保持できる JSONB で受ける。
- package_extensions / definitions_extensions (JSONB): cf_documents のみ。
  CFPackage / CFDefinitions コンテナ単位の extensions を、document 中心ビューの
  所有 document 行に保存する。

すべて nullable。既存データへの影響なし。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "5389de18d5e7"
down_revision: Union[str, None] = "cb3b9a162d76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All entity tables get `extensions`.
_EXTENSION_TABLES = [
    "cf_documents",
    "cf_items",
    "cf_associations",
    "cf_association_groupings",
    "cf_item_types",
    "cf_concepts",
    "cf_subjects",
    "cf_licenses",
    "cf_rubrics",
    "cf_rubric_criteria",
    "cf_rubric_criterion_levels",
]

# Tables that get `notes`.
_NOTES_TABLES = ["cf_documents", "cf_items", "cf_associations"]


def upgrade() -> None:
    for table in _NOTES_TABLES:
        op.add_column(table, sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("cf_items", sa.Column("alternative_label", sa.Text(), nullable=True))
    for table in _EXTENSION_TABLES:
        op.add_column(table, sa.Column("extensions", JSONB(), nullable=True))
    # Container-level extensions (CFPackage / CFDefinitions) — stored on the
    # owning document since a package is a document-centered view in compeito.
    op.add_column("cf_documents", sa.Column("package_extensions", JSONB(), nullable=True))
    op.add_column("cf_documents", sa.Column("definitions_extensions", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("cf_documents", "definitions_extensions")
    op.drop_column("cf_documents", "package_extensions")
    for table in _EXTENSION_TABLES:
        op.drop_column(table, "extensions")
    op.drop_column("cf_items", "alternative_label")
    for table in _NOTES_TABLES:
        op.drop_column(table, "notes")
