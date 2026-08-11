"""Worker-owned activation of due team-membership projection changes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.models import User
from istari_service.organisation_models import (
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from istari_service.team_models import TeamActivityType, TeamMembership

DEFAULT_MEMBERSHIP_BATCH = 100


class TeamMembershipProjector:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        batch_size: int = DEFAULT_MEMBERSHIP_BATCH,
    ) -> None:
        self._sessions = sessions
        self._batch_size = batch_size

    async def reconcile_once(self) -> bool:
        async with self._sessions() as session, session.begin():
            return bool(
                await synchronise_due_team_memberships(session, limit=self._batch_size)
            )


async def synchronise_due_team_memberships(
    session: AsyncSession,
    at: datetime | None = None,
    *,
    limit: int = DEFAULT_MEMBERSHIP_BATCH,
) -> int:
    """Apply only due, unprojected timeline boundaries in a bounded batch."""

    effective_at = at or datetime.now(UTC)
    due_rows = list(
        await session.scalars(
            select(TeamMembership)
            .where(_due_boundary(effective_at))
            .order_by(TeamMembership.effective_from, TeamMembership.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    if not due_rows:
        return 0
    user_ids = {row.user_id for row in due_rows}
    users = {
        user.id: user
        for user in await session.scalars(select(User).where(User.id.in_(user_ids)))
    }
    current_rows = list(
        await session.scalars(
            select(TeamMembership).where(
                TeamMembership.user_id.in_(user_ids),
                TeamMembership.effective_from <= effective_at,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > effective_at,
                ),
            )
        )
    )
    current_by_user = {row.user_id: row for row in current_rows}
    team_ids = {row.team_id for row in current_rows}
    teams = {
        team.id: team
        for team in await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.id.in_(team_ids))
        )
    }
    projected_rows = (
        await session.execute(
            select(
                UserOrganisationMembership.user_id,
                UserOrganisationMembership.unit_id,
            ).where(UserOrganisationMembership.user_id.in_(user_ids))
        )
    ).all()
    projected_by_user: dict[UUID, set[UUID]] = {}
    for user_id, unit_id in projected_rows:
        projected_by_user.setdefault(user_id, set()).add(unit_id)

    repository = SqlAlchemyTeamMembershipRepository(session)
    due_by_user = _rows_by_user(due_rows)
    for user_id, boundaries in due_by_user.items():
        current = current_by_user.get(user_id)
        next_ids = {current.team_id} if current is not None else set()
        previous_ids = projected_by_user.get(user_id, set())
        user = users.get(user_id)
        if user is not None and previous_ids != next_ids:
            team = teams.get(current.team_id) if current is not None else None
            await repository._set_projection(
                user, team, previous_ids | next_ids, at=effective_at
            )
            if current is not None and current.start_projected_at is None:
                repository._activity(
                    current,
                    None,
                    TeamActivityType.TRANSFER_ACTIVATED,
                    "A scheduled workspace transfer became effective.",
                )
        _mark_projected(boundaries, effective_at)
    return len(due_by_user)


def _due_boundary(at: datetime) -> ColumnElement[bool]:
    return or_(
        and_(
            TeamMembership.start_projected_at.is_(None),
            TeamMembership.effective_from <= at,
        ),
        and_(
            TeamMembership.end_projected_at.is_(None),
            TeamMembership.effective_until.is_not(None),
            TeamMembership.effective_until <= at,
        ),
    )


def _rows_by_user(rows: list[TeamMembership]) -> dict[UUID, list[TeamMembership]]:
    result: dict[UUID, list[TeamMembership]] = {}
    for row in rows:
        result.setdefault(row.user_id, []).append(row)
    return result


def _mark_projected(rows: list[TeamMembership], at: datetime) -> None:
    for row in rows:
        if row.start_projected_at is None and _aware(row.effective_from) <= at:
            row.start_projected_at = at
        if (
            row.end_projected_at is None
            and row.effective_until is not None
            and _aware(row.effective_until) <= at
        ):
            row.end_projected_at = at


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
