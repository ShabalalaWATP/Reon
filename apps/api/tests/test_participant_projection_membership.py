"""Live exact-team membership for Analyst action and notification projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness, request_payload
from istari_service.action_notification_models import (
    ActionSection,
    ActionSourceType,
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
)
from istari_service.domain import Actor
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.organisation_models import RequestRouteSelection
from istari_service.repositories.actions import SqlAlchemyActionRepository
from istari_service.repositories.auth import actor_from_user_with_memberships
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.notifications import SqlAlchemyNotificationRepository
from istari_service.repositories.request_participants import (
    replace_request_participants,
)
from istari_service.repositories.route_access import (
    live_selected_route_membership_condition,
)
from istari_service.schemas.actions import ActionFilters
from istari_service.schemas.requests import RequestCreate
from istari_service.team_models import TeamMembership


def test_delivery_membership_predicate_correlates_assigned_team() -> None:
    actor = Actor(
        uuid4(),
        "analyst",
        "Synthetic Analyst",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
    )
    statement = select(
        live_selected_route_membership_condition(
            actor,
            NotificationEvent.request_id,
            datetime.now(UTC),
        )
    ).select_from(NotificationEvent)
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FROM service_requests, notification_events" not in sql
    assert "service_requests.id = request_route_selections.request_id" in sql


async def _actor(session: AsyncSession, user_id: UUID) -> Actor:
    user = await session.get(User, user_id)
    assert user is not None
    return await actor_from_user_with_memberships(session, user)


async def _project_for_participant(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    now: datetime,
) -> None:
    actions = SqlAlchemyActionRepository(session)
    await actions.project_action(
        stable_key=f"participant:{request.id}:{actor.id}",
        source_type=ActionSourceType.WORKFLOW_TASK,
        source_id=f"task-{actor.id}",
        source_version=1,
        request_id=request.id,
        recipient_user_id=actor.id,
        candidate_role=actor.role,
        required_scope=None,
        organisation_unit_id=request.assigned_delivery_team_id,
        section=ActionSection.NEEDS_MY_ACTION,
        action_type="PRODUCE_PRODUCT",
        reference=request.reference,
        safe_title=None,
        current_owner="SSG Team",
        required_by=request.required_by,
        last_changed_at=now,
        completed_at=None,
        deep_link=f"/requests/{request.id}",
        projected_at=now,
    )
    notifications = SqlAlchemyNotificationProjectionRepository(session)
    event = await notifications.publish_event(
        stable_key=f"participant-notification:{request.id}:{actor.id}",
        event_type="TASK_ASSIGNED",
        event_group=NotificationEventGroup.ASSIGNMENT,
        source_version=1,
        request_id=request.id,
        safe_subject="A synthetic production task is ready.",
        deep_link=f"/requests/{request.id}",
        audience=[],
        occurred_at=now,
    )
    projected = await notifications.project_event(
        event.id,
        [
            RecipientRule(
                actor.id,
                NotificationAccessKind.ASSIGNEE,
                actor.role,
            )
        ],
        projected_at=now,
    )
    assert len(projected) == 1


async def _visible_counts(session: AsyncSession, actor: Actor) -> tuple[int, int]:
    actions, _cursor = await SqlAlchemyActionRepository(session).list_actions(
        actor, ActionFilters(), limit=20, cursor=None
    )
    notifications, _cursor = await SqlAlchemyNotificationRepository(
        session
    ).list_notifications(
        actor,
        states=[],
        event_types=[],
        from_date=None,
        to_date=None,
        limit=20,
        cursor=None,
    )
    return len(actions), len(notifications)


async def test_lead_expiry_and_contributor_removal_hide_stored_projections(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    lead_id = await harness.user_id("admin11")
    contributor_id = await harness.user_id("admin12")
    requester_id = await harness.user_id("admin2")
    team_id = await harness.unit_id("SSG_TEAM")
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        request = ServiceRequest(
            reference=f"SR-PARTICIPANT-{uuid4().hex[:8]}",
            requester_id=requester_id,
            status=RequestStatus.IN_PROGRESS,
            current_owner="SSG Team",
            assigned_delivery_team="SSG Team",
            assigned_delivery_team_id=team_id,
            assigned_specialist_id=lead_id,
            **RequestCreate.model_validate(request_payload()).model_dump(),
        )
        session.add(request)
        await session.flush()
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=lead_id,
            contributor_ids=[contributor_id],
            actor_id=lead_id,
            reason="Synthetic active production participants.",
        )
        lead = await _actor(session, lead_id)
        contributor = await _actor(session, contributor_id)
        await _project_for_participant(session, request, lead, now)
        await _project_for_participant(session, request, contributor, now)
        assert await _visible_counts(session, lead) == (1, 1)
        assert await _visible_counts(session, contributor) == (1, 1)

        lead_membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == lead_id,
                TeamMembership.team_id == team_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert lead_membership is not None
        lead_membership.effective_from = now - timedelta(days=2)
        lead_membership.effective_until = now - timedelta(days=1)
        await session.flush()
        assert await _visible_counts(session, lead) == (0, 0)
        assert await _visible_counts(session, contributor) == (1, 1)

        await session.execute(
            delete(TeamMembership).where(
                TeamMembership.user_id == contributor_id,
                TeamMembership.team_id == team_id,
            )
        )
        assert await _visible_counts(session, contributor) == (0, 0)


async def test_route_and_team_lead_membership_revocation_hides_projections(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    requester_id = await harness.user_id("admin2")
    now = datetime.now(UTC)
    scenarios = [
        ("admin4", "CRIOC", 0, RequestStatus.TRIAGE_REVIEW, False),
        ("admin8", "SSG_TEAM", 3, RequestStatus.DELIVERY_PLANNING, True),
    ]
    async with harness.sessions() as session, session.begin():
        for username, unit_code, position, status, delete_membership in scenarios:
            actor_id = await harness.user_id(username)
            unit_id = await harness.unit_id(unit_code)
            actor = await _actor(session, actor_id)
            assert unit_id in actor.organisation_unit_ids
            request = ServiceRequest(
                reference=f"SR-ROUTE-MEMBER-{uuid4().hex[:8]}",
                requester_id=requester_id,
                status=status,
                current_owner=unit_code,
                assigned_delivery_team=unit_code if position == 3 else None,
                assigned_delivery_team_id=unit_id if position == 3 else None,
                **RequestCreate.model_validate(request_payload()).model_dump(),
            )
            session.add(request)
            await session.flush()
            session.add(
                RequestRouteSelection(
                    request_id=request.id,
                    unit_id=unit_id,
                    position=position,
                )
            )
            instance = WorkflowInstance(
                request_id=request.id,
                process_id="service-request-v1",
                process_instance_key=f"process-{uuid4().hex}",
                status=WorkflowInstanceStatus.ACTIVE,
            )
            session.add(instance)
            await session.flush()
            session.add(
                WorkflowTask(
                    request_id=request.id,
                    workflow_instance_id=instance.id,
                    task_key=f"task-{uuid4().hex}",
                    element_id=f"route-{position}",
                    name="Synthetic routing decision",
                    candidate_role=actor.role,
                    expected_status=status,
                    status=WorkflowTaskStatus.CLAIMED,
                    assignee_user_id=actor.id,
                    claimed_at=now,
                )
            )
            await session.flush()
            assert await session.scalar(
                select(
                    live_selected_route_membership_condition(
                        actor,
                        request.id,
                        now,
                    )
                )
            )
            await _project_for_participant(session, request, actor, now)
            assert await _visible_counts(session, actor) == (1, 1)

            membership = await session.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == actor.id,
                    TeamMembership.team_id == unit_id,
                    TeamMembership.effective_until.is_(None),
                )
            )
            assert membership is not None
            if delete_membership:
                await session.delete(membership)
            else:
                membership.effective_from = now - timedelta(days=2)
                membership.effective_until = now - timedelta(days=1)
            await session.flush()
            assert await _visible_counts(session, actor) == (0, 0)
