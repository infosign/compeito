from datetime import date, datetime, timezone

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
        # tz-aware datetime is converted to UTC; naive datetime is treated as UTC.
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc)
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer(
        "status_start_date",
        "status_end_date",
        check_fields=False,
    )
    @classmethod
    def serialize_date(cls, v: date | None) -> str | None:
        if v is None:
            return None
        return v.strftime("%Y-%m-%d")

    @field_serializer("score", "weight", check_fields=False)
    @classmethod
    def serialize_int_or_float(cls, v: float | None) -> int | float | None:
        """Emit whole-number floats as int (round-trip parity with OpenCASE).

        DB columns are float, but rubric scores / weights are commonly authored
        as integers (e.g., 5). OpenCASE and other CASE-conformant clients emit
        these as int. Without this serializer, compeito would convert 5 to 5.0,
        breaking byte-for-byte round-trip even though the numeric values match.
        """
        if v is None:
            return None
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
