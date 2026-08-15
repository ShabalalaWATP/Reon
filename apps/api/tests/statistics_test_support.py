"""Shared content-free statistics fixtures for API contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from conftest import ApiHarness, request_payload
from mist_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from mist_service.analytics_projection import PROJECTION_NAME, PROJECTION_VERSION
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.requests import RequestCreate


async def seed_statistics(harness: ApiHarness) -> None:
    now = datetime.now(UTC)
    requester_id = await harness.user_id("admin2")
    unit_codes = (
        "CRIOC",
        "JOCK",
        "ACSA_B_OPS",
        "SSG_TEAM",
        "AURORA_OPS",
        "LANTERN_TEAM",
        "SYGOC",
        "NIMBUS_OPS",
        "BEACON_TEAM",
        "MYGOC",
        "MERIDIAN_OPS",
        "FLINT_TEAM",
    )
    unit_ids = {code: await harness.unit_id(code) for code in unit_codes}
    rows = [
        (
            "JOCK",
            "ACSA_B_OPS",
            "SSG_TEAM",
            RequestStatus.COMPLETED,
            rating,
            8 - rating,
            10,
        )
        for rating in range(1, 6)
    ]
    rows.extend(
        (
            ("JOCK", "ACSA_B_OPS", "SSG_TEAM", RequestStatus.IN_PROGRESS, None, 1, -1),
            (
                "JOCK",
                "AURORA_OPS",
                "LANTERN_TEAM",
                RequestStatus.IN_PROGRESS,
                None,
                2,
                3,
            ),
            ("SYGOC", "NIMBUS_OPS", "BEACON_TEAM", RequestStatus.COMPLETED, 5, 3, 8),
            (
                "SYGOC",
                "NIMBUS_OPS",
                "BEACON_TEAM",
                RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
                None,
                0,
                6,
            ),
            (
                "MYGOC",
                "MERIDIAN_OPS",
                "FLINT_TEAM",
                RequestStatus.CLOSED_NOT_PROGRESSED,
                None,
                4,
                12,
            ),
        )
    )
    async with harness.sessions() as session, session.begin():
        for index, (command, ops, team, status, rating, age, due_offset) in enumerate(
            rows
        ):
            request_id = uuid4()
            received_at = now - timedelta(days=age)
            command_data = RequestCreate.model_validate(request_payload()).model_dump()
            request = ServiceRequest(
                id=request_id,
                reference=f"SR-STATS-{index:03d}",
                requester_id=requester_id,
                status=status,
                current_owner="Synthetic statistics fixture",
                created_at=received_at,
                **command_data,
            )
            request.title = f"Content marker {index} must not enter statistics"
            request.required_by = now.date() + timedelta(days=due_offset)
            completed_at = (
                received_at + timedelta(hours=8)
                if status is RequestStatus.COMPLETED
                else None
            )
            session.add(request)
            session.add(
                RequestAnalyticsFact(
                    request_id=request_id,
                    root_unit_id=unit_ids["CRIOC"],
                    command_unit_id=unit_ids[command],
                    ops_unit_id=unit_ids[ops],
                    team_unit_id=unit_ids[team],
                    received_at=received_at,
                    required_by=request.required_by,
                    current_status=status,
                    last_transition_at=completed_at or received_at,
                    completed_at=completed_at,
                    closed_at=(
                        received_at + timedelta(hours=2)
                        if status is RequestStatus.CLOSED_NOT_PROGRESSED
                        else None
                    ),
                    released_at=completed_at,
                    clarification_count=2 if index == 5 else 0,
                    clarification_response_seconds=7200 if index == 5 else 0,
                    rework_count=1 if index == 5 else 0,
                    feedback_received=rating is not None,
                    feedback_rating=rating,
                    projection_version=PROJECTION_VERSION,
                    source_event_count=1,
                    projected_at=now,
                )
            )
            session.add(
                RequestStageInterval(
                    request_id=request_id,
                    sequence=1,
                    status=RequestStatus.IN_PROGRESS,
                    unit_id=unit_ids[team],
                    started_at=received_at,
                    ended_at=received_at + timedelta(hours=index + 1),
                    duration_seconds=(index + 1) * 3600,
                    source_event_id=None,
                )
            )
        session.add(
            AnalyticsProjectionState(
                name=PROJECTION_NAME,
                projection_version=PROJECTION_VERSION,
                health=ProjectionHealth.READY,
                source_event_count=len(rows),
                projected_request_count=len(rows),
                last_projected_at=now,
            )
        )
