from datetime import datetime

from pydantic import Field

from src.schemas.common import CASEBaseSchema, LinkGenURIDType, LinkURIType


class CFAssociationDType(CASEBaseSchema):
    """Standalone CFAssociation schema (includes CFDocumentURI)."""

    identifier: str
    uri: str
    association_type: str = Field(alias="associationType")
    origin_node_uri: LinkGenURIDType = Field(alias="originNodeURI")
    destination_node_uri: LinkGenURIDType = Field(alias="destinationNodeURI")
    sequence_number: int | None = Field(default=None, alias="sequenceNumber")
    cf_association_grouping_uri: LinkURIType | None = Field(default=None, alias="CFAssociationGroupingURI")
    cf_document_uri: LinkURIType = Field(alias="CFDocumentURI")
    notes: str | None = None
    extensions: dict | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")


class CFPckgAssociationDType(CASEBaseSchema):
    """CFAssociation within CFPackage / CFItemAssociations (excludes CFDocumentURI)."""

    identifier: str
    uri: str
    association_type: str = Field(alias="associationType")
    origin_node_uri: LinkGenURIDType = Field(alias="originNodeURI")
    destination_node_uri: LinkGenURIDType = Field(alias="destinationNodeURI")
    sequence_number: int | None = Field(default=None, alias="sequenceNumber")
    cf_association_grouping_uri: LinkURIType | None = Field(default=None, alias="CFAssociationGroupingURI")
    notes: str | None = None
    extensions: dict | None = None
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
