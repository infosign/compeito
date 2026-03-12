import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFItem(Base):
    __tablename__ = "cf_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier", name="uq_cf_items_tenant_identifier"),
        Index("ix_cf_items_tenant_document_coding", "tenant_id", "cf_document_id", "human_coding_scheme"),
        Index("ix_cf_items_document_depth", "cf_document_id", "depth"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    cf_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_documents.id", ondelete="CASCADE"), nullable=False
    )
    cf_item_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_item_types.id", ondelete="SET NULL")
    )
    cf_license_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_licenses.id", ondelete="SET NULL")
    )
    cf_concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_concepts.id", ondelete="SET NULL")
    )
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    full_statement: Mapped[str] = mapped_column(Text, nullable=False)
    human_coding_scheme: Mapped[str | None] = mapped_column(String)
    list_enumeration: Mapped[str | None] = mapped_column(String)
    abbreviated_statement: Mapped[str | None] = mapped_column(Text)
    concept_keywords: Mapped[dict | None] = mapped_column(JSONB)
    education_level: Mapped[dict | None] = mapped_column(JSONB)
    subject: Mapped[dict | None] = mapped_column(JSONB)
    subject_uri: Mapped[dict | None] = mapped_column(JSONB)
    language: Mapped[str | None] = mapped_column(String(10))
    status_start_date: Mapped[date | None] = mapped_column(Date)
    status_end_date: Mapped[date | None] = mapped_column(Date)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", back_populates="cf_items")
    cf_document = relationship("CFDocument", back_populates="cf_items")
    item_type = relationship("CFItemType", back_populates="cf_items")
    license = relationship("CFLicense", back_populates="cf_items")
    concept = relationship("CFConcept", back_populates="cf_items")
