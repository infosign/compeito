from datetime import date, datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema, LinkURIType


class CFItemDType(CASEBaseSchema):
    """Standalone CFItem schema (includes CFDocumentURI)."""

    identifier: str
    uri: str
    full_statement: str = Field(alias="fullStatement")
    human_coding_scheme: str | None = Field(default=None, alias="humanCodingScheme")
    abbreviated_statement: str | None = Field(default=None, alias="abbreviatedStatement")
    concept_keywords: list[str] | None = Field(default=None, alias="conceptKeywords")
    concept_keywords_uri: LinkURIType | None = Field(default=None, alias="conceptKeywordsURI")
    education_level: list[str] | None = Field(default=None, alias="educationLevel")
    subject: list[str] | None = None
    subject_uri: list[LinkURIType] | None = Field(default=None, alias="subjectURI")
    cf_item_type: str | None = Field(default=None, alias="CFItemType")
    cf_item_type_uri: LinkURIType | None = Field(default=None, alias="CFItemTypeURI")
    language: str | None = None
    license_uri: LinkURIType | None = Field(default=None, alias="licenseURI")
    status_start_date: date | None = Field(default=None, alias="statusStartDate")
    status_end_date: date | None = Field(default=None, alias="statusEndDate")
    list_enumeration: str | None = Field(default=None, alias="listEnumeration")
    cf_document_uri: LinkURIType = Field(alias="CFDocumentURI")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")


class CFPckgItemDType(CASEBaseSchema):
    """CFItem within CFPackage (excludes CFDocumentURI)."""

    identifier: str
    uri: str
    full_statement: str = Field(alias="fullStatement")
    human_coding_scheme: str | None = Field(default=None, alias="humanCodingScheme")
    abbreviated_statement: str | None = Field(default=None, alias="abbreviatedStatement")
    concept_keywords: list[str] | None = Field(default=None, alias="conceptKeywords")
    concept_keywords_uri: LinkURIType | None = Field(default=None, alias="conceptKeywordsURI")
    education_level: list[str] | None = Field(default=None, alias="educationLevel")
    subject: list[str] | None = None
    subject_uri: list[LinkURIType] | None = Field(default=None, alias="subjectURI")
    cf_item_type: str | None = Field(default=None, alias="CFItemType")
    cf_item_type_uri: LinkURIType | None = Field(default=None, alias="CFItemTypeURI")
    language: str | None = None
    license_uri: LinkURIType | None = Field(default=None, alias="licenseURI")
    status_start_date: date | None = Field(default=None, alias="statusStartDate")
    status_end_date: date | None = Field(default=None, alias="statusEndDate")
    list_enumeration: str | None = Field(default=None, alias="listEnumeration")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
