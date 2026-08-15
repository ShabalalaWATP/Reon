"""Synthetic content-free facts for statistics evolution API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness, request_payload
from mist_service.analytics_evolution_models import (
    AnalyticsDefinitionVersion,
    OperationalAnalyticsFact,
    OperationalFactType,
)
from mist_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from mist_service.analytics_projection import PROJECTION_NAME, PROJECTION_VERSION
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.requests import RequestCreate


async def seed_evolution_statistics(harness: ApiHarness) -> None:
    now = datetime.now(UTC)
    requester_id = await harness.user_id("admin2")
    units = {
        code: await harness.unit_id(code)
        for code in (
            "CRIOC",
            "JOCK",
            "ACSA_B_OPS",
            "SSG_TEAM",
            "SYGOC",
            "NIMBUS_OPS",
            "BEACON_TEAM",
        )
    }
    async with harness.sessions() as session, session.begin():
        for index in range(5):
            _request_fact(
                session,
                now=now,
                requester_id=requester_id,
                units=units,
                index=index,
                previous=False,
                small=False,
            )
            _request_fact(
                session,
                now=now,
                requester_id=requester_id,
                units=units,
                index=index,
                previous=True,
                small=False,
            )
        _request_fact(
            session,
            now=now,
            requester_id=requester_id,
            units=units,
            index=90,
            previous=False,
            small=True,
        )
        _request_fact(
            session,
            now=now,
            requester_id=requester_id,
            units=units,
            index=91,
            previous=True,
            small=True,
        )
        session.add(
            AnalyticsProjectionState(
                name=PROJECTION_NAME,
                projection_version=PROJECTION_VERSION,
                health=ProjectionHealth.READY,
                source_event_count=12,
                projected_request_count=12,
                last_projected_at=now,
            )
        )
        _operational_facts(session, now, units, small=False)
        _operational_facts(session, now, units, small=True)
        session.add(
            AnalyticsDefinitionVersion(
                key="notification_response",
                version=1,
                label="Notification response",
                description="Content-free elapsed notification response time.",
                unit="hours",
            )
        )


def _request_fact(
    session: AsyncSession,
    *,
    now: datetime,
    requester_id: UUID,
    units: dict[str, UUID],
    index: int,
    previous: bool,
    small: bool,
) -> None:
    received_at = now - timedelta(days=(14 if previous else 4), hours=index % 4)
    status = RequestStatus.COMPLETED if index % 2 == 0 else RequestStatus.IN_PROGRESS
    request_id = uuid4()
    command = RequestCreate.model_validate(request_payload()).model_dump()
    request = ServiceRequest(
        id=request_id,
        reference=f"SR-EVOL-{index:03d}-{'P' if previous else 'C'}",
        requester_id=requester_id,
        status=status,
        current_owner="Synthetic statistics fixture",
        created_at=received_at,
        **command,
    )
    request.title = f"PROHIBITED CONTENT MARKER {index}"
    command_id = units["SYGOC"] if small else units["JOCK"]
    ops_id = units["NIMBUS_OPS"] if small else units["ACSA_B_OPS"]
    team_id = units["BEACON_TEAM"] if small else units["SSG_TEAM"]
    completed_at = (
        received_at + timedelta(hours=8) if status is RequestStatus.COMPLETED else None
    )
    session.add_all(
        (
            request,
            RequestAnalyticsFact(
                request_id=request_id,
                root_unit_id=units["CRIOC"],
                command_unit_id=command_id,
                ops_unit_id=ops_id,
                team_unit_id=team_id,
                received_at=received_at,
                required_by=now.date() - timedelta(days=1),
                current_status=status,
                last_transition_at=completed_at or received_at,
                completed_at=completed_at,
                released_at=completed_at,
                feedback_received=False,
                projection_version=PROJECTION_VERSION,
                source_event_count=1,
                projected_at=now,
            ),
            RequestStageInterval(
                request_id=request_id,
                sequence=1,
                status=RequestStatus.IN_PROGRESS,
                unit_id=team_id,
                started_at=received_at,
                ended_at=completed_at,
                duration_seconds=8 * 3600 if completed_at else None,
            ),
        )
    )


def _operational_facts(
    session: AsyncSession,
    now: datetime,
    units: dict[str, UUID],
    *,
    small: bool,
) -> None:
    command_id = units["SYGOC"] if small else units["JOCK"]
    ops_id = units["NIMBUS_OPS"] if small else units["ACSA_B_OPS"]
    team_id = units["BEACON_TEAM"] if small else units["SSG_TEAM"]
    cohort = 2 if small else 5
    prefix = "small" if small else "large"
    for index in range(cohort + (0 if small else 1)):
        session.add(
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key=f"{prefix}-notification-{index}",
                fact_type=OperationalFactType.NOTIFICATION_SENT,
                occurred_at=now - timedelta(days=1),
                duration=None if index == cohort else (index + 1) * 1800,
            )
        )
    for index in range(cohort):
        session.add(
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key=f"{prefix}-release-{index}",
                fact_type=OperationalFactType.DISSEMINATION_RELEASED,
                occurred_at=now - timedelta(days=2),
                duration=(index + 1) * 3600,
            )
        )
    if small:
        return
    session.add_all(
        (
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key="large-downloads",
                fact_type=OperationalFactType.DISSEMINATION_DOWNLOADED,
                occurred_at=now - timedelta(days=2),
                count=5,
                duration=3600,
            ),
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key="large-withdrawals",
                fact_type=OperationalFactType.DISSEMINATION_WITHDRAWN,
                occurred_at=now - timedelta(days=2),
                count=2,
            ),
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key="iteration-committed",
                fact_type=OperationalFactType.ITERATION_COMMITTED,
                occurred_at=now,
                count=5,
            ),
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key="iteration-completed",
                fact_type=OperationalFactType.ITERATION_COMPLETED,
                occurred_at=now,
                count=4,
            ),
        )
    )
    for fact_type, minutes in (
        (OperationalFactType.CAPACITY_AVAILABLE, 2250),
        (OperationalFactType.CAPACITY_RESERVED, 300),
        (OperationalFactType.PLANNING_ACTIVE_WORK, 900),
        (OperationalFactType.PLANNING_DEMAND, 1200),
    ):
        session.add(
            _fact(
                units,
                command_id,
                ops_id,
                team_id,
                key=f"capacity-{fact_type}",
                fact_type=fact_type,
                occurred_at=now,
                count=5,
                minutes=minutes,
            )
        )


def _fact(
    units: dict[str, UUID],
    command_id: UUID,
    ops_id: UUID,
    team_id: UUID,
    *,
    key: str,
    fact_type: OperationalFactType,
    occurred_at: datetime,
    count: int = 1,
    duration: int | None = None,
    minutes: int | None = None,
) -> OperationalAnalyticsFact:
    return OperationalAnalyticsFact(
        source_key=key,
        type=fact_type,
        root_unit_id=units["CRIOC"],
        command_unit_id=command_id,
        ops_unit_id=ops_id,
        team_unit_id=team_id,
        occurred_at=occurred_at,
        count_value=count,
        duration_seconds=duration,
        measure_minutes=minutes,
        definition_version=1,
        projection_version=1,
    )
