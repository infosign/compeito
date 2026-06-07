import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_association import CFAssociation
from src.models.cf_document import CFDocument
from src.models.cf_item import CFItem
from src.models.cf_subject import CFSubject
from src.repositories import cf_rubric_repository
from src.schemas.cf_association_grouping import CFAssociationGroupingDType
from src.schemas.cf_concept import CFConceptDType
from src.schemas.cf_document import CFPckgDocumentDType
from src.schemas.cf_item import CFPckgItemDType
from src.schemas.cf_item_type import CFItemTypeDType
from src.schemas.cf_license import CFLicenseDType
from src.schemas.cf_package import CFDefinitionsDType, CFPackageDType
from src.schemas.cf_subject import CFSubjectDType
from src.schemas.common import LinkURIType
from src.services.case_query_service import (
    _build_concept_keywords_uri,
    _build_document_uri,
    _build_item_type_uri,
    _build_license_uri_from_model,
    _build_subject_uri_list,
    association_to_pckg_schema,
    rubric_to_schema,
)


def _pckg_document_to_schema(doc: CFDocument) -> CFPckgDocumentDType:
    return CFPckgDocumentDType(
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
        lastChangeDateTime=doc.last_change_date_time,
    )


def _pckg_item_to_schema(item: CFItem, doc_uri: LinkURIType) -> CFPckgItemDType:
    return CFPckgItemDType(
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
        CFDocumentURI=doc_uri,
        lastChangeDateTime=item.last_change_date_time,
    )


def _collect_subject_identifiers(doc: CFDocument, items: list[CFItem]) -> set[str]:
    """Collect subject identifiers from document and items subject_uri JSON."""
    ids: set[str] = set()
    if doc.subject_uri:
        for su in doc.subject_uri:
            sid = su.get("identifier")
            if sid:
                ids.add(sid)
    for item in items:
        if item.subject_uri:
            for su in item.subject_uri:
                sid = su.get("identifier")
                if sid:
                    ids.add(sid)
    return ids


def _build_definitions(
    doc: CFDocument,
    items: list[CFItem],
    associations: list[CFAssociation],
    subjects: list[CFSubject],
) -> CFDefinitionsDType | None:
    """Build CFDefinitions from referenced lookup resources."""
    item_types_seen: dict[str, object] = {}
    concepts_seen: dict[str, object] = {}
    licenses_seen: dict[str, object] = {}
    groupings_seen: dict[str, object] = {}

    # Document license
    if doc.license is not None:
        licenses_seen[str(doc.license.identifier)] = doc.license

    for item in items:
        if item.item_type is not None:
            item_types_seen[str(item.item_type.identifier)] = item.item_type
        if item.concept is not None:
            concepts_seen[str(item.concept.identifier)] = item.concept
        if item.license is not None:
            licenses_seen[str(item.license.identifier)] = item.license

    for assoc in associations:
        if assoc.association_grouping is not None:
            groupings_seen[str(assoc.association_grouping.identifier)] = assoc.association_grouping

    # Build schema lists (only if non-empty)
    cf_item_types = (
        sorted(
            [
                CFItemTypeDType(
                    identifier=str(it.identifier),
                    uri=it.uri,
                    title=it.title,
                    description=it.description,
                    typeCode=it.type_code,
                    hierarchyCode=it.hierarchy_code,
                    lastChangeDateTime=it.last_change_date_time,
                )
                for it in item_types_seen.values()
            ],
            key=lambda x: x.identifier,
        )
        or None
    )

    cf_concepts = (
        sorted(
            [
                CFConceptDType(
                    identifier=str(c.identifier),
                    uri=c.uri,
                    title=c.title,
                    description=c.description,
                    keywords=c.keywords,
                    hierarchyCode=c.hierarchy_code,
                    lastChangeDateTime=c.last_change_date_time,
                )
                for c in concepts_seen.values()
            ],
            key=lambda x: x.identifier,
        )
        or None
    )

    cf_licenses = (
        sorted(
            [
                CFLicenseDType(
                    identifier=str(lic.identifier),
                    uri=lic.uri,
                    title=lic.title,
                    description=lic.description,
                    licenseText=lic.license_text,
                    lastChangeDateTime=lic.last_change_date_time,
                )
                for lic in licenses_seen.values()
            ],
            key=lambda x: x.identifier,
        )
        or None
    )

    cf_subjects = (
        sorted(
            [
                CFSubjectDType(
                    identifier=str(s.identifier),
                    uri=s.uri,
                    title=s.title,
                    description=s.description,
                    hierarchyCode=s.hierarchy_code,
                    lastChangeDateTime=s.last_change_date_time,
                )
                for s in subjects
            ],
            key=lambda x: x.identifier,
        )
        or None
    )

    cf_association_groupings = (
        sorted(
            [
                CFAssociationGroupingDType(
                    identifier=str(g.identifier),
                    uri=g.uri,
                    title=g.title,
                    description=g.description,
                    lastChangeDateTime=g.last_change_date_time,
                )
                for g in groupings_seen.values()
            ],
            key=lambda x: x.identifier,
        )
        or None
    )

    defs = CFDefinitionsDType(
        CFItemTypes=cf_item_types,
        CFSubjects=cf_subjects,
        CFConcepts=cf_concepts,
        CFLicenses=cf_licenses,
        CFAssociationGroupings=cf_association_groupings,
    )
    # If all None → return None (no CFDefinitions key)
    serialized = defs.model_dump(by_alias=True)
    if not serialized:
        return None
    return defs


