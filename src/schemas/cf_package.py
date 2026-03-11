from typing import Any

from pydantic import ConfigDict, Field, model_serializer

from src.schemas.cf_association import CFPckgAssociationDType
from src.schemas.cf_association_grouping import CFAssociationGroupingDType
from src.schemas.cf_concept import CFConceptDType
from src.schemas.cf_document import CFPckgDocumentDType
from src.schemas.cf_item import CFPckgItemDType
from src.schemas.cf_item_type import CFItemTypeDType
from src.schemas.cf_license import CFLicenseDType
from src.schemas.cf_subject import CFSubjectDType
from src.schemas.common import CASEBaseSchema


class CFDefinitionsDType(CASEBaseSchema):
    """CFDefinitions within CFPackage. Empty arrays are excluded at key level."""

    cf_item_types: list[CFItemTypeDType] | None = Field(default=None, alias="CFItemTypes")
    cf_subjects: list[CFSubjectDType] | None = Field(default=None, alias="CFSubjects")
    cf_concepts: list[CFConceptDType] | None = Field(default=None, alias="CFConcepts")
    cf_licenses: list[CFLicenseDType] | None = Field(default=None, alias="CFLicenses")
    cf_association_groupings: list[CFAssociationGroupingDType] | None = Field(default=None, alias="CFAssociationGroupings")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Exclude keys with None or empty lists."""
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
                result[alias] = [item.model_dump(by_alias=True) for item in value]
        return result


class CFPackageDType(CASEBaseSchema):
    model_config = ConfigDict(populate_by_name=True)

    cf_document: CFPckgDocumentDType = Field(alias="CFDocument")
    cf_items: list[CFPckgItemDType] = Field(alias="CFItems")
    cf_associations: list[CFPckgAssociationDType] = Field(alias="CFAssociations")
    cf_definitions: CFDefinitionsDType | None = Field(default=None, alias="CFDefinitions")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "CFDocument": self.cf_document.model_dump(by_alias=True),
            "CFItems": [item.model_dump(by_alias=True) for item in self.cf_items],
            "CFAssociations": [assoc.model_dump(by_alias=True) for assoc in self.cf_associations],
        }
        if self.cf_definitions is not None:
            definitions = self.cf_definitions.model_dump(by_alias=True)
            if definitions:
                result["CFDefinitions"] = definitions
        return result
