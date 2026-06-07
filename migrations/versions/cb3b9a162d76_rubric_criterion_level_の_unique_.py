"""rubric criterion/level の unique を親スコープに変更（テナント分離）

Revision ID: cb3b9a162d76
Revises: bfbb97d3805a
Create Date: 2026-06-07 21:53:53.469403

CFRubricCriterion / CFRubricCriterionLevel の identifier がグローバルに一意
だったため、別テナントが同一 identifier のルーブリック CSV を import すると
既存テナントの criterion / level を奪うバグがあった（CFRubric / CFItem /
CFDocument は (tenant_id, identifier) で分離されているのに criterion / level
だけ不整合）。これらは tenant_id 列を持たず親経由でテナントに属するため、
ユニーク制約を親スコープの複合キーに変更する:

- criterion: (identifier) → (cf_rubric_id, identifier)
- level:     (identifier) → (cf_rubric_criterion_id, identifier)

旧グローバル制約下では重複 identifier が存在し得ないため、複合制約への移行は
データ移行不要（衝突なし）。
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb3b9a162d76"
down_revision: Union[str, None] = "bfbb97d3805a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # criterion
    op.drop_constraint("uq_cf_rubric_criteria_identifier", "cf_rubric_criteria", type_="unique")
    op.create_unique_constraint(
        "uq_cf_rubric_criteria_rubric_identifier",
        "cf_rubric_criteria",
        ["cf_rubric_id", "identifier"],
    )
    # level
    op.drop_constraint(
        "uq_cf_rubric_criterion_levels_identifier", "cf_rubric_criterion_levels", type_="unique"
    )
    op.create_unique_constraint(
        "uq_cf_rubric_criterion_levels_criterion_identifier",
        "cf_rubric_criterion_levels",
        ["cf_rubric_criterion_id", "identifier"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cf_rubric_criterion_levels_criterion_identifier",
        "cf_rubric_criterion_levels",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_cf_rubric_criterion_levels_identifier",
        "cf_rubric_criterion_levels",
        ["identifier"],
    )
    op.drop_constraint(
        "uq_cf_rubric_criteria_rubric_identifier", "cf_rubric_criteria", type_="unique"
    )
    op.create_unique_constraint(
        "uq_cf_rubric_criteria_identifier",
        "cf_rubric_criteria",
        ["identifier"],
    )
