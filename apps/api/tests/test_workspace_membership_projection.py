"""Effective workspace membership projection edge behaviour."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.models import User
from mist_service.organisation_models import UserOrganisationMembership
from mist_service.team_membership_projection import refresh_membership_projection
from mist_service.team_membership_sync import synchronise_due_team_memberships
from mist_service.team_models import TeamMembership


async def test_projection_selects_a_stable_unit_when_no_preference_is_supplied(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    user_id = await harness.user_id("admin5")
    async with harness.sessions() as session, session.begin():
        user = await session.get(User, user_id)
        assert user is not None
        await refresh_membership_projection(
            session,
            user=user,
            preferred_unit=None,
            affected_unit_ids=set(),
        )
        projected = set(
            await session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == user_id
                )
            )
        )
        assert len(projected) == 3
        assert user.scope == "DIGOC"


async def test_due_boundary_marks_an_unchanged_projection_without_rewriting_it(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    user_id = await harness.user_id("admin75")
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert membership is not None
        membership.start_projected_at = None
        await session.flush()
        assert await synchronise_due_team_memberships(session, at=now) == 1
        assert membership.start_projected_at == now
