"""Branch coverage for action and notification policy boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationProjectionStatus,
)
from istari_service.domain import Actor
from istari_service.errors import InvalidAction, ObjectNotFound, StaleVersion
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
)
from istari_service.repositories.actions import SqlAlchemyActionRepository
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.notifications import (
    SqlAlchemyNotificationRepository,
)
from istari_service.repositories.request_participants import (
    replace_request_participants,
)
from istari_service.request_event_models import RequestEvent
from istari_service.request_notification_projection import (
    _assignee_rule,
    deserialise_rule,
    publish_request_notification,
    recipient_rules,
    recipient_rules_for,
    serialise_rule,
)
from istari_service.schemas.actions import (
    ActionFilters,
    NotificationPreferenceUpdate,
)
from istari_service.services.notification_service import (
    NotificationEventCommand,
    NotificationService,
    _validate_recipient_rule,
)


async def _actor(harness: ApiHarness, username: str) -> Actor:
    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return Actor(user.id, user.username, user.display_name, user.role, user.scope)


async def _submitted_request(harness: ApiHarness) -> UUID:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _request(status: RequestStatus, *, assigned: UUID | None = None) -> ServiceRequest:
    return ServiceRequest(
        id=uuid4(),
        requester_id=uuid4(),
        reference="SR-EDGE",
        title="Synthetic edge case",
        status=status,
        current_owner="Synthetic owner",
        required_by=datetime.now(UTC).date() + timedelta(days=10),
        assigned_specialist_id=assigned,
        awaiting_team_staffing=False,
    )


@pytest.mark.asyncio
async def test_clarification_event_projects_waiting_action(
    api_harness: ApiHarness,
) -> None:
    request_id = await _submitted_request(api_harness)
    specialist_id = await api_harness.user_id("admin11")
    analyst = await _actor(api_harness, "admin11")
    customer = await _actor(api_harness, "admin2")
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        prior = request.status
        request.status = RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        request.assigned_specialist_id = specialist_id
        request.assigned_delivery_team_id = await api_harness.unit_id("SSG_TEAM")
        request.current_owner = "Customer"
        request.version += 1
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=specialist_id,
            contributor_ids=[],
            actor_id=specialist_id,
            reason="Synthetic active participant for clarification projection.",
        )
        await append_request_event(
            session,
            request_id=request.id,
            actor_id=specialist_id,
            event_type="workflow_request_clarification",
            message="Additional information requested.",
            prior_status=prior,
            next_status=request.status,
        )
        items, _ = await SqlAlchemyActionRepository(session).list_actions(
            analyst, ActionFilters(), limit=20, cursor=None
        )
        assert {item.action_type for item in items} == {
            "WAITING_FOR_CLARIFICATION",
        }
        customer_items, _ = await SqlAlchemyActionRepository(session).list_actions(
            customer, ActionFilters(), limit=20, cursor=None
        )
        assert {item.action_type for item in customer_items} == {
            "PROVIDE_CLARIFICATION",
        }


@pytest.mark.asyncio
async def test_notification_policy_and_validation_edges(
    api_harness: ApiHarness,
) -> None:
    request_id = await _submitted_request(api_harness)
    customer = await _actor(api_harness, "admin2")
    specialist_id = await api_harness.user_id("admin11")
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.assigned_specialist_id = specialist_id
        request.assigned_delivery_team_id = await api_harness.unit_id("SSG_TEAM")
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=specialist_id,
            contributor_ids=[],
            actor_id=specialist_id,
            reason="Synthetic current Lead for notification projection.",
        )
        stored_policy_event = NotificationEvent(
            request_id=request.id,
            event_type="PRODUCT_WITHDRAWN",
            audience=[],
        )
        assert (await recipient_rules(session, stored_policy_event))[
            0
        ].user_id == customer.id
        rules = await recipient_rules_for(session, "PRODUCT_WITHDRAWN", request)
        assert rules[0].access_kind is NotificationAccessKind.REQUESTER
        rules = await recipient_rules_for(session, "CLARIFICATION_ANSWERED", request)
        assert rules[0].access_kind is NotificationAccessKind.ASSIGNEE
        request.status = RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        direct = await recipient_rules_for(session, "TASK_ASSIGNED", request)
        assert direct[0].access_kind is NotificationAccessKind.REQUESTER
        request.status = RequestStatus.QUALITY_REVIEW
        scoped = await recipient_rules_for(session, "TASK_ASSIGNED", request)
        assert scoped[0].access_kind is NotificationAccessKind.ROLE_SCOPE
        serialised = serialise_rule(rules[0])
        assert deserialise_rule(serialised) == rules[0]
        with pytest.raises(ValueError):
            _assignee_rule(_request(RequestStatus.IN_PROGRESS))

        missing = NotificationEvent(
            request_id=uuid4(), event_type="TASK_ASSIGNED", audience=[]
        )
        assert await recipient_rules(session, missing) == []
        unknown = RequestEvent(type="unrelated", created_at=now)
        await publish_request_notification(session, unknown, request)

        projection = SqlAlchemyNotificationProjectionRepository(session)
        with pytest.raises(ObjectNotFound):
            await projection.project_event(uuid4(), [], projected_at=now)
        with pytest.raises(ObjectNotFound):
            await projection.mark_projection_failed(
                uuid4(), error_code="FAILED", attempted_at=now
            )

        reads = SqlAlchemyNotificationRepository(session)
        no_projection = NotificationService(reads)
        count = await no_projection.count(customer)
        assert count.unread_count >= 0
        with pytest.raises(RuntimeError):
            await no_projection.publish(
                NotificationEventCommand(
                    "key",
                    "REQUEST_SUBMITTED",
                    NotificationEventGroup.ASSIGNMENT,
                    1,
                    "SR-1",
                    now,
                )
            )
        service = NotificationService(reads, projection)
        with pytest.raises(InvalidAction):
            await service.publish(
                NotificationEventCommand(
                    "",
                    "REQUEST_SUBMITTED",
                    NotificationEventGroup.ASSIGNMENT,
                    0,
                    "SR-1",
                    now,
                )
            )
        with pytest.raises(InvalidAction):
            await service.publish(
                NotificationEventCommand(
                    "key",
                    "REQUEST_SUBMITTED",
                    NotificationEventGroup.ASSIGNMENT,
                    1,
                    "SR-1",
                    now,
                    deep_link="//external",
                )
            )
        event = await service.publish(
            NotificationEventCommand(
                "edge:event",
                "REQUEST_SUBMITTED",
                NotificationEventGroup.ASSIGNMENT,
                1,
                "SR-1",
                now,
            )
        )
        invalid_rules = [
            RecipientRule(
                customer.id,
                NotificationAccessKind.ACCOUNT,
                customer.role,
                organisation_unit_id=uuid4(),
            ),
            RecipientRule(
                customer.id, NotificationAccessKind.REQUESTER, UserRole.QUALITY_RELEASE
            ),
            RecipientRule(
                customer.id, NotificationAccessKind.ROUTE_MEMBER, customer.role
            ),
            RecipientRule(
                customer.id, NotificationAccessKind.ROLE_SCOPE, customer.role
            ),
        ]
        for rule in invalid_rules:
            with pytest.raises(InvalidAction):
                await service.project(event.id, [rule])
        await service.projection_failed(event.id, "SAFE_FAILURE", attempted_at=now)
        await service.project(
            event.id,
            [
                RecipientRule(
                    customer.id,
                    NotificationAccessKind.REQUESTER,
                    UserRole.REQUESTER,
                )
            ],
            projected_at=now,
        )
        stored_event = await session.get(NotificationEvent, event.id)
        assert stored_event is not None
        stored_event.status = NotificationProjectionStatus.FAILED
        await service.project(event.id, [], projected_at=now)

        preference = await reads.update_preference(
            customer.id,
            NotificationEventGroup.ASSIGNMENT,
            NotificationPreferenceUpdate(
                enabled=True, reminder_days=[], expected_version=0
            ),
        )
        updated = await reads.update_preference(
            customer.id,
            NotificationEventGroup.ASSIGNMENT,
            NotificationPreferenceUpdate(
                enabled=False, reminder_days=[], expected_version=preference.version
            ),
        )
        assert not updated.enabled
        with pytest.raises(StaleVersion):
            await reads.update_preference(
                customer.id,
                NotificationEventGroup.ASSIGNMENT,
                NotificationPreferenceUpdate(
                    enabled=True, reminder_days=[], expected_version=1
                ),
            )
        with pytest.raises(StaleVersion):
            await reads.update_preference(
                customer.id,
                NotificationEventGroup.FEEDBACK,
                NotificationPreferenceUpdate(
                    enabled=True, reminder_days=[], expected_version=1
                ),
            )
        wrong_scope = Actor(
            customer.id,
            customer.username,
            customer.display_name,
            customer.role,
            "Different scope",
        )
        with pytest.raises(ObjectNotFound):
            await reads.unread_count(wrong_scope)

    _validate_recipient_rule(
        RecipientRule(customer.id, NotificationAccessKind.ACCOUNT, customer.role)
    )
    _validate_recipient_rule(
        RecipientRule(
            customer.id,
            NotificationAccessKind.ROUTE_MEMBER,
            customer.role,
            organisation_unit_id=uuid4(),
        )
    )
    _validate_recipient_rule(
        RecipientRule(
            customer.id,
            NotificationAccessKind.ROLE_SCOPE,
            customer.role,
            required_scope=customer.scope,
        )
    )