async def get_cf_package(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identifier: uuid.UUID,
) -> CFPackageDType | None:
    # 1. Get document
    result = await session.execute(
        select(CFDocument)
        .options(joinedload(CFDocument.license))
        .where(CFDocument.tenant_id == tenant_id, CFDocument.identifier == identifier)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        return None

    # 2. Get items for this document
    items_result = await session.execute(
        select(CFItem)
        .options(
            joinedload(CFItem.item_type),
            joinedload(CFItem.license),
            joinedload(CFItem.concept),
        )
        .where(CFItem.cf_document_id == doc.id)
        .order_by(CFItem.identifier)
    )
    items = list(items_result.scalars().unique().all())

    # 3. Get associations for this document
    assocs_result = await session.execute(
        select(CFAssociation)
        .options(joinedload(CFAssociation.association_grouping))
        .where(CFAssociation.cf_document_id == doc.id)
        .order_by(CFAssociation.identifier)
    )
    assocs = list(assocs_result.scalars().unique().all())

    # 4. Get referenced subjects from DB
    subject_ids = _collect_subject_identifiers(doc, items)
    subjects: list[CFSubject] = []
    if subject_ids:
        subject_uuids = []
        for sid in subject_ids:
            try:
                subject_uuids.append(uuid.UUID(sid))
            except (ValueError, AttributeError):
                pass
        if subject_uuids:
            subj_result = await session.execute(
                select(CFSubject)
                .where(
                    CFSubject.tenant_id == tenant_id,
                    CFSubject.identifier.in_(subject_uuids),
                )
                .order_by(CFSubject.identifier)
            )
            subjects = list(subj_result.scalars().all())

    # 5. Get rubrics for this document
    rubrics = await cf_rubric_repository.list_by_document(session, doc.id)

    # 6. Build package
    doc_uri = _build_document_uri(doc)
    return CFPackageDType(
        CFDocument=_pckg_document_to_schema(doc),
        CFItems=[_pckg_item_to_schema(item, doc_uri) for item in items],
        CFAssociations=[association_to_pckg_schema(a) for a in assocs],
        CFDefinitions=_build_definitions(doc, items, assocs, subjects),
        CFRubrics=[rubric_to_schema(r) for r in rubrics],
    )
