from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema, LinkURIType


class CFRubricCriterionLevelDType(CASEBaseSchema):
    identifier: str
    uri: str
    description: str | None = None
    quality: str | None = None
    score: float | None = None
    feedback: str | None = None
    position: int | None = None
    rubric_criterion_id: str | None = Field(default=None, alias="rubricCriterionId")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")


class CFRubricCriterionDType(CASEBaseSchema):
    identifier: str
    uri: str
    category: str | None = None
    description: str | None = None
    cf_item_uri: LinkURIType | None = Field(default=None, alias="CFItemURI")
    weight: float | None = None
    position: int | None = None
    rubric_id: str | None = Field(default=None, alias="rubricId")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
    cf_rubric_criterion_levels: list[CFRubricCriterionLevelDType] | None = Field(
        default=None, alias="CFRubricCriterionLevels"
    )


class CFRubricDType(CASEBaseSchema):
    identifier: str
    uri: str
    title: str | None = None
    description: str | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
    cf_rubric_criteria: list[CFRubricCriterionDType] | None = Field(default=None, alias="CFRubricCriteria")
