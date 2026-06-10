import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.errors import ResourceNotFoundError
from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.repositories import (
    cf_association_grouping_repository,
    cf_association_repository,
    cf_concept_repository,
    cf_document_repository,
    cf_item_repository,
    cf_item_type_repository,
    cf_license_repository,
    cf_rubric_repository,
    cf_subject_repository,
)
from src.schemas.cf_association import CFAssociationDType, CFPckgAssociationDType
from src.schemas.cf_association_grouping import CFAssociationGroupingDType
from src.schemas.cf_concept import CFConceptDType
from src.schemas.cf_document import CFDocumentDType
from src.schemas.cf_item import CFItemDType
from src.schemas.cf_item_type import CFItemTypeDType
from src.schemas.cf_license import CFLicenseDType
from src.schemas.cf_rubric import CFRubricCriterionDType, CFRubricCriterionLevelDType, CFRubricDType
from src.schemas.cf_subject import CFSubjectDType
from src.schemas.common import LinkGenURIDType, LinkURIType


def _build_cf_package_uri(tenant_id: uuid.UUID, doc: CFDocument) -> LinkURIType:
    # Prefer the verbatim source CFPackageURI.uri captured at import time
    # (round-trip cat G); fall back to a compeito-native URL when this
    # CFDocument originated from CSV/manual creation rather than a CFPackage.
    uri = doc.cf_package_uri_source or (f"{settings.base_url}/{tenant_id}/ims/case/v1p1/CFPackages/{doc.identifier}")
    return LinkURIType(
        title=doc.title,
        identifier=str(doc.identifier),
        uri=uri,
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
        notes=doc.notes,
        extensions=doc.extensions,
        CFPackageURI=_build_cf_package_uri(tenant_id, doc),
        lastChangeDateTime=doc.last_change_date_time,
    )


async def get_cf_document(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFDocumentDType | None:
    doc = await cf_document_repository.get_cf_document_by_identifier(session, tenant_id, identifier)
    if doc is None:
        return None
    return document_to_schema(tenant_id, doc)


async def list_cf_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    *,
    filter_clause=None,
    order_by=None,
) -> list[CFDocumentDType]:
    docs = await cf_document_repository.list_cf_documents(
        session, tenant_id, limit, offset, filter_clause=filter_clause, order_by=order_by
    )
    return [document_to_schema(tenant_id, doc) for doc in docs]


async def count_cf_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    filter_clause=None,
) -> int:
    return await cf_document_repository.count_cf_documents(session, tenant_id, filter_clause=filter_clause)


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
        alternativeLabel=item.alternative_label,
        notes=item.notes,
        extensions=item.extensions,
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
    item = await cf_item_repository.get_cf_item_by_identifier(session, tenant_id, identifier)
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
        notes=assoc.notes,
        extensions=assoc.extensions,
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
        notes=assoc.notes,
        extensions=assoc.extensions,
        lastChangeDateTime=assoc.last_change_date_time,
    )


