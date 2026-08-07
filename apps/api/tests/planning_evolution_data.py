"""Synthetic planning projection fixtures shared by focused API tests."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness, request_payload
from istari_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
)
from istari_service.analytics_projection import PROJECTION_NAME, PROJECTION_VERSION
from istari_service.board_models import (
    CapacityReservation,
    IterationStatus,
    ReservationStatus,
    TeamIteration,
    WorkPackage,
    WorkPackageDependency,
    WorkPackagePriority,
    WorkPackageStatus,
)
from istari_service.calendar_models import (
    CalendarCategory,
    CalendarEvent,
    CalendarEventKind,
    CalendarEventStatus,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.organisation_models import UserOrganisationMembership
from istari_service.planning_analytics_models import (
    PackageBlocker,
    PackageChecklist,
    PackageChecklistItem,
    PackageTemplate,
    PackageTemplateChecklistItem,
)
from istari_service.schemas.requests import RequestCreate


async def seed_planning(harness: ApiHarness) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    today = now.date()
    team_id = await harness.unit_id("OSG_TEAM")
    manager_id = await harness.user_id("admin8")
    owner_id = await harness.user_id("admin11")
    contributor_id = await harness.user_id("admin12")
    root_id = await harness.unit_id("JIOC")
    command_id = await harness.unit_id("DIGOC")
    ops_id = await harness.unit_id("NCGI_A_OPS")
    next_workday = today
    while next_workday.weekday() >= 5:
        next_workday += timedelta(days=1)
    zone = ZoneInfo("Europe/London")
    starts_at = datetime.combine(next_workday, time(hour=9), zone).astimezone(UTC)
    ends_at = starts_at + timedelta(minutes=450)
    async with harness.sessions() as session, session.begin():
        iteration = TeamIteration(
            team_id=team_id,
            name="Synthetic active iteration",
            goal="Complete traceable synthetic planning work.",
            starts_on=today,
            ends_on=today + timedelta(days=14),
            status=IterationStatus.ACTIVE,
            created_by_user_id=manager_id,
            version=1,
        )
        session.add(iteration)
        await session.flush()
        dependency = package(
            team_id,
            manager_id,
            owner_id,
            "Blocked dependency",
            WorkPackageStatus.BLOCKED,
        )
        dependency.due_on = today + timedelta(days=2)
        done = package(
            team_id,
            manager_id,
            owner_id,
            "Completed dependency",
            WorkPackageStatus.DONE,
        )
        primary = package(
            team_id, manager_id, owner_id, "Primary package", WorkPackageStatus.BLOCKED
        )
        primary.iteration_id = iteration.id
        primary.due_on = today + timedelta(days=3)
        fallback = package(
            team_id,
            manager_id,
            contributor_id,
            "Fallback blocker",
            WorkPackageStatus.BLOCKED,
        )
        fallback.updated_at = now - timedelta(days=2)
        session.add_all((dependency, done, primary, fallback))
        await session.flush()
        session.add_all(
            (
                WorkPackageDependency(
                    package_id=primary.id, depends_on_id=dependency.id
                ),
                WorkPackageDependency(package_id=primary.id, depends_on_id=done.id),
                WorkPackageDependency(package_id=fallback.id, depends_on_id=uuid4()),
                PackageBlocker(
                    package_id=primary.id,
                    team_id=team_id,
                    reason="Waiting for a synthetic dependency decision.",
                    opened_at=now - timedelta(days=4),
                    opened_by_user_id=manager_id,
                    version=1,
                ),
            )
        )
        template = PackageTemplate(
            team_id=team_id,
            name="Standard planning package",
            description="Synthetic checklist guidance.",
            version=1,
            created_by_user_id=manager_id,
        )
        session.add(template)
        await session.flush()
        checklist = PackageChecklist(
            package_id=primary.id,
            template_id=template.id,
            template_name=template.name,
            template_version=1,
            version=1,
        )
        session.add_all(
            (
                PackageTemplateChecklistItem(
                    template_id=template.id,
                    position=0,
                    label="Confirm synthetic acceptance criteria",
                    required=True,
                ),
                checklist,
            )
        )
        await session.flush()
        session.add_all(
            (
                PackageChecklistItem(
                    checklist_id=checklist.id,
                    position=0,
                    label="Confirm synthetic acceptance criteria",
                    required=True,
                    completed_at=now,
                    completed_by_user_id=manager_id,
                    version=1,
                ),
                PackageChecklistItem(
                    checklist_id=checklist.id,
                    position=1,
                    label="Record the review outcome",
                    required=False,
                    version=1,
                ),
            )
        )
        _add_request_fact(
            session,
            now,
            team_id,
            manager_id,
            owner_id,
            root_id,
            command_id,
            ops_id,
        )
        session.add(
            CalendarEvent(
                subject_user_id=manager_id,
                team_id=team_id,
                created_by_user_id=manager_id,
                kind=CalendarEventKind.TEAM,
                category=CalendarCategory.TRAINING,
                visibility=CalendarVisibility.PRIVATE,
                title="PRIVATE CALENDAR MARKER",
                notes="PRIVATE NOTES MARKER",
                starts_at=starts_at,
                ends_at=ends_at,
                time_zone="Europe/London",
                all_day=False,
                recurrence=RecurrenceFrequency.NONE,
                recurrence_interval=1,
                status=CalendarEventStatus.ACTIVE,
                commitment_status=CommitmentStatus.NOT_REQUIRED,
                version=1,
            )
        )
        member_ids = list(
            await session.scalars(
                select(UserOrganisationMembership.user_id).where(
                    UserOrganisationMembership.unit_id == team_id
                )
            )
        )
        session.add_all(
            CapacityReservation(
                package_id=primary.id,
                team_id=team_id,
                user_id=user_id,
                starts_at=starts_at,
                ends_at=ends_at,
                minutes=450,
                status=ReservationStatus.ACTIVE,
                reason="Synthetic capacity reservation.",
                created_by_user_id=manager_id,
                version=1,
            )
            for user_id in member_ids
        )
    return team_id, primary.id


def _add_request_fact(
    session: AsyncSession,
    now: datetime,
    team_id: UUID,
    manager_id: UUID,
    owner_id: UUID,
    root_id: UUID,
    command_id: UUID,
    ops_id: UUID,
) -> None:
    request_id = uuid4()
    command = RequestCreate.model_validate(request_payload()).model_dump()
    request = ServiceRequest(
        id=request_id,
        reference="SR-PLAN-001",
        requester_id=manager_id,
        status=RequestStatus.IN_PROGRESS,
        current_owner="Synthetic team",
        assigned_specialist_id=owner_id,
        **command,
    )
    request.title = "Synthetic request planning work"
    session.add_all(
        (
            request,
            RequestAnalyticsFact(
                request_id=request_id,
                root_unit_id=root_id,
                command_unit_id=command_id,
                ops_unit_id=ops_id,
                team_unit_id=team_id,
                received_at=now,
                required_by=now.date() + timedelta(days=2),
                current_status=RequestStatus.IN_PROGRESS,
                last_transition_at=now,
                feedback_received=False,
                projection_version=PROJECTION_VERSION,
                source_event_count=1,
                projected_at=now,
            ),
            AnalyticsProjectionState(
                name=PROJECTION_NAME,
                projection_version=PROJECTION_VERSION,
                health=ProjectionHealth.READY,
                source_event_count=1,
                projected_request_count=1,
                last_projected_at=now,
            ),
        )
    )


def package(
    team_id: UUID,
    creator_id: UUID,
    owner_id: UUID,
    title: str,
    status: WorkPackageStatus,
) -> WorkPackage:
    return WorkPackage(
        team_id=team_id,
        title=title,
        description="Synthetic planning description.",
        owner_user_id=owner_id,
        estimate_points=5,
        remaining_effort_minutes=240,
        due_on=datetime.now(UTC).date() + timedelta(days=10),
        priority=WorkPackagePriority.HIGH,
        status=status,
        blockers="Fallback synthetic blocker reason.",
        acceptance_criteria="Synthetic acceptance criteria.",
        created_by_user_id=creator_id,
        version=1,
    )
