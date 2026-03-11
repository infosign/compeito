import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.cf_document import CFDocument
from src.repositories import cf_document_repository
from src.schemas.cf_document import CFDocumentDType
from src.schemas.common import LinkURIType


def _build_cf_package_uri(tenant_id: uuid.UUID, doc: CFDocument) -> LinkURIType:
    return LinkURIType(
        title=doc.title,
        identifier=str(doc.identifier),
        uri=f"{settings.base_url}/{tenant_id}/ims/case/v1p1/CFPackages/{doc.identifier}",
    )


def _build_license_uri(doc: CFDocument) -> LinkURIType | None:
    if doc.license is None:
        return None
    return LinkURIType(
        title=doc.license.title,
        identifier=str(doc.license.identifier),
        uri=doc.license.uri,
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
        licenseURI=_build_license_uri(doc),
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
