"""Notification repair and maintenance-loop branch coverage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import func, select

from conftest import ApiHarness
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationProjectionStatus,
    NotificationRecipient,
)
from mist_service.models import UserRole
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.request_event_projection import NotificationProjectionReconciler
from mist_service.request_notification_projection import serialise_rule
from mist_service.workflow_maintenance import (
    WorkflowMaintenanceHealth,
    run_workflow_maintenance,
)


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
async def test_notification_reconciler_rolls_back_invalid_audience(
    api_harness: ApiHarness,
) -> None:
    event = await _publish_pending(
        api_harness,
        key="account-security:invalid-audience",
        audience=[
            {
                "userId": "",
                "accessKind": NotificationAccessKind.ACCOUNT.value,
                "requiredRole": UserRole.REQUESTER.value,
                "requiredScope": None,
                "organisationUnitId": None,
            }
        ],
    )

    with pytest.raises(ValueError):
        await NotificationProjectionReconciler(api_harness.sessions).reconcile_once()

    async with api_harness.sessions() as session:
        stored = await session.get(NotificationEvent, event.id)
        assert stored is not None
        assert stored.status is NotificationProjectionStatus.PENDING
        assert stored.attempts == 0


class _MaintenanceStep:
    def __init__(
        self,
        result: bool,
        *,
        stop: asyncio.Event | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.stop = stop
        self.error = error
        self.calls = 0

    async def dispatch_once(self) -> bool:
        return await self._run()

    async def reconcile_once(self) -> bool:
        return await self._run()

    async def _run(self) -> bool:
        self.calls += 1
        if self.stop is not None:
            self.stop.set()
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.asyncio
@pytest.mark.parametrize("notification_worked", [True, False])
async def test_maintenance_runs_optional_notification_reconciler(
    notification_worked: bool,
) -> None:
    stop = asyncio.Event()
    dispatcher = _MaintenanceStep(False)
    workflow_reconciler = _MaintenanceStep(False)
    notification_reconciler = _MaintenanceStep(
        notification_worked,
        stop=stop,
    )

    await run_workflow_maintenance(
        cast(Any, dispatcher),
        cast(Any, workflow_reconciler),
        stop,
        notification_reconciler=cast(Any, notification_reconciler),
    )

    assert dispatcher.calls == 1
    assert workflow_reconciler.calls == 1
    assert notification_reconciler.calls == 1


@pytest.mark.asyncio
async def test_maintenance_supervises_notification_reconciler_failure() -> None:
    stop = asyncio.Event()
    failure = RuntimeError("synthetic reconciliation failure")
    notification_reconciler = _MaintenanceStep(False, stop=stop, error=failure)
    health = WorkflowMaintenanceHealth()

    await run_workflow_maintenance(
        cast(Any, _MaintenanceStep(False)),
        cast(Any, _MaintenanceStep(False)),
        stop,
        notification_reconciler=cast(Any, notification_reconciler),
        health=health,
    )

    assert notification_reconciler.calls == 1
    assert health.consecutive_failures == 1
    assert health.last_failure_at is not None
