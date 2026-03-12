"""CASE v1.1 API router aggregator.

Collects all CASE API sub-routers for registration in main.py.
"""

from fastapi import APIRouter

from src.routers.cf_association_groupings import router as cf_association_groupings_router
from src.routers.cf_associations import router as cf_associations_router
from src.routers.cf_concepts import router as cf_concepts_router
from src.routers.cf_documents import router as cf_documents_router
from src.routers.cf_item_types import router as cf_item_types_router
from src.routers.cf_items import router as cf_items_router
from src.routers.cf_licenses import router as cf_licenses_router
from src.routers.cf_packages import router as cf_packages_router
from src.routers.cf_subjects import router as cf_subjects_router

router = APIRouter()
router.include_router(cf_documents_router)
router.include_router(cf_items_router)
router.include_router(cf_associations_router)
router.include_router(cf_packages_router)
router.include_router(cf_item_types_router)
router.include_router(cf_concepts_router)
router.include_router(cf_subjects_router)
router.include_router(cf_licenses_router)
router.include_router(cf_association_groupings_router)
