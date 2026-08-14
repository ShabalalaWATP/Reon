"""Transactional request leadership and contributor persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import InvalidAction
from istari_service.models import ServiceRequest, User, UserRole
from istari_service.request_participant_models import (
    RequestParticipant,
    RequestParticipantRole,
)
from istari_service.schemas.requests import RequesterView
from istari_service.team_models import TeamMembership


def eligible_participant_condition(
    request_id: Any,
    user_id: Any,
    at: Any,
) -> ColumnElement[bool]:
    """Require an effective participant and live membership in the assigned team."""

    return exists(
        select(RequestParticipant.user_id)
        .join(ServiceRequest, ServiceRequest.id == RequestParticipant.request_id)
        .join(User, User.id == RequestParticipant.user_id)
        .join(
            TeamMembership,
            and_(
                TeamMembership.user_id == RequestParticipant.user_id,
                TeamMembership.team_id == ServiceRequest.assigned_delivery_team_id,
            ),
        )
        .where(
            RequestParticipant.request_id == request_id,
            RequestParticipant.user_id == user_id,
            RequestParticipant.effective_from <= at,
            RequestParticipant.ended_at.is_(None),
            ServiceRequest.assigned_delivery_team_id.is_not(None),
            User.is_active.is_(True),
            User.role == UserRole.DELIVERY_SPECIALIST,
            TeamMembership.effective_from <= at,
            or_(
                TeamMembership.effective_until.is_(None),
                TeamMembership.effective_until > at,
            ),
        )
    )


async def replace_request_participants(
    session: AsyncSession,
    *,
    request_id: UUID,
    lead_id: UUID,
    contributor_ids: list[UUID],
    actor_id: UUID,
    reason: str,
) -> None:
    now = datetime.now(UTC)
    current = list(
        await session.scalars(
            select(RequestParticipant)
            .where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.ended_at.is_(None),
            )
            .with_for_update()
        )
    )
    for participant in current:
        participant.ended_at = now
        participant.ended_by_user_id = actor_id
        participant.end_reason = reason.strip()
        participant.version += 1
    session.add(
        RequestParticipant(
            request_id=request_id,
            user_id=lead_id,
            role=RequestParticipantRole.LEAD,
            assigned_by_user_id=actor_id,
            reason=reason.strip(),
            effective_from=now,
        )
    )
    session.add_all(
        RequestParticipant(
            request_id=request_id,
            user_id=user_id,
            role=RequestParticipantRole.CONTRIBUTOR,
            assigned_by_user_id=actor_id,
            reason=reason.strip(),
            effective_from=now,
        )
        for user_id in contributor_ids
    )
    await session.flush()


async def active_participant_ids(
    session: AsyncSession, request_id: UUID
) -> frozenset[UUID]:
    return frozenset(
        await session.scalars(
            select(RequestParticipant.user_id).where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.ended_at.is_(None),
            )
        )
    )


async def eligible_participant_ids(
    session: AsyncSession,
    request: ServiceRequest,
) -> frozenset[UUID]:
    """Return current participants who still satisfy delivery authority."""

    if request.assigned_delivery_team_id is None:
        return frozenset()
    now = datetime.now(UTC)
    return frozenset(
        await session.scalars(
            select(RequestParticipant.user_id)
            .join(User, User.id == RequestParticipant.user_id)
            .join(
                TeamMembership,
                TeamMembership.user_id == RequestParticipant.user_id,
            )
            .where(
                RequestParticipant.request_id == request.id,
                RequestParticipant.ended_at.is_(None),
                RequestParticipant.effective_from <= now,
                User.is_active.is_(True),
                User.role == UserRole.DELIVERY_SPECIALIST,
                TeamMembership.team_id == request.assigned_delivery_team_id,
                TeamMembership.effective_from <= now,
                (
                    TeamMembership.effective_until.is_(None)
                    | (TeamMembership.effective_until > now)
                ),
            )
        )
    )


async def validate_request_participants(
    session: AsyncSession,
    request: ServiceRequest,
) -> frozenset[UUID]:
    """Lock and reject a stale lead or contributor at the command boundary."""

    participant_ids = set(
        await session.scalars(
            select(RequestParticipant.user_id).where(
                RequestParticipant.request_id == request.id,
                RequestParticipant.ended_at.is_(None),
            )
        )
    )
    if not participant_ids or request.assigned_delivery_team_id is None:
        raise InvalidAction()
    users = (
        await session.execute(
            select(User.id, User.is_active, User.role)
            .where(User.id.in_(participant_ids))
            .order_by(User.id)
            .with_for_update()
        )
    ).all()
    now = datetime.now(UTC)
    membership_user_ids = set(
        await session.scalars(
            select(TeamMembership.user_id)
            .where(
                TeamMembership.user_id.in_(participant_ids),
                TeamMembership.team_id == request.assigned_delivery_team_id,
                TeamMembership.effective_from <= now,
                (
                    TeamMembership.effective_until.is_(None)
                    | (TeamMembership.effective_until > now)
                ),
            )
            .order_by(TeamMembership.user_id, TeamMembership.id)
            .with_for_update()
        )
    )
    participants = (
        await session.execute(
            select(RequestParticipant.user_id, RequestParticipant.role)
            .where(
                RequestParticipant.request_id == request.id,
                RequestParticipant.ended_at.is_(None),
            )
            .order_by(RequestParticipant.user_id, RequestParticipant.id)
            .with_for_update()
        )
    ).all()
    locked_participant_ids = {item.user_id for item in participants}
    eligible = {
        user.id
        for user in users
        if user.is_active and user.role is UserRole.DELIVERY_SPECIALIST
    } & membership_user_ids
    leads = [item for item in participants if item.role is RequestParticipantRole.LEAD]
    if (
        len(leads) != 1
        or request.assigned_specialist_id != leads[0].user_id
        or locked_participant_ids != participant_ids
        or eligible != locked_participant_ids
    ):
        raise InvalidAction()
    return frozenset(eligible)


async def validate_participant_selection(
    session: AsyncSession,
    *,
    team_id: UUID | None,
    lead_id: UUID,
    contributor_ids: list[UUID],
) -> None:
    """Lock and validate every proposed participant against the exact team."""

    selected = {lead_id, *contributor_ids}
    if team_id is None or len(selected) != 1 + len(contributor_ids):
        raise InvalidAction()
    now = datetime.now(UTC)
    users = set(
        await session.scalars(
            select(User.id)
            .where(
                User.id.in_(selected),
                User.is_active.is_(True),
                User.role == UserRole.DELIVERY_SPECIALIST,
            )
            .with_for_update()
        )
    )
    memberships = set(
        await session.scalars(
            select(TeamMembership.user_id)
            .where(
                TeamMembership.user_id.in_(selected),
                TeamMembership.team_id == team_id,
                TeamMembership.effective_from <= now,
                (
                    TeamMembership.effective_until.is_(None)
                    | (TeamMembership.effective_until > now)
                ),
            )
            .with_for_update()
        )
    )
    if users != selected or memberships != selected:
        raise InvalidAction()


async def active_contributor_views(
    session: AsyncSession, request_id: UUID
) -> list[RequesterView]:
    rows = (
        await session.execute(
            select(User.id, User.display_name)
            .join(RequestParticipant, RequestParticipant.user_id == User.id)
            .where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.role == RequestParticipantRole.CONTRIBUTOR,
                RequestParticipant.ended_at.is_(None),
                User.is_active.is_(True),
            )
            .order_by(User.display_name, User.id)
        )
    ).all()
    return [RequesterView(id=user_id, display_name=name) for user_id, name in rows]
