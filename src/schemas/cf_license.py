from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema


class CFLicenseDType(CASEBaseSchema):
    identifier: str
    uri: str
    title: str
    description: str | None = None
    license_text: str | None = Field(default=None, alias="licenseText")
    extensions: dict | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
