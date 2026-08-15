"""Focused notification idempotency, policy, state and preference coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from conftest import ApiHarness, request_payload
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationProjectionStatus,
    ProjectionHealth,
)
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound, StaleVersion
from mist_service.models import User, UserRole
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notification_reconciliation import (
    SqlAlchemyNotificationReconciler,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.schemas.actions import (
    NotificationFilterState,
    NotificationPreferenceUpdate,
    NotificationStateAction,
    NotificationStateCommand,
    NotificationStateTarget,
)
from mist_service.services.notification_service import (
    NotificationEventCommand,
    NotificationService,
)


async def _actor(harness: ApiHarness, username: str) -> Actor:
    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return Actor(user.id, user.username, user.display_name, user.role, user.scope)


async def _request_id(harness: ApiHarness) -> UUID:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _command(
    request_id: UUID,
    now: datetime,
    *,
    key: str = "request:submitted:1",
    event_type: str = "REQUEST_SUBMITTED",
    group: NotificationEventGroup = NotificationEventGroup.REQUEST_LIFECYCLE,
) -> NotificationEventCommand:
    return NotificationEventCommand(
        stable_key=key,
        event_type=event_type,
        event_group=group,
        source_version=1,
        reference="SR-0001",
        request_id=request_id,
        deep_link=f"/requests/{request_id}",
        occurred_at=now,
    )


@pytest.mark.asyncio
async def test_notification_replay_state_filters_count_and_freshness(
    api_harness: ApiHarness,
) -> None:
    request_id = await _request_id(api_harness)
    customer = await _actor(api_harness, "admin2")
    now = datetime.now(UTC)
    rule = RecipientRule(
        customer.id,
        NotificationAccessKind.REQUESTER,
        UserRole.REQUESTER,
    )
    async with api_harness.sessions() as session, session.begin():
        reads = SqlAlchemyNotificationRepository(session)
        service = NotificationService(
            reads,
            SqlAlchemyNotificationProjectionRepository(session),
            SqlAlchemyNotificationReconciler(session),
        )
        event = await service.publish(_command(request_id, now))
        replay = await service.publish(_command(request_id, now))
        assert replay.id == event.id
        recipients = await service.project(event.id, [rule, rule], projected_at=now)
        assert len(recipients) == 1
        replayed = await service.project(event.id, [rule], projected_at=now)
        assert [item.id for item in replayed] == [recipients[0].id]
        second = await service.publish(
            _command(request_id, now - timedelta(seconds=1), key="request:submitted:2")
        )
        await service.project(second.id, [rule], projected_at=now)

        listed = await service.list_notifications(
            customer,
            states=[NotificationFilterState.UNREAD],
            event_types=["request_submitted", "REQUEST_SUBMITTED"],
            from_date=now - timedelta(minutes=1),
            to_date=now + timedelta(minutes=1),
            limit=10,
            cursor=None,
            now=now,
        )
        assert listed.unread_count == 2
        assert listed.items[0].subject == "SR-0001: request submitted."
        assert listed.freshness.status is ProjectionHealth.CURRENT
        assert listed.freshness.pending_count == 0
        page = await service.list_notifications(
            customer,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=1,
            cursor=None,
        )
        assert page.next_cursor is not None
        next_page = await service.list_notifications(
            customer,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=1,
            cursor=page.next_cursor,
        )
        assert next_page.items[0].id != page.items[0].id

        target = NotificationStateTarget(id=recipients[0].id, expected_version=1)
        read = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.MARK_READ, targets=[target]
            ),
            changed_at=now,
        )
        assert read.items[0].is_read and read.items[0].version == 2
        unchanged = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.MARK_READ,
                targets=[NotificationStateTarget(id=target.id, expected_version=2)],
            ),
            changed_at=now,
        )
        assert unchanged.items[0].version == 2
        unread = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.MARK_UNREAD,
                targets=[NotificationStateTarget(id=target.id, expected_version=2)],
            ),
            changed_at=now,
        )
        assert not unread.items[0].is_read and unread.items[0].version == 3
        archived = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.ARCHIVE,
                targets=[NotificationStateTarget(id=target.id, expected_version=3)],
            ),
            changed_at=now,
        )
        assert archived.items[0].is_archived and archived.items[0].is_read
        restored = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.RESTORE,
                targets=[NotificationStateTarget(id=target.id, expected_version=4)],
            ),
            changed_at=now,
        )
        assert not restored.items[0].is_archived
        completed = await service.mutate_state(
            customer,
            NotificationStateCommand(
                action=NotificationStateAction.COMPLETE_ACTION,
                targets=[NotificationStateTarget(id=target.id, expected_version=5)],
            ),
            changed_at=now,
        )
        assert completed.items[0].is_action_completed
        with pytest.raises(StaleVersion):
            await service.mutate_state(
                customer,
                NotificationStateCommand(
                    action=NotificationStateAction.MARK_READ, targets=[target]
                ),
            )


@pytest.mark.asyncio
async def test_preferences_suppression_mandatory_groups_and_failed_repair(
    api_harness: ApiHarness,
) -> None:
    request_id = await _request_id(api_harness)
    customer = await _actor(api_harness, "admin2")
    disabled = await _actor(api_harness, "admin16")
    now = datetime.now(UTC)
    rule = RecipientRule(
        customer.id,
        NotificationAccessKind.REQUESTER,
        UserRole.REQUESTER,
    )
    async with api_harness.sessions() as session, session.begin():
        reads = SqlAlchemyNotificationRepository(session)
        service = NotificationService(
            reads, SqlAlchemyNotificationProjectionRepository(session)
        )
        assignment = await service.update_preference(
            customer,
            NotificationEventGroup.ASSIGNMENT,
            NotificationPreferenceUpdate(
                enabled=False, reminder_days=[14, 7, 1], expected_version=0
            ),
        )
        assert not assignment.enabled and assignment.version == 1
        event = await service.publish(
            _command(
                request_id,
                now,
                key="task:assigned:1",
                event_type="TASK_ASSIGNED",
                group=NotificationEventGroup.ASSIGNMENT,
            )
        )
        assert await service.project(event.id, [rule], projected_at=now) == []

        mandatory = await service.update_preference(
            customer,
            NotificationEventGroup.RELEASE,
            NotificationPreferenceUpdate(
                enabled=False, reminder_days=[], expected_version=0
            ),
        )
        assert mandatory.enabled and mandatory.mandatory
        release = await service.publish(
            _command(
                request_id,
                now,
                key="product:released:1",
                event_type="PRODUCT_DISSEMINATED",
                group=NotificationEventGroup.RELEASE,
            )
        )
        skipped_rule = RecipientRule(
            disabled.id,
            NotificationAccessKind.REQUESTER,
            UserRole.REQUESTER,
        )
        created = await service.project(
            release.id, [rule, skipped_rule], projected_at=now
        )
        assert len(created) == 1

        failed = await service.publish(
            _command(request_id, now, key="request:withdrawn:failure")
        )
        await service.projection_failed(
            failed.id, "unsafe error: details", attempted_at=now
        )
        stored = await session.get(NotificationEvent, failed.id)
        assert stored is not None
        assert stored.status is NotificationProjectionStatus.FAILED
        assert stored.last_error == "PROJECTION_FAILED"
        checkpoint = await reads.checkpoint()
        assert checkpoint is not None and checkpoint.health is ProjectionHealth.DEGRADED
        repaired = await service.project(failed.id, [rule], projected_at=now)
        assert len(repaired) == 1
        assert (await reads.checkpoint()).health is ProjectionHealth.CURRENT  # type: ignore[union-attr]

        preferences = await service.preferences(customer)
        assert len(preferences.groups) == len(NotificationEventGroup)
        assert next(
            group
            for group in preferences.groups
            if group.event_group is NotificationEventGroup.RELEASE
        ).mandatory


@pytest.mark.asyncio
async def test_request_and_account_access_are_rechecked_without_disclosure(
    api_harness: ApiHarness,
) -> None:
    request_id = await _request_id(api_harness)
    customer = await _actor(api_harness, "admin2")
    unrelated = await _actor(api_harness, "admin3")
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        service = NotificationService(
            SqlAlchemyNotificationRepository(session),
            SqlAlchemyNotificationProjectionRepository(session),
        )
        event = await service.publish(_command(request_id, now))
        created = await service.project(
            event.id,
            [
                RecipientRule(
                    unrelated.id,
                    NotificationAccessKind.REQUESTER,
                    UserRole.REQUESTER,
                )
            ],
            projected_at=now,
        )
        hidden = await service.list_notifications(
            unrelated,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=10,
            cursor=None,
        )
        assert hidden.items == []
        with pytest.raises(ObjectNotFound):
            await service.mutate_state(
                customer,
                NotificationStateCommand(
                    action=NotificationStateAction.MARK_READ,
                    targets=[
                        NotificationStateTarget(
                            id=created[0].id,
                            expected_version=1,
                        )
                    ],
                ),
            )
