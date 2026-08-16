"""Focused action projection, scope, saved-view and freshness coverage."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from conftest import ApiHarness
from mist_service.action_notification_models import (
    ActionSection,
    ActionSourceType,
    ProjectionHealth,
)
from mist_service.domain import Actor
from mist_service.errors import InvalidAction, ObjectNotFound, StaleVersion
from mist_service.models import User, UserRole
from mist_service.organisation_models import (
    OrganisationUnit,
)
from mist_service.repositories.actions import SqlAlchemyActionRepository
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.repositories.projection_pagination import InvalidProjectionQuery
from mist_service.routers.actions import (
    create_action_view,
    delete_action_view,
    get_actions,
    update_action_view,
)
from mist_service.schemas.actions import (
    ActionColumn,
    ActionFilters,
    SavedActionViewCommand,
    SavedActionViewUpdate,
)
from mist_service.services.action_service import (
    ActionProjectionCommand,
    ActionService,
)
from mist_service.team_models import TeamMembership


async def _actor(harness: ApiHarness, username: str) -> Actor:
    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return await actor_from_user_with_memberships(session, user)


def _command(
    actor: Actor,
    now: datetime,
    *,
    key: str = "task:synthetic:1",
    version: int = 1,
    section: ActionSection = ActionSection.NEEDS_MY_ACTION,
) -> ActionProjectionCommand:
    return ActionProjectionCommand(
        stable_key=key,
        source_type=ActionSourceType.WORKFLOW_TASK,
        source_id=key,
        source_version=version,
        recipient_user_id=actor.id,
        section=section,
        action_type="REVIEW_REQUEST",
        reference=f"SR-{version:04d}",
        safe_title="Synthetic planning summary",
        current_owner="Stored stage owner",
        required_by=now.date() + timedelta(days=3),
        last_changed_at=now - timedelta(days=2),
        deep_link=f"/requests/{uuid4()}?action=review",
        projected_at=now,
    )


@pytest.mark.asyncio
async def test_action_projection_replay_pagination_counts_and_freshness(
    api_harness: ApiHarness,
) -> None:
    actor = await _actor(api_harness, "admin11")
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyActionRepository(session)
        service = ActionService(repository)
        first = await service.project(_command(actor, now))
        replay = await service.project(_command(actor, now, version=1))
        assert replay.id == first.id
        assert replay.version == 1

        updated = await service.project(
            _command(
                actor,
                now + timedelta(seconds=1),
                version=2,
                section=ActionSection.WAITING,
            )
        )
        assert updated.id == first.id
        assert updated.version == 2
        older = await service.project(_command(actor, now, version=1))
        assert older.id == first.id
        assert older.source_version == 2
        await service.project(_command(actor, now, key="task:synthetic:2", version=1))
        await repository.update_checkpoint(
            "actions",
            last_event_key="task:synthetic:2",
            source_changed_at=now,
            projected_at=now,
            pending_count=0,
            failed_count=0,
            health=ProjectionHealth.CURRENT,
        )

        page = await service.workspace(
            actor, ActionFilters(), limit=1, cursor=None, now=now
        )
        assert len(page.items) == 1
        assert page.next_cursor is not None
        assert page.counts.needs_my_action == 1
        assert page.counts.waiting == 1
        assert page.freshness.status is ProjectionHealth.CURRENT
        assert page.items[0].age_days == 1
        assert page.items[0].current_owner == actor.display_name
        next_page = await service.workspace(
            actor,
            ActionFilters(),
            limit=1,
            cursor=page.next_cursor,
            now=now,
        )
        assert len(next_page.items) == 1
        assert next_page.items[0].id != page.items[0].id

        filtered = await service.workspace(
            actor,
            ActionFilters(
                sections=[ActionSection.WAITING],
                action_types=["review_request"],
                due_before=now.date() + timedelta(days=4),
            ),
            limit=10,
            cursor=None,
            now=now,
        )
        assert [item.section for item in filtered.items] == [ActionSection.WAITING]

        with pytest.raises(InvalidProjectionQuery):
            await service.workspace(
                actor, ActionFilters(), limit=10, cursor="invalid", now=now
            )


@pytest.mark.asyncio
async def test_action_role_membership_and_account_are_rechecked(
    api_harness: ApiHarness,
) -> None:
    manager = await _actor(api_harness, "admin8")
    sibling = await _actor(api_harness, "admin21")
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        team_id = await session.scalar(
            select(OrganisationUnit.id).where(OrganisationUnit.code == "SSG_TEAM")
        )
        assert team_id is not None
        repository = SqlAlchemyActionRepository(session)
        await repository.project_action(
            stable_key="team:intake:ssg",
            source_type=ActionSourceType.WORKFLOW_TASK,
            source_id="team-intake",
            source_version=1,
            request_id=None,
            recipient_user_id=None,
            candidate_role=UserRole.DELIVERY_TEAM_LEAD,
            required_scope=None,
            organisation_unit_id=team_id,
            section=ActionSection.NEEDS_MY_ACTION,
            action_type="TEAM_INTAKE",
            reference="SR-TEAM",
            safe_title=None,
            current_owner="OSG Team",
            required_by=None,
            last_changed_at=now,
            completed_at=None,
            deep_link="/me/actions",
            projected_at=now,
        )
        manager_items, _ = await repository.list_actions(
            manager, ActionFilters(), limit=10, cursor=None
        )
        sibling_items, _ = await repository.list_actions(
            sibling, ActionFilters(), limit=10, cursor=None
        )
        assert len(manager_items) == 1
        assert sibling_items == []
        manager_workspace = await ActionService(repository).workspace(
            manager, ActionFilters(), limit=10, cursor=None, now=now
        )
        assert manager_workspace.items[0].current_owner == "OSG Team · Awaiting owner"

        await session.execute(
            delete(TeamMembership).where(
                TeamMembership.user_id == manager.id,
                TeamMembership.team_id == team_id,
            )
        )
        user = await session.get(User, manager.id)
        assert user is not None
        removed_manager = await actor_from_user_with_memberships(session, user)
        removed_items, _ = await repository.list_actions(
            removed_manager, ActionFilters(), limit=10, cursor=None
        )
        assert removed_items == []
        user.is_active = False
        await session.flush()
        with pytest.raises(ObjectNotFound):
            await repository.list_actions(
                removed_manager, ActionFilters(), limit=10, cursor=None
            )


@pytest.mark.asyncio
async def test_saved_action_views_are_owner_scoped_and_optimistic(
    api_harness: ApiHarness,
) -> None:
    actor = await _actor(api_harness, "admin11")
    other = await _actor(api_harness, "admin12")
    create = SavedActionViewCommand(
        name="Urgent reviews",
        filters=ActionFilters(sections=[ActionSection.NEEDS_MY_ACTION]),
        visible_columns=[ActionColumn.REFERENCE, ActionColumn.REQUIRED_BY],
    )
    async with api_harness.sessions() as session, session.begin():
        created = await create_action_view(create, actor, session)
        assert created.version == 1
        assert created.visible_columns == [
            ActionColumn.REFERENCE,
            ActionColumn.REQUIRED_BY,
        ]
        updated = await update_action_view(
            created.id,
            SavedActionViewUpdate(
                **create.model_dump(), expected_version=created.version
            ),
            actor,
            session,
        )
        assert updated.version == 2
        with pytest.raises(StaleVersion):
            await update_action_view(
                created.id,
                SavedActionViewUpdate(**create.model_dump(), expected_version=1),
                actor,
                session,
            )
        with pytest.raises(ObjectNotFound):
            await delete_action_view(created.id, other, session, 2)
        with pytest.raises(StaleVersion):
            await delete_action_view(created.id, actor, session, 1)

        workspace = await get_actions(
            actor,
            session,
            sections=None,
            action_types=None,
            due_before=None,
            cursor=None,
            limit=50,
        )
        assert workspace.saved_views[0].id == created.id
        response = await delete_action_view(created.id, actor, session, 2)
        assert response.status_code == 204


def test_action_schema_validation_branches() -> None:
    with pytest.raises(ValidationError):
        SavedActionViewCommand(
            name="View",
            filters=ActionFilters(),
            visible_columns=[ActionColumn.REFERENCE, ActionColumn.REFERENCE],
        )
    with pytest.raises(ValidationError):
        ActionFilters(action_types=["review", " REVIEW "])


@pytest.mark.asyncio
async def test_action_projection_validation_precedes_persistence(
    api_harness: ApiHarness,
) -> None:
    actor = await _actor(api_harness, "admin2")
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        service = ActionService(SqlAlchemyActionRepository(session))
        invalid = replace(_command(actor, now), deep_link="//host/x")
        with pytest.raises(InvalidAction):
            await service.project(invalid)
        with pytest.raises(InvalidAction):
            await service.project(
                replace(invalid, deep_link="/requests/x", recipient_user_id=None)
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(invalid, deep_link="/requests/x", source_version=0)
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(invalid, deep_link="/requests/x", action_type="bad type")
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(invalid, deep_link="/requests/x", stable_key=" ")
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(
                    invalid,
                    deep_link="/requests/x",
                    recipient_user_id=None,
                    organisation_unit_id=uuid4(),
                )
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(
                    invalid,
                    deep_link="/requests/x",
                    organisation_unit_id=uuid4(),
                )
            )
        with pytest.raises(InvalidAction):
            await service.project(
                replace(
                    invalid,
                    deep_link="/requests/x",
                    required_scope="Synthetic scope",
                )
            )
