"""Explicit, action-specific management authority and hierarchy closure."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, UUID_TYPE, Base, TimestampMixin, _enum


class ManagementAction(StrEnum):
    STATISTICS = "STATISTICS"
    ROSTER = "ROSTER"
    CALENDAR = "CALENDAR"
    BOARD = "BOARD"
    CAPACITY = "CAPACITY"


class OrganisationClosure(Base):
    __tablename__ = "organisation_closure"
    __table_args__ = (
        CheckConstraint("depth >= 0", name="organisation_closure_depth"),
        Index("ix_organisation_closure_descendant", "descendant_id", "depth"),
    )

    ancestor_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), primary_key=True
    )
    descendant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), primary_key=True
    )
    depth: Mapped[int] = mapped_column(Integer)


class ManagementGrant(TimestampMixin, Base):
    __tablename__ = "management_grants"
    __table_args__ = (
        CheckConstraint("version > 0", name="management_grant_version"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="management_grant_effective_window",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL "
            "AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND revocation_reason IS NOT NULL)",
            name="management_grant_revocation_shape",
        ),
        Index(
            "ix_management_grants_subject_window",
            "subject_user_id",
            "effective_from",
            "effective_until",
        ),
    )

    subject_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    root_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    include_descendants: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    effective_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    granted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(Text)
    supersedes_grant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("management_grants.id", ondelete="RESTRICT")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ManagementGrantAction(Base):
    __tablename__ = "management_grant_actions"

    grant_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("management_grants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    action: Mapped[ManagementAction] = mapped_column(
        _enum(ManagementAction, "management_action"), primary_key=True
    )


MANAGEMENT_SEED_REASON = "Synthetic local management authority fixture."
