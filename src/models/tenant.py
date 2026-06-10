import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        # 2-64 chars; lowercase letters / digits / hyphens; must start AND end
        # with an alphanumeric character (no leading / trailing hyphen).
        CheckConstraint(
            "slug IS NULL OR slug ~ '^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$'",
            name="ck_tenants_slug_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # URL-friendly short alias used in public URLs as an alternative to `id`.
    # Optional and nullable. UUID remains the canonical identifier: CASE clients
    # (OBF, TAO, etc.) read `LinkURIDType.identifier` / `uri`, which always carry
    # the UUID — the slug is a Web UI / share-link convenience only.
    slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Optional manual display order for the public tenant list. Smaller = higher;
    # NULL sinks below explicitly-ordered tenants (then name ASC). compeito-local
    # display concern — not a CASE field.
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @property
    def slug_or_id(self) -> str:
        """Preferred URL segment for navigation links.

        Returns the slug if set, else the UUID as a string. Templates and
        link-generation code should use this; permalink and CASE-API URL
        display should use `id` (UUID) directly because those identify a
        resource canonically and must not change when a slug is renamed.
        """
        return self.slug if self.slug else str(self.id)

    cf_documents = relationship("CFDocument", back_populates="tenant", cascade="all, delete-orphan")
    cf_items = relationship("CFItem", back_populates="tenant", cascade="all, delete-orphan")
    cf_associations = relationship("CFAssociation", back_populates="tenant", cascade="all, delete-orphan")
    cf_item_types = relationship("CFItemType", back_populates="tenant", cascade="all, delete-orphan")
    cf_subjects = relationship("CFSubject", back_populates="tenant", cascade="all, delete-orphan")
    cf_concepts = relationship("CFConcept", back_populates="tenant", cascade="all, delete-orphan")
    cf_licenses = relationship("CFLicense", back_populates="tenant", cascade="all, delete-orphan")
    cf_association_groupings = relationship(
        "CFAssociationGrouping", back_populates="tenant", cascade="all, delete-orphan"
    )
    cf_rubrics = relationship("CFRubric", back_populates="tenant", cascade="all, delete-orphan")
