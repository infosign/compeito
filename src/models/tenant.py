import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    cf_documents = relationship("CFDocument", back_populates="tenant", cascade="all, delete-orphan")
    cf_items = relationship("CFItem", back_populates="tenant", cascade="all, delete-orphan")
    cf_associations = relationship("CFAssociation", back_populates="tenant", cascade="all, delete-orphan")
    cf_item_types = relationship("CFItemType", back_populates="tenant", cascade="all, delete-orphan")
    cf_subjects = relationship("CFSubject", back_populates="tenant", cascade="all, delete-orphan")
    cf_concepts = relationship("CFConcept", back_populates="tenant", cascade="all, delete-orphan")
    cf_licenses = relationship("CFLicense", back_populates="tenant", cascade="all, delete-orphan")
    cf_association_groupings = relationship("CFAssociationGrouping", back_populates="tenant", cascade="all, delete-orphan")
    cf_rubrics = relationship("CFRubric", back_populates="tenant", cascade="all, delete-orphan")
