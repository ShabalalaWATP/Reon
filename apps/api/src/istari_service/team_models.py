"""Effective-dated organisation membership and immutable workspace activity."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base, CreatedMixin, TimestampMixin, _enum


class TeamActivityType(StrEnum):
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBERSHIP_ENDED = "MEMBERSHIP_ENDED"
    TRANSFER_SCHEDULED = "TRANSFER_SCHEDULED"
    TRANSFER_ACTIVATED = "TRANSFER_ACTIVATED"


class WorkspacePosition(StrEnum):
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


class TeamMembership(TimestampMixin, Base):
    """Authoritative workspace membership for every organisation-unit kind.

    The legacy table and ``team_id`` column names are retained for a safe rolling
    migration. They now contain any organisation unit, not only delivery teams.
    """

    __tablename__ = "team_memberships"
    __table_args__ = (
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="team_membership_effective_window",
        ),
        CheckConstraint("version > 0", name="team_membership_version"),
        Index(
            "uq_team_memberships_one_open",
            "user_id",
            "team_id",
            unique=True,
            sqlite_where=text("effective_until IS NULL"),
            postgresql_where=text("effective_until IS NULL"),
        ),
        Index(
            "ix_team_memberships_team_window",
            "team_id",
            "effective_from",
            "effective_until",
        ),
        Index(
            "ix_team_memberships_due_start",
            "effective_from",
            "user_id",
            sqlite_where=text("start_projected_at IS NULL"),
            postgresql_where=text("start_projected_at IS NULL"),
        ),
        Index(
            "ix_team_memberships_due_end",
            "effective_until",
            "user_id",
            sqlite_where=text(
                "end_projected_at IS NULL AND effective_until IS NOT NULL"
            ),
            postgresql_where=text(
                "end_projected_at IS NULL AND effective_until IS NOT NULL"
            ),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    workspace_position: Mapped[WorkspacePosition] = mapped_column(
        _enum(WorkspacePosition, "workspace_position"),
        default=WorkspacePosition.MEMBER,
        server_default=WorkspacePosition.MEMBER.value,
        index=True,
    )
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    effective_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    start_projected_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    end_projected_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    started_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    start_reason: Mapped[str] = mapped_column(Text)
    ended_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    end_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class TeamActivityEvent(CreatedMixin, Base):
    __tablename__ = "team_activity_events"
    __table_args__ = (Index("ix_team_activity_team_created", "team_id", "created_at"),)

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    subject_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("team_memberships.id", ondelete="RESTRICT")
    )
    type: Mapped[TeamActivityType] = mapped_column(
        _enum(TeamActivityType, "team_activity_type"), index=True
    )
    summary: Mapped[str] = mapped_column(String(240))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
