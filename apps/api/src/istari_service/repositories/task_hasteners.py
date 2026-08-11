"""Persistence queries for exact-team task hasteners."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import ServiceRequest, User, UserRole
from istari_service.request_participant_models import RequestParticipant
from istari_service.schemas.task_hasteners import TaskHastenerRecipient
from istari_service.team_models import TeamMembership


class SqlAlchemyTaskHastenerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request_for_team(
        self, team_id: UUID, request_id: UUID
    ) -> ServiceRequest | None:
        return cast(
            ServiceRequest | None,
            await self.session.scalar(
                select(ServiceRequest).where(
                    ServiceRequest.id == request_id,
                    ServiceRequest.assigned_delivery_team_id == team_id,
                )
            ),
        )

    async def active_recipients(
        self, team_id: UUID, request_id: UUID
    ) -> list[TaskHastenerRecipient]:
        now = datetime.now(UTC)
        rows = (
            await self.session.execute(
                select(User.id, User.display_name, RequestParticipant.role)
                .join(RequestParticipant, RequestParticipant.user_id == User.id)
                .join(
                    TeamMembership,
                    TeamMembership.user_id == User.id,
                )
                .where(
                    RequestParticipant.request_id == request_id,
                    RequestParticipant.ended_at.is_(None),
                    TeamMembership.team_id == team_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    User.is_active.is_(True),
                )
            )
        ).all()
        unique = {
            user_id: TaskHastenerRecipient(
                user_id=user_id,
                display_name=display_name,
                assignment_role=assignment_role,
            )
            for user_id, display_name, assignment_role in rows
        }
        return sorted(
            unique.values(),
            key=lambda item: (
                0 if item.assignment_role.value == "LEAD" else 1,
                item.display_name.casefold(),
            ),
        )
