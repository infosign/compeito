import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFDocument(Base):
    __tablename__ = "cf_documents"
    __table_args__ = (UniqueConstraint("tenant_id", "identifier", name="uq_cf_documents_tenant_identifier"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    cf_license_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_licenses.id", ondelete="SET NULL")
    )
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    creator: Mapped[str | None] = mapped_column(String)
    publisher: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    framework_type: Mapped[str | None] = mapped_column(String)
    case_version: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String(10))
    version: Mapped[str | None] = mapped_column(String)
    adoption_status: Mapped[str | None] = mapped_column(String)
    status_start_date: Mapped[date | None] = mapped_column(Date)
    status_end_date: Mapped[date | None] = mapped_column(Date)
    official_source_url: Mapped[str | None] = mapped_column(String)
    subject: Mapped[dict | None] = mapped_column(JSONB)
    subject_uri: Mapped[dict | None] = mapped_column(JSONB)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", back_populates="cf_documents")
    license = relationship("CFLicense", back_populates="cf_documents")
    cf_items = relationship("CFItem", back_populates="cf_document", cascade="all, delete-orphan")
    cf_associations = relationship("CFAssociation", back_populates="cf_document", cascade="all, delete-orphan")
    cf_rubrics = relationship("CFRubric", back_populates="cf_document", cascade="all, delete-orphan")
