from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema


class CFSubjectDType(CASEBaseSchema):
    identifier: str
    uri: str
    title: str
    description: str | None = None
    hierarchy_code: str | None = Field(default=None, alias="hierarchyCode")
    extensions: dict | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
