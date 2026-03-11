from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class LinkURIType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    identifier: str
    uri: str


class LinkGenURIDType(BaseModel):
    """CASE v1.1 LinkGenURIDType — used for originNodeURI / destinationNodeURI.
    identifier is not restricted to UUID (external references may use non-UUID).
    targetType is v1.1 new field.
    """

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    identifier: str
    uri: str
    target_type: str | None = Field(default=None, alias="targetType")


class ImsxCodeMinorField(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    imsx_code_minor_field_name: str = Field(alias="imsx_codeMinorFieldName", default="sourcedId")
    imsx_code_minor_field_value: str = Field(alias="imsx_codeMinorFieldValue")


class ImsxCodeMinor(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    imsx_code_minor_field: list[ImsxCodeMinorField] = Field(alias="imsx_codeMinorField")


class ImsxStatusInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    imsx_code_major: str = Field(alias="imsx_codeMajor")
    imsx_severity: str = Field(alias="imsx_severity")
    imsx_description: str | None = Field(default=None, alias="imsx_description")
    imsx_code_minor: ImsxCodeMinor | None = Field(default=None, alias="imsx_codeMinor")


class CASEBaseSchema(BaseModel):
    """Base schema for all CASE resource types with common serialization config."""

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("last_change_date_time", check_fields=False)
    @classmethod
    def serialize_datetime(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer(
        "status_start_date", "status_end_date",
        check_fields=False,
    )
    @classmethod
    def serialize_date(cls, v: date | None) -> str | None:
        if v is None:
            return None
        return v.strftime("%Y-%m-%d")
