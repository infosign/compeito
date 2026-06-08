import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFRubric(Base):
    __tablename__ = "cf_rubrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier", name="uq_cf_rubrics_tenant_identifier"),
        Index("ix_cf_rubrics_document", "cf_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    cf_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_documents.id", ondelete="CASCADE"), nullable=False
    )
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    extensions: Mapped[dict | None] = mapped_column(JSONB)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", back_populates="cf_rubrics")
    cf_document = relationship("CFDocument", back_populates="cf_rubrics")
    criteria = relationship("CFRubricCriterion", back_populates="cf_rubric", cascade="all, delete-orphan")
