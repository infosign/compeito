from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema


class CFRubricDType(CASEBaseSchema):
    identifier: str
    uri: str
    title: str | None = None
    description: str | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
