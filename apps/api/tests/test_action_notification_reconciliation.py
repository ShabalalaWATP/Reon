"""Notification repair branch coverage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

import mist_service.request_event_projection as projection_module
from conftest import ApiHarness
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationProjectionStatus,
    NotificationRecipient,
)
from mist_service.maintenance_models import MaintenanceJobState
from mist_service.models import UserRole
from mist_service.repositories.maintenance_leases import HEARTBEAT_JOB
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.request_action_projection import as_utc
from mist_service.request_event_projection import (
    NotificationProjectionBatchFailed,
    NotificationProjectionReconciler,
)
from mist_service.request_notification_projection import serialise_rule
from mist_service.worker_runtime import MaintenanceJob, WorkerIteration


async def _publish_pending(
    harness: ApiHarness,
    *,
    key: str,
    audience: list[dict[str, str | None]],
) -> NotificationEvent:
    occurred_at = datetime.now(UTC) - timedelta(seconds=1)
    async with harness.sessions() as session, session.begin():
        return await SqlAlchemyNotificationProjectionRepository(session).publish_event(
            stable_key=key,
            event_type="ACCOUNT_SECURITY_CHANGED",
            event_group=NotificationEventGroup.ACCOUNT_SECURITY,
            source_version=1,
            request_id=None,
            safe_subject="Synthetic account: account security changed.",
            deep_link="/account",
            audience=audience,
            occurred_at=occurred_at,
        )


@pytest.mark.asyncio
async def test_notification_reconciler_projects_one_bounded_batch(
    api_harness: ApiHarness,
) -> None:
    user_id = await api_harness.user_id("admin2")
    rule = RecipientRule(
        user_id,
        NotificationAccessKind.ACCOUNT,
        UserRole.REQUESTER,
    )
    first = await _publish_pending(
        api_harness,
        key="account-security:first",
        audience=[serialise_rule(rule)],
    )
    second = await _publish_pending(
        api_harness,
        key="account-security:second",
        audience=[serialise_rule(rule)],
    )
    async with api_harness.sessions() as session, session.begin():
        session.add(
            NotificationRecipient(
                notification_event_id=first.id,
                recipient_user_id=user_id,
                idempotency_key=f"account-security:first:{user_id}",
                access_kind=rule.access_kind,
                required_role=rule.required_role,
                version=1,
            )
        )
    reconciler = NotificationProjectionReconciler(
        api_harness.sessions,
        batch_size=1,
    )

    assert await reconciler.reconcile_once()
    async with api_harness.sessions() as session:
        statuses = list(
            await session.scalars(
                select(NotificationEvent.status)
                .where(NotificationEvent.id.in_([first.id, second.id]))
                .order_by(NotificationEvent.stable_key)
            )
        )
        recipient_count = await session.scalar(
            select(func.count(NotificationRecipient.id))
        )
    assert statuses == [
        NotificationProjectionStatus.PROJECTED,
        NotificationProjectionStatus.PENDING,
    ]
    assert recipient_count == 1

    assert await reconciler.reconcile_once()
    assert not await reconciler.reconcile_once()


@pytest.mark.asyncio
async def test_notification_reconciler_persists_failure_and_continues_batch(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await api_harness.user_id("admin2")
    rule = RecipientRule(
        user_id,
        NotificationAccessKind.ACCOUNT,
        UserRole.REQUESTER,
    )
    failed = await _publish_pending(
        api_harness,
        key="account-security:projection-failure",
        audience=[serialise_rule(rule)],
    )
    progressed = await _publish_pending(
        api_harness,
        key="account-security:progress-after-failure",
        audience=[serialise_rule(rule)],
    )
    original_project = SqlAlchemyNotificationProjectionRepository.project_event
    failed_once = False

    async def project_then_fail_once(
        projection: SqlAlchemyNotificationProjectionRepository,
        event_id: UUID,
        recipients: list[RecipientRule],
        *,
        projected_at: datetime,
        update_checkpoint: bool = True,
    ) -> list[NotificationRecipient]:
        nonlocal failed_once
        projected = await original_project(
            projection,
            event_id,
            recipients,
            projected_at=projected_at,
            update_checkpoint=update_checkpoint,
        )
        if event_id == failed.id and not failed_once:
            failed_once = True
            raise RuntimeError("synthetic sensitive failure details")
        return projected

    monkeypatch.setattr(
        SqlAlchemyNotificationProjectionRepository,
        "project_event",
        project_then_fail_once,
    )

    attempt_started = datetime.now(UTC)
    failure_observed = attempt_started + timedelta(seconds=10)
    clock_values = [attempt_started, failure_observed, failure_observed]

    def slow_failure_clock() -> datetime:
        if clock_values:
            return clock_values.pop(0)
        return datetime.now(UTC)

    monkeypatch.setattr(projection_module, "_utc_now", slow_failure_clock)
    reconciler = NotificationProjectionReconciler(
        api_harness.sessions,
        batch_size=2,
    )
    iteration = WorkerIteration(
        api_harness.sessions,
        (MaintenanceJob("notification-projection", reconciler.reconcile_once),),
        lease_seconds=5,
        owner="notification-test-worker",
    )
    assert not await iteration.run_once()

    async with api_harness.sessions() as session:
        stored_failed = await session.get(NotificationEvent, failed.id)
        stored_progressed = await session.get(NotificationEvent, progressed.id)
        assert stored_failed is not None
        assert stored_progressed is not None
        assert stored_failed.status is NotificationProjectionStatus.FAILED
        assert stored_failed.attempts == 1
        assert stored_failed.last_error == "RUNTIMEERROR"
        assert as_utc(stored_failed.available_at) > failure_observed
        assert stored_progressed.status is NotificationProjectionStatus.PROJECTED
        failed_recipient_count = await session.scalar(
            select(func.count(NotificationRecipient.id)).where(
                NotificationRecipient.notification_event_id == failed.id
            )
        )
        assert failed_recipient_count == 0
        job = await session.get(MaintenanceJobState, "notification-projection")
        heartbeat = await session.get(MaintenanceJobState, HEARTBEAT_JOB)
        expected_error = NotificationProjectionBatchFailed.__name__
        assert job is not None and job.last_error_code == expected_error
        assert heartbeat is not None and heartbeat.last_error_code == expected_error

    async with api_harness.sessions() as session, session.begin():
        stored_failed = await session.get(NotificationEvent, failed.id)
        assert stored_failed is not None
        stored_failed.available_at = datetime.now(UTC) - timedelta(seconds=1)

    assert await NotificationProjectionReconciler(
        api_harness.sessions,
        batch_size=1,
    ).reconcile_once()
    async with api_harness.sessions() as session:
        repaired = await session.get(NotificationEvent, failed.id)
        assert repaired is not None
        assert repaired.status is NotificationProjectionStatus.PROJECTED
        assert repaired.attempts == 2
        assert repaired.last_error is None

    async with api_harness.sessions() as session, session.begin():
        await SqlAlchemyNotificationProjectionRepository(
            session
        ).mark_projection_failed(
            failed.id,
            error_code="LATE_FAILURE",
            attempted_at=datetime.now(UTC),
        )
    async with api_harness.sessions() as session:
        still_projected = await session.get(NotificationEvent, failed.id)
        assert still_projected is not None
        assert still_projected.status is NotificationProjectionStatus.PROJECTED
        assert still_projected.attempts == 2
        assert still_projected.last_error is None


@pytest.mark.asyncio
async def test_notification_reconciler_propagates_cancellation_without_failure(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = await _publish_pending(
        api_harness,
        key="account-security:cancelled-projection",
        audience=[],
    )

    async def cancel_projection(
        _projection: SqlAlchemyNotificationProjectionRepository,
        _event_id: UUID,
        _recipients: list[RecipientRule],
        *,
        projected_at: datetime,
        update_checkpoint: bool = True,
    ) -> list[NotificationRecipient]:
        del projected_at, update_checkpoint
        raise asyncio.CancelledError

    monkeypatch.setattr(
        SqlAlchemyNotificationProjectionRepository,
        "project_event",
        cancel_projection,
    )

    with pytest.raises(asyncio.CancelledError):
        await NotificationProjectionReconciler(api_harness.sessions).reconcile_once()

    async with api_harness.sessions() as session:
        stored = await session.get(NotificationEvent, event.id)
        assert stored is not None
        assert stored.status is NotificationProjectionStatus.PENDING
        assert stored.attempts == 0
        assert stored.last_error is None
