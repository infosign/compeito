import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFAssociation(Base):
    __tablename__ = "cf_associations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier", name="uq_cf_associations_tenant_identifier"),
        Index("ix_cf_associations_origin_node", "origin_node_identifier"),
        Index("ix_cf_associations_destination_node", "destination_node_identifier"),
        Index("ix_cf_associations_document_destination", "cf_document_id", "destination_node_identifier"),
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
    association_type: Mapped[str] = mapped_column(String, nullable=False)
    origin_node_uri: Mapped[str] = mapped_column(String, nullable=False)
    origin_node_identifier: Mapped[str] = mapped_column(String, nullable=False)
    origin_node_title: Mapped[str | None] = mapped_column(String)
    origin_node_target_type: Mapped[str | None] = mapped_column(String)
    destination_node_uri: Mapped[str] = mapped_column(String, nullable=False)
    destination_node_identifier: Mapped[str] = mapped_column(String, nullable=False)
    destination_node_title: Mapped[str | None] = mapped_column(String)
    destination_node_target_type: Mapped[str | None] = mapped_column(String)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    cf_association_grouping_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_association_groupings.id", ondelete="SET NULL")
    )
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", back_populates="cf_associations")
    cf_document = relationship("CFDocument", back_populates="cf_associations")
    association_grouping = relationship("CFAssociationGrouping", back_populates="cf_associations")
