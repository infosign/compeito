from datetime import date, datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema, LinkURIType


class CFDocumentDType(CASEBaseSchema):
    """Standalone CFDocument schema (includes CFPackageURI)."""

    identifier: str
    uri: str
    title: str
    creator: str | None = None
    publisher: str | None = None
    description: str | None = None
    framework_type: str | None = Field(default=None, alias="frameworkType")
    case_version: str | None = Field(default=None, alias="caseVersion")
    language: str | None = None
    version: str | None = None
    adoption_status: str | None = Field(default=None, alias="adoptionStatus")
    status_start_date: date | None = Field(default=None, alias="statusStartDate")
    status_end_date: date | None = Field(default=None, alias="statusEndDate")
    license_uri: LinkURIType | None = Field(default=None, alias="licenseURI")
    official_source_url: str | None = Field(default=None, alias="officialSourceURL")
    subject: list[str] | None = None
    subject_uri: list[LinkURIType] | None = Field(default=None, alias="subjectURI")
    cf_package_uri: LinkURIType = Field(alias="CFPackageURI")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")


class CFPckgDocumentDType(CASEBaseSchema):
    """CFDocument within CFPackage (excludes CFPackageURI)."""

    identifier: str
    uri: str
    title: str
    creator: str | None = None
    publisher: str | None = None
    description: str | None = None
    framework_type: str | None = Field(default=None, alias="frameworkType")
    case_version: str | None = Field(default=None, alias="caseVersion")
    language: str | None = None
    version: str | None = None
    adoption_status: str | None = Field(default=None, alias="adoptionStatus")
    status_start_date: date | None = Field(default=None, alias="statusStartDate")
    status_end_date: date | None = Field(default=None, alias="statusEndDate")
    license_uri: LinkURIType | None = Field(default=None, alias="licenseURI")
    official_source_url: str | None = Field(default=None, alias="officialSourceURL")
    subject: list[str] | None = None
    subject_uri: list[LinkURIType] | None = Field(default=None, alias="subjectURI")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
