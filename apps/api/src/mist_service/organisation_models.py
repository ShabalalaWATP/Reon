"""Relational organisation hierarchy and per-request routing selections."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.models import Base, CreatedMixin, TimestampMixin, _enum


class OrganisationKind(StrEnum):
    ROOT = "ROOT"
    COMMAND = "COMMAND"
    OPS_GROUP = "OPS_GROUP"
    TEAM = "TEAM"


class StaffingStatus(StrEnum):
    ROUTING_POOL = "ROUTING_POOL"
    STAFFED = "STAFFED"
    UNSTAFFED = "UNSTAFFED"


class OrganisationUnit(TimestampMixin, Base):
    __tablename__ = "organisation_units"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'ROOT' AND parent_id IS NULL) OR "
            "(kind <> 'ROOT' AND parent_id IS NOT NULL)",
            name="organisation_parent_shape",
        ),
        CheckConstraint(
            "(kind = 'TEAM' AND staffing_status IN ('STAFFED', 'UNSTAFFED')) OR "
            "(kind <> 'TEAM' AND staffing_status = 'ROUTING_POOL')",
            name="organisation_staffing_shape",
        ),
        CheckConstraint(
            "(kind = 'TEAM' AND routing_candidate_group IS NULL "
            "AND manager_candidate_group IS NOT NULL "
            "AND analyst_candidate_group IS NOT NULL) OR "
            "(kind <> 'TEAM' AND routing_candidate_group IS NOT NULL "
            "AND manager_candidate_group IS NULL "
            "AND analyst_candidate_group IS NULL)",
            name="organisation_candidate_group_shape",
        ),
    )

    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[OrganisationKind] = mapped_column(
        _enum(OrganisationKind, "organisation_kind"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    staffing_status: Mapped[StaffingStatus] = mapped_column(
        _enum(StaffingStatus, "staffing_status")
    )
    routing_candidate_group: Mapped[str | None] = mapped_column(String(120))
    manager_candidate_group: Mapped[str | None] = mapped_column(String(120))
    analyst_candidate_group: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_configured: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class RequestRouteSelection(CreatedMixin, Base):
    __tablename__ = "request_route_selections"
    __table_args__ = (
        UniqueConstraint("request_id", "position"),
        CheckConstraint("position BETWEEN 0 AND 3", name="route_position_range"),
        Index(
            "ix_request_routes_unit_position_request",
            "unit_id",
            "position",
            "request_id",
        ),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)


class UserOrganisationMembership(CreatedMixin, Base):
    __tablename__ = "user_organisation_memberships"
    __table_args__ = (UniqueConstraint("user_id", "unit_id"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
