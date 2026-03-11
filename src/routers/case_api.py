"""CASE v1.1 API router aggregator.

Collects all CASE API sub-routers for registration in main.py.
"""

from fastapi import APIRouter

from src.routers.cf_associations import router as cf_associations_router
from src.routers.cf_documents import router as cf_documents_router
from src.routers.cf_items import router as cf_items_router

router = APIRouter()
router.include_router(cf_documents_router)
router.include_router(cf_items_router)
router.include_router(cf_associations_router)
