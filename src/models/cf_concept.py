import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFConcept(Base):
    __tablename__ = "cf_concepts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier", name="uq_cf_concepts_tenant_identifier"),
        Index("ix_cf_concepts_tenant_title", "tenant_id", "title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    keywords: Mapped[str | None] = mapped_column(String)
    hierarchy_code: Mapped[str | None] = mapped_column(String)

    tenant = relationship("Tenant", back_populates="cf_concepts")
    cf_items = relationship("CFItem", back_populates="concept")