async def get_cf_association(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFAssociationDType | None:
    assoc = await cf_association_repository.get_cf_association_by_identifier(session, tenant_id, identifier)
    if assoc is None:
        return None
    return association_to_schema(assoc)


async def list_item_associations(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item_identifier: str,
    limit: int | None = None,
    offset: int = 0,
) -> list[CFPckgAssociationDType]:
    assocs = await cf_association_repository.list_associations_for_item(
        session, tenant_id, item_identifier, limit, offset
    )
    return [association_to_pckg_schema(a) for a in assocs]


# ---------------------------------------------------------------------------
# Lookup resources
# ---------------------------------------------------------------------------


def _item_type_to_schema(obj) -> CFItemTypeDType:
    return CFItemTypeDType(
        identifier=str(obj.identifier),
        uri=obj.uri,
        title=obj.title,
        description=obj.description,
        typeCode=obj.type_code,
        hierarchyCode=obj.hierarchy_code,
        extensions=obj.extensions,
        lastChangeDateTime=obj.last_change_date_time,
    )


def _concept_to_schema(obj) -> CFConceptDType:
    return CFConceptDType(
        identifier=str(obj.identifier),
        uri=obj.uri,
        title=obj.title,
        description=obj.description,
        keywords=obj.keywords,
        hierarchyCode=obj.hierarchy_code,
        extensions=obj.extensions,
        lastChangeDateTime=obj.last_change_date_time,
    )


def _subject_to_schema(obj) -> CFSubjectDType:
    return CFSubjectDType(
        identifier=str(obj.identifier),
        uri=obj.uri,
        title=obj.title,
        description=obj.description,
        hierarchyCode=obj.hierarchy_code,
        extensions=obj.extensions,
        lastChangeDateTime=obj.last_change_date_time,
    )


def _license_to_schema(obj) -> CFLicenseDType:
    return CFLicenseDType(
        identifier=str(obj.identifier),
        uri=obj.uri,
        title=obj.title,
        description=obj.description,
        licenseText=obj.license_text,
        extensions=obj.extensions,
        lastChangeDateTime=obj.last_change_date_time,
    )


def _association_grouping_to_schema(obj) -> CFAssociationGroupingDType:
    return CFAssociationGroupingDType(
        identifier=str(obj.identifier),
        uri=obj.uri,
        title=obj.title,
        description=obj.description,
        extensions=obj.extensions,
        lastChangeDateTime=obj.last_change_date_time,
    )


# --- CFItemType ---


async def get_cf_item_type(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFItemTypeDType | None:
    obj = await cf_item_type_repository.get_by_identifier(session, tenant_id, identifier)
    return _item_type_to_schema(obj) if obj else None


async def get_cf_item_type_set(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> list[CFItemTypeDType] | None:
    """CASE v1.1 CFItemTypeSetDType: requested item type first, then descendants by hierarchyCode."""
    root = await cf_item_type_repository.get_by_identifier(session, tenant_id, identifier)
    if root is None:
        return None
    descendants: list = []
    if root.hierarchy_code:
        all_descendants = await cf_item_type_repository.list_descendants_by_hierarchy_code(
            session, tenant_id, root.hierarchy_code
        )
        descendants = [d for d in all_descendants if d.identifier != root.identifier]
    return [_item_type_to_schema(root)] + [_item_type_to_schema(d) for d in descendants]


async def list_cf_item_types(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFItemTypeDType]:
    objs = await cf_item_type_repository.list_all(session, tenant_id, limit, offset)
    return [_item_type_to_schema(o) for o in objs]


# --- CFConcept ---


async def get_cf_concept(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFConceptDType | None:
    obj = await cf_concept_repository.get_by_identifier(session, tenant_id, identifier)
    return _concept_to_schema(obj) if obj else None


async def get_cf_concept_set(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> list[CFConceptDType] | None:
    """CASE v1.1 CFConceptSetDType: requested concept first, then descendants by hierarchyCode."""
    root = await cf_concept_repository.get_by_identifier(session, tenant_id, identifier)
    if root is None:
        return None
    descendants: list = []
    if root.hierarchy_code:
        all_descendants = await cf_concept_repository.list_descendants_by_hierarchy_code(
            session, tenant_id, root.hierarchy_code
        )
        descendants = [d for d in all_descendants if d.identifier != root.identifier]
    return [_concept_to_schema(root)] + [_concept_to_schema(d) for d in descendants]


async def list_cf_concepts(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFConceptDType]:
    objs = await cf_concept_repository.list_all(session, tenant_id, limit, offset)
    return [_concept_to_schema(o) for o in objs]


# --- CFSubject ---


async def get_cf_subject(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFSubjectDType | None:
    obj = await cf_subject_repository.get_by_identifier(session, tenant_id, identifier)
    return _subject_to_schema(obj) if obj else None


async def get_cf_subject_set(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> list[CFSubjectDType] | None:
    """CASE v1.1 CFSubjectSetDType: requested subject first, then descendants by hierarchyCode."""
    root = await cf_subject_repository.get_by_identifier(session, tenant_id, identifier)
    if root is None:
        return None
    descendants: list = []
    if root.hierarchy_code:
        all_descendants = await cf_subject_repository.list_descendants_by_hierarchy_code(
            session, tenant_id, root.hierarchy_code
        )
        descendants = [d for d in all_descendants if d.identifier != root.identifier]
    return [_subject_to_schema(root)] + [_subject_to_schema(d) for d in descendants]


async def list_cf_subjects(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFSubjectDType]:
    objs = await cf_subject_repository.list_all(session, tenant_id, limit, offset)
    return [_subject_to_schema(o) for o in objs]


# --- CFLicense ---


async def get_cf_license(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFLicenseDType | None:
    obj = await cf_license_repository.get_by_identifier(session, tenant_id, identifier)
    return _license_to_schema(obj) if obj else None


async def list_cf_licenses(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFLicenseDType]:
    objs = await cf_license_repository.list_all(session, tenant_id, limit, offset)
    return [_license_to_schema(o) for o in objs]


# --- CFRubric ---


def _rubric_criterion_level_to_schema(level) -> CFRubricCriterionLevelDType:
    return CFRubricCriterionLevelDType(
        identifier=str(level.identifier),
        uri=level.uri,
        description=level.description,
        quality=level.quality,
        score=level.score,
        feedback=level.feedback,
        position=level.position,
        rubricCriterionId=str(level.rubric_criterion_id) if level.rubric_criterion_id else None,
        extensions=level.extensions,
        lastChangeDateTime=level.last_change_date_time,
    )


def _rubric_criterion_to_schema(criterion) -> CFRubricCriterionDType:
    cf_item_uri = None
    if criterion.cf_item is not None:
        # Prefer the source's denormalized CFItemURI.uri verbatim (round-trip
        # cat F) — upstream systems like OpenCASE don't re-resolve linked URIs
        # on import, so preserving the source value keeps the round-trip
        # lossless. Falls back to the live CFItem.uri if we didn't capture
        # a source value (e.g., resource created via CSV import).
        cf_item_uri = LinkURIType(
            title=criterion.cf_item.full_statement,
            identifier=str(criterion.cf_item.identifier),
            uri=criterion.cf_item_uri_source or criterion.cf_item.uri,
        )

    levels = criterion.levels
    cf_levels = (
        sorted(
            [_rubric_criterion_level_to_schema(lv) for lv in levels],
            key=lambda x: x.identifier,
        )
        or None
    )

    return CFRubricCriterionDType(
        identifier=str(criterion.identifier),
        uri=criterion.uri,
        category=criterion.category,
        description=criterion.description,
        CFItemURI=cf_item_uri,
        weight=criterion.weight,
        position=criterion.position,
        rubricId=str(criterion.rubric_id) if criterion.rubric_id else None,
        extensions=criterion.extensions,
        lastChangeDateTime=criterion.last_change_date_time,
        CFRubricCriterionLevels=cf_levels,
    )


def rubric_to_schema(rubric) -> CFRubricDType:
    criteria = rubric.criteria
    cf_criteria = (
        sorted(
            [_rubric_criterion_to_schema(c) for c in criteria],
            key=lambda x: x.identifier,
        )
        or None
    )

    return CFRubricDType(
        identifier=str(rubric.identifier),
        uri=rubric.uri,
        title=rubric.title,
        description=rubric.description,
        extensions=rubric.extensions,
        lastChangeDateTime=rubric.last_change_date_time,
        CFRubricCriteria=cf_criteria,
    )


async def get_cf_rubric(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFRubricDType | None:
    obj = await cf_rubric_repository.get_by_identifier(session, tenant_id, identifier)
    return rubric_to_schema(obj) if obj else None


async def list_cf_rubrics(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    doc_identifier: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFRubricDType]:
    doc = await cf_document_repository.get_cf_document_by_identifier(session, tenant_id, doc_identifier)
    if doc is None:
        raise ResourceNotFoundError(f"CFDocument not found: '{doc_identifier}'")
    rubrics = await cf_rubric_repository.list_by_document(session, doc.id, limit=limit, offset=offset)
    return [rubric_to_schema(r) for r in rubrics]


# --- CFAssociationGrouping ---


async def get_cf_association_grouping(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFAssociationGroupingDType | None:
    obj = await cf_association_grouping_repository.get_by_identifier(session, tenant_id, identifier)
    return _association_grouping_to_schema(obj) if obj else None


async def list_cf_association_groupings(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CFAssociationGroupingDType]:
    objs = await cf_association_grouping_repository.list_all(session, tenant_id, limit, offset)
    return [_association_grouping_to_schema(o) for o in objs]
