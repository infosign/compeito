from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema


class CFItemTypeDType(CASEBaseSchema):
    identifier: str
    uri: str
    title: str
    description: str | None = None
    type_code: str | None = Field(default=None, alias="typeCode")
    hierarchy_code: str | None = Field(default=None, alias="hierarchyCode")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
