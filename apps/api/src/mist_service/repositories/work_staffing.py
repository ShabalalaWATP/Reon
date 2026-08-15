"""Effective-dated delivery specialist lookup for work assignment."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.models import User, UserRole
from mist_service.organisation_models import OrganisationUnit
from mist_service.repositories.auth import actor_from_user
from mist_service.team_models import TeamMembership


class WorkStaffingRepositoryMixin:
    _session: AsyncSession

    async def find_specialist(
        self, user_id: UUID, *, delivery_team_id: UUID | None = None
    ) -> Actor | None:
        query = select(User).where(User.id == user_id)
        if delivery_team_id is not None:
            query = query.join(
                TeamMembership,
                TeamMembership.user_id == User.id,
            ).where(
                TeamMembership.team_id == delivery_team_id,
                TeamMembership.effective_from <= datetime.now(UTC),
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > datetime.now(UTC),
                ),
            )
        user = await self._session.scalar(query)
        if user is None or not user.is_active:
            return None
        return actor_from_user(
            user,
            frozenset({delivery_team_id})
            if delivery_team_id is not None
            else frozenset(),
        )

    async def list_active_specialists(
        self, delivery_team: str, *, delivery_team_id: UUID | None = None
    ) -> list[Actor]:
        filters = (
            (TeamMembership.team_id == delivery_team_id,)
            if delivery_team_id is not None
            else (
                User.scope == delivery_team,
                OrganisationUnit.name == delivery_team,
                OrganisationUnit.is_configured.is_(True),
            )
        )
        users = (
            await self._session.scalars(
                select(User)
                .join(
                    TeamMembership,
                    TeamMembership.user_id == User.id,
                )
                .join(
                    OrganisationUnit,
                    OrganisationUnit.id == TeamMembership.team_id,
                )
                .where(
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    User.is_active.is_(True),
                    TeamMembership.effective_from <= datetime.now(UTC),
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > datetime.now(UTC),
                    ),
                    *filters,
                )
                .order_by(User.display_name, User.id)
            )
        ).all()
        memberships = (
            frozenset({delivery_team_id})
            if delivery_team_id is not None
            else frozenset()
        )
        return [actor_from_user(user, memberships) for user in users]
