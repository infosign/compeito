import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFRubricCriterion(Base):
    __tablename__ = "cf_rubric_criteria"
    __table_args__ = (
        UniqueConstraint("cf_rubric_id", "identifier", name="uq_cf_rubric_criteria_rubric_identifier"),
        Index("ix_cf_rubric_criteria_rubric", "cf_rubric_id"),
        Index("ix_cf_rubric_criteria_identifier", "identifier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cf_rubric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_rubrics.id", ondelete="CASCADE"), nullable=False
    )
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    cf_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_items.id", ondelete="SET NULL")
    )
    # Verbatim copy of the source CFItemURI.uri at import time. CFPackage
    # exports denormalize the linked CFItem's uri into each CFRubricCriterion;
    # if the upstream system (e.g., OpenCASE) doesn't re-resolve those links
    # when CFItem.uri changes, the denormalized value diverges from the live
    # CFItem.uri. Preserving it here keeps OpenCASE → compeito → OpenCASE
    # round-trip lossless. NULL falls back to `cf_item.uri` at emit time.
    cf_item_uri_source: Mapped[str | None] = mapped_column(Text)
    rubric_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    category: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float | None] = mapped_column(Float)
    position: Mapped[int | None] = mapped_column(Integer)
    rubric_criterion_text_plain: Mapped[str | None] = mapped_column(Text)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cf_rubric = relationship("CFRubric", back_populates="criteria")
    cf_item = relationship("CFItem")
    levels = relationship("CFRubricCriterionLevel", back_populates="cf_rubric_criterion", cascade="all, delete-orphan")
