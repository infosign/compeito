import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CFRubricCriterionLevel(Base):
    __tablename__ = "cf_rubric_criterion_levels"
    __table_args__ = (
        UniqueConstraint(
            "cf_rubric_criterion_id", "identifier", name="uq_cf_rubric_criterion_levels_criterion_identifier"
        ),
        Index("ix_cf_rubric_criterion_levels_criterion", "cf_rubric_criterion_id"),
        Index("ix_cf_rubric_criterion_levels_identifier", "identifier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cf_rubric_criterion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cf_rubric_criteria.id", ondelete="CASCADE"), nullable=False
    )
    rubric_criterion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str | None] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer)
    last_change_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cf_rubric_criterion = relationship("CFRubricCriterion", back_populates="levels")
