"""Content-free operational snapshot and alert-threshold tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from mist_service.analytics_models import AnalyticsProjectionState, ProjectionHealth
from mist_service.models import (
    OutboxStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from mist_service.operational_snapshot import capture_operational_snapshot
from mist_service.operations_models import OperationalRun


async def test_healthy_snapshot_contains_only_bounded_operational_metrics(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        session.add(
            AnalyticsProjectionState(
                name="request-analytics-v1",
                projection_version=1,
                health=ProjectionHealth.READY,
                source_event_count=0,
                projected_request_count=0,
                last_projected_at=now,
            )
        )
        session.add(
            OperationalRun(
                job_name="retention",
                policy_version="v1",
                mode="APPLIED",
                criteria={},
                result_counts={},
                created_at=now - timedelta(hours=2),
            )
        )

    async with harness.sessions() as session:
        report = await capture_operational_snapshot(session, now=now)
    assert report.status == "ok"
    assert report.alerts == ()
    assert report.command_backlog == report.failed_commands == 0
    assert report.projection_health == "READY"
    assert report.projection_age_seconds == 0
    assert report.retention_age_seconds == 7_200


async def test_snapshot_warns_for_failed_old_commands_and_degraded_projection(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    now = datetime.now(UTC)
    await harness.login("admin2")
    assert (
        await harness.client.post(
            "/api/v1/requests",
            json=request_payload(),
            headers=harness.mutation_headers(),
        )
    ).status_code == 201
    async with harness.sessions() as session, session.begin():
        command = await session.scalar(select(WorkflowOutbox))
        instance = await session.scalar(select(WorkflowInstance))
        projection = await session.scalar(select(AnalyticsProjectionState))
        assert command is not None and instance is not None and projection is not None
        command.status = OutboxStatus.FAILED
        command.available_at = now - timedelta(minutes=10)
        instance.status = WorkflowInstanceStatus.ERROR
        projection.health = ProjectionHealth.DEGRADED
        projection.last_projected_at = now - timedelta(minutes=20)

    async with harness.sessions() as session:
        report = await capture_operational_snapshot(
            session,
            now=now,
            max_command_age_seconds=300,
            max_projection_age_seconds=600,
        )
    assert report.status == "warning"
    assert report.command_backlog == report.failed_commands == 1
    assert report.oldest_command_age_seconds == 600
    assert report.workflow_instance_errors == 1
    assert set(report.alerts) == {
        "failed_workflow_commands",
        "workflow_command_backlog_old",
        "analytics_projection_not_ready",
        "workflow_projection_errors",
    }
    assert report.retention_age_seconds is None


async def test_missing_projection_is_reported_without_invented_freshness(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session:
        report = await capture_operational_snapshot(session)
    assert report.projection_health == "MISSING"
    assert report.projection_age_seconds is None
    assert report.alerts == ("analytics_projection_not_ready",)
