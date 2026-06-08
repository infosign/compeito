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
    round-trip preserves the field (OpenCASE / OpenSALT emit it inside CFPackage
    too). NOTE: the official CASE v1.1 OpenAPI schema for CFPckgItemDType uses
    `additionalProperties: false` and does NOT list `CFDocumentURI`, so strict
    schema validation of package output would reject it. compeito echoes it by
    default for real-world interop; request `?strict=1` on GET /CFPackages/{id}
    to omit it (and CFDocument.CFPackageURI) for strict conformance.
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
