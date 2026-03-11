import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.repositories import cf_association_repository, cf_document_repository, cf_item_repository
from src.schemas.cf_association import CFAssociationDType, CFPckgAssociationDType
from src.schemas.cf_document import CFDocumentDType
from src.schemas.cf_item import CFItemDType
from src.schemas.common import LinkGenURIDType, LinkURIType


def _build_cf_package_uri(tenant_id: uuid.UUID, doc: CFDocument) -> LinkURIType:
    return LinkURIType(
        title=doc.title,
        identifier=str(doc.identifier),
        uri=f"{settings.base_url}/{tenant_id}/ims/case/v1p1/CFPackages/{doc.identifier}",
    )


def _build_license_uri_from_model(license_obj) -> LinkURIType | None:
    if license_obj is None:
        return None
    return LinkURIType(
        title=license_obj.title,
        identifier=str(license_obj.identifier),
        uri=license_obj.uri,
    )


def _build_subject_uri_list(subject_uri_json: list | None) -> list[LinkURIType] | None:
    if subject_uri_json is None:
        return None
    return [LinkURIType(**item) for item in subject_uri_json]


def document_to_schema(tenant_id: uuid.UUID, doc: CFDocument) -> CFDocumentDType:
    return CFDocumentDType(
        identifier=str(doc.identifier),
        uri=doc.uri,
        title=doc.title,
        creator=doc.creator,
        publisher=doc.publisher,
        description=doc.description,
        frameworkType=doc.framework_type,
        caseVersion=doc.case_version,
        language=doc.language,
        version=doc.version,
        adoptionStatus=doc.adoption_status,
        statusStartDate=doc.status_start_date,
        statusEndDate=doc.status_end_date,
        licenseURI=_build_license_uri_from_model(doc.license),
        officialSourceURL=doc.official_source_url,
        subject=doc.subject,
        subjectURI=_build_subject_uri_list(doc.subject_uri),
        CFPackageURI=_build_cf_package_uri(tenant_id, doc),
        lastChangeDateTime=doc.last_change_date_time,
    )


async def get_cf_document(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFDocumentDType | None:
    doc = await cf_document_repository.get_cf_document_by_identifier(
        session, tenant_id, identifier
    )
    if doc is None:
        return None
    return document_to_schema(tenant_id, doc)


async def list_cf_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFDocumentDType]:
    docs = await cf_document_repository.list_cf_documents(
        session, tenant_id, limit, offset
    )
    return [document_to_schema(tenant_id, doc) for doc in docs]


# ---------------------------------------------------------------------------
# CFItem
# ---------------------------------------------------------------------------

def _build_document_uri(doc: CFDocument) -> LinkURIType:
    return LinkURIType(
        title=doc.title,
        identifier=str(doc.identifier),
        uri=doc.uri,
    )


def _build_item_type_uri(item: CFItem) -> LinkURIType | None:
    if item.item_type is None:
        return None
    return LinkURIType(
        title=item.item_type.title,
        identifier=str(item.item_type.identifier),
        uri=item.item_type.uri,
    )


def _build_concept_keywords_uri(item: CFItem) -> LinkURIType | None:
    if item.concept is None:
        return None
    return LinkURIType(
        title=item.concept.title,
        identifier=str(item.concept.identifier),
        uri=item.concept.uri,
    )


def item_to_schema(item: CFItem) -> CFItemDType:
    return CFItemDType(
        identifier=str(item.identifier),
        uri=item.uri,
        fullStatement=item.full_statement,
        humanCodingScheme=item.human_coding_scheme,
        abbreviatedStatement=item.abbreviated_statement,
        conceptKeywords=item.concept_keywords,
        conceptKeywordsURI=_build_concept_keywords_uri(item),
        educationLevel=item.education_level,
        subject=item.subject,
        subjectURI=_build_subject_uri_list(item.subject_uri),
        CFItemType=item.item_type.title if item.item_type else None,
        CFItemTypeURI=_build_item_type_uri(item),
        language=item.language,
        licenseURI=_build_license_uri_from_model(item.license),
        statusStartDate=item.status_start_date,
        statusEndDate=item.status_end_date,
        listEnumeration=item.list_enumeration,
        CFDocumentURI=_build_document_uri(item.cf_document),
        lastChangeDateTime=item.last_change_date_time,
    )


async def get_cf_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFItemDType | None:
    item = await cf_item_repository.get_cf_item_by_identifier(
        session, tenant_id, identifier
    )
    if item is None:
        return None
    return item_to_schema(item)


# ---------------------------------------------------------------------------
# CFAssociation (CFPckg variant — no CFDocumentURI)
# ---------------------------------------------------------------------------

def _build_origin_node_uri(assoc: CFAssociation) -> LinkGenURIDType:
    return LinkGenURIDType(
        title=assoc.origin_node_title,
        identifier=assoc.origin_node_identifier,
        uri=assoc.origin_node_uri,
        targetType=assoc.origin_node_target_type,
    )


def _build_destination_node_uri(assoc: CFAssociation) -> LinkGenURIDType:
    return LinkGenURIDType(
        title=assoc.destination_node_title,
        identifier=assoc.destination_node_identifier,
        uri=assoc.destination_node_uri,
        targetType=assoc.destination_node_target_type,
    )


def _build_association_grouping_uri(assoc: CFAssociation) -> LinkURIType | None:
    if assoc.association_grouping is None:
        return None
    return LinkURIType(
        title=assoc.association_grouping.title,
        identifier=str(assoc.association_grouping.identifier),
        uri=assoc.association_grouping.uri,
    )


def association_to_schema(assoc: CFAssociation) -> CFAssociationDType:
    return CFAssociationDType(
        identifier=str(assoc.identifier),
        uri=assoc.uri,
        associationType=assoc.association_type,
        originNodeURI=_build_origin_node_uri(assoc),
        destinationNodeURI=_build_destination_node_uri(assoc),
        sequenceNumber=assoc.sequence_number,
        CFAssociationGroupingURI=_build_association_grouping_uri(assoc),
        CFDocumentURI=_build_document_uri(assoc.cf_document),
        lastChangeDateTime=assoc.last_change_date_time,
    )


def association_to_pckg_schema(assoc: CFAssociation) -> CFPckgAssociationDType:
    return CFPckgAssociationDType(
        identifier=str(assoc.identifier),
        uri=assoc.uri,
        associationType=assoc.association_type,
        originNodeURI=_build_origin_node_uri(assoc),
        destinationNodeURI=_build_destination_node_uri(assoc),
        sequenceNumber=assoc.sequence_number,
        CFAssociationGroupingURI=_build_association_grouping_uri(assoc),
        lastChangeDateTime=assoc.last_change_date_time,
    )


async def get_cf_association(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFAssociationDType | None:
    assoc = await cf_association_repository.get_cf_association_by_identifier(
        session, tenant_id, identifier
    )
    if assoc is None:
        return None
    return association_to_schema(assoc)


async def list_item_associations(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
    limit: int = 100,
    offset: int = 0,
) -> list[CFPckgAssociationDType]:
    assocs = await cf_association_repository.list_associations_for_item(
        session, tenant_id, item_identifier, limit, offset
    )
    return [association_to_pckg_schema(a) for a in assocs]
