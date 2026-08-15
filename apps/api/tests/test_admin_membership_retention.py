"""Focused unchanged Platform Administration membership alignment."""

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.models import User
from mist_service.team_membership_admin import align_admin_workspace_memberships
from mist_service.team_models import TeamMembership, WorkspacePosition


async def test_admin_alignment_retains_exact_current_membership(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    user_id = await harness.user_id("admin11")
    actor_id = await harness.user_id("admin1")
    team_id = await harness.unit_id("SSG_TEAM")
    async with harness.sessions() as session, session.begin():
        user = await session.get(User, user_id)
        membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.team_id == team_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert user is not None and membership is not None
        original_id, original_version = membership.id, membership.version
        await align_admin_workspace_memberships(
            session,
            user=user,
            next_unit_ids={team_id},
            workspace_position=WorkspacePosition.MEMBER,
            actor_id=actor_id,
        )
        retained = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert retained is not None
        assert (retained.id, retained.version) == (original_id, original_version)
