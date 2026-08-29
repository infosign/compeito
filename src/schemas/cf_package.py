from typing import Any

from pydantic import ConfigDict, Field, SerializationInfo, model_serializer

from src.schemas.cf_association import CFPckgAssociationDType
from src.schemas.cf_association_grouping import CFAssociationGroupingDType
from src.schemas.cf_concept import CFConceptDType
from src.schemas.cf_document import CFPckgDocumentDType
from src.schemas.cf_item import CFPckgItemDType
from src.schemas.cf_item_type import CFItemTypeDType
from src.schemas.cf_license import CFLicenseDType
from src.schemas.cf_rubric import CFRubricDType
from src.schemas.cf_subject import CFSubjectDType
from src.schemas.common import CASEBaseSchema


class CFDefinitionsDType(CASEBaseSchema):
    """CFDefinitions within CFPackage. Empty arrays are excluded at key level."""

    cf_item_types: list[CFItemTypeDType] | None = Field(default=None, alias="CFItemTypes")
    cf_subjects: list[CFSubjectDType] | None = Field(default=None, alias="CFSubjects")
    cf_concepts: list[CFConceptDType] | None = Field(default=None, alias="CFConcepts")
    cf_licenses: list[CFLicenseDType] | None = Field(default=None, alias="CFLicenses")
    cf_association_groupings: list[CFAssociationGroupingDType] | None = Field(
        default=None, alias="CFAssociationGroupings"
    )
    extensions: dict | None = None

    @model_serializer(mode="plain")
    def serialize_model(self, info: SerializationInfo) -> dict[str, Any]:
        """Exclude keys with None or empty lists.

        A custom serializer bypasses pydantic's own dump options, so
        ``exclude_none`` has to be forwarded by hand — otherwise strict output
        would keep every nested ``null`` (C16).
        """
        exclude_none = bool(info.exclude_none)
        result: dict[str, Any] = {}
        field_map = {
            "cf_item_types": "CFItemTypes",
            "cf_subjects": "CFSubjects",
            "cf_concepts": "CFConcepts",
            "cf_licenses": "CFLicenses",
            "cf_association_groupings": "CFAssociationGroupings",
        }
        for attr, alias in field_map.items():
            value = getattr(self, attr)
            if value:
                result[alias] = [item.model_dump(by_alias=True, exclude_none=exclude_none) for item in value]
        if self.extensions:
            result["extensions"] = self.extensions
        return result


class CFPackageDType(CASEBaseSchema):
    model_config = ConfigDict(populate_by_name=True)

    cf_document: CFPckgDocumentDType = Field(alias="CFDocument")
    cf_items: list[CFPckgItemDType] = Field(alias="CFItems")
    cf_associations: list[CFPckgAssociationDType] = Field(alias="CFAssociations")
    cf_definitions: CFDefinitionsDType | None = Field(default=None, alias="CFDefinitions")
    cf_rubrics: list[CFRubricDType] = Field(default_factory=list, alias="CFRubrics")
    extensions: dict | None = None

    @model_serializer(mode="plain")
    def serialize_model(self, info: SerializationInfo) -> dict[str, Any]:
        exclude_none = bool(info.exclude_none)
        result: dict[str, Any] = {
            "CFDocument": self.cf_document.model_dump(by_alias=True, exclude_none=exclude_none),
            "CFItems": [item.model_dump(by_alias=True, exclude_none=exclude_none) for item in self.cf_items],
            "CFAssociations": [
                assoc.model_dump(by_alias=True, exclude_none=exclude_none) for assoc in self.cf_associations
            ],
        }
        if self.cf_definitions is not None:
            definitions = self.cf_definitions.model_dump(by_alias=True, exclude_none=exclude_none)
            if definitions:
                result["CFDefinitions"] = definitions
        result["CFRubrics"] = [r.model_dump(by_alias=True, exclude_none=exclude_none) for r in self.cf_rubrics]
        if self.extensions:
            result["extensions"] = self.extensions
        return result
