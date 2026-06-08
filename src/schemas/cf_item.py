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
    alternative_label: str | None = Field(default=None, alias="alternativeLabel")
    notes: str | None = None
    extensions: dict | None = None
    cf_document_uri: LinkURIType = Field(alias="CFDocumentURI")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")


class CFPckgItemDType(CASEBaseSchema):
    """CFItem within CFPackage.

    Includes `CFDocumentURI` so that the OpenCASE → compeito → OpenCASE
    round-trip preserves the field (OpenCASE emits it inside CFPackage too).
    The CASE v1.1 spec permits this — the document is at the top of the
    package, but echoing the link on each item is allowed and aids parsing
    by clients that walk items independently.
    """

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
    alternative_label: str | None = Field(default=None, alias="alternativeLabel")
    notes: str | None = None
    extensions: dict | None = None
    cf_document_uri: LinkURIType = Field(alias="CFDocumentURI")
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
