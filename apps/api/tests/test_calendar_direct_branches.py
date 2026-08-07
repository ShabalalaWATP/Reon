"""Direct calendar adapter tests for every persistence decision branch."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from istari_service.calendar_capacity import (
    CalendarCapacityService,
    _digest,
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
from istari_service.domain import Actor
from istari_service.errors import (
    CalendarItemNotFound,
    InvalidCalendarChange,
    InvalidRosterChange,
    StaleVersion,
)
from istari_service.management_models import ManagementAction
from istari_service.models import UserRole
from istari_service.repositories.calendar import SqlAlchemyCalendarRepository
from istari_service.roster_disposition import reject_active_roster_assignments
from istari_service.schemas.calendar import (
    CommitmentDecisionCommand,
    OccurrenceCancelCommand,
)
from istari_service.schemas.team_workspaces import TeamWorkspaceAccess
from istari_service.services.calendar_service import CalendarService


def calendar_event(
    user_id: UUID,
    *,
    start: datetime = datetime(2026, 8, 10, 9, tzinfo=UTC),
    kind: CalendarEventKind = CalendarEventKind.PERSONAL,
) -> CalendarEvent:
    event = CalendarEvent(
        subject_user_id=user_id,
        team_id=None,
        created_by_user_id=user_id,
        kind=kind,
        category=CalendarCategory.TRAINING,
        visibility=CalendarVisibility.PRIVATE,
        title="Synthetic protected block",
        notes="Required synthetic detail.",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        time_zone="Europe/London",
        all_day=False,
        recurrence=RecurrenceFrequency.NONE,
        recurrence_interval=1,
        recurrence_until=None,
        status=CalendarEventStatus.ACTIVE,
        commitment_status=CommitmentStatus.NOT_REQUIRED,
        version=1,
    )
    event.id = uuid4()
    return event


async def test_capacity_preview_commit_and_all_rejection_branches() -> None:
    actor_id, team_id = uuid4(), uuid4()
    added: list[object] = []
    session = MagicMock()

    def add(item: object) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid4()  # type: ignore[attr-defined]
        added.append(item)

    session.add.side_effect = add
    session.flush = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock(return_value=[])
    calendar = MagicMock()
    calendar.list_team = AsyncMock(return_value=[])
    calendar.current_team_members = AsyncMock(return_value={actor_id})
    service = CalendarCapacityService(session, calendar)

    preview_result = await service.preview(
        actor_id=actor_id,
        team_id=team_id,
        date_from=date(2026, 8, 10),
        date_to=date(2026, 8, 10),
        time_zone="Europe/London",
    )
    assert preview_result.days[0].available_minutes == 450
    preview = added[0]

    session.scalar.return_value = None
    with pytest.raises(InvalidCalendarChange, match="unavailable"):
        await service.commit(actor_id=actor_id, team_id=team_id, token="x" * 32)

    preview.consumed_at = None  # type: ignore[attr-defined]
    preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)  # type: ignore[attr-defined]
    session.scalar.return_value = preview
    with pytest.raises(InvalidCalendarChange, match="expired"):
        await service.commit(actor_id=actor_id, team_id=team_id, token="x" * 32)

    preview.expires_at = datetime.now(UTC) + timedelta(minutes=5)  # type: ignore[attr-defined]
    preview.source_digest = "stale"  # type: ignore[attr-defined]
    with pytest.raises(StaleVersion, match="availability changed"):
        await service.commit(actor_id=actor_id, team_id=team_id, token="x" * 32)

    preview.source_digest = _digest([], 1)  # type: ignore[attr-defined]
    committed = await service.commit(actor_id=actor_id, team_id=team_id, token="x" * 32)
    assert committed.snapshot_id == added[-1].id  # type: ignore[attr-defined]


async def test_repository_locking_expansion_and_exception_identity_branches() -> None:
    user_id = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.execute = AsyncMock()
    repository = SqlAlchemyCalendarRepository(session)

    session.scalar.return_value = None
    with pytest.raises(CalendarItemNotFound):
        await repository.locked_event(uuid4(), 1)
    event = calendar_event(user_id)
    session.scalar.return_value = event
    with pytest.raises(StaleVersion):
        await repository.locked_event(event.id, 2)
    event.status = CalendarEventStatus.CANCELLED
    with pytest.raises(InvalidCalendarChange, match="cancelled"):
        await repository.locked_event(event.id, 1)
    event.status = CalendarEventStatus.ACTIVE
    assert await repository.locked_event(event.id, 1) is event

    repository._exceptions = AsyncMock(return_value={event.id: []})  # type: ignore[method-assign]
    repository._names = AsyncMock(return_value={user_id: "Synthetic Analyst"})  # type: ignore[method-assign]
    visible = await repository._expand(
        [event],
        event.starts_at - timedelta(minutes=1),
        event.ends_at + timedelta(minutes=1),
        viewer_id=user_id,
    )
    assert visible[0].title == event.title
    empty = await repository._expand(
        [event],
        event.starts_at - timedelta(days=2),
        event.starts_at - timedelta(days=1),
        viewer_id=user_id,
    )
    assert empty == []

    repository = SqlAlchemyCalendarRepository(session)
    session.scalars.return_value = [
        SimpleNamespace(event_id=event.id),
        SimpleNamespace(event_id=event.id),
    ]
    grouped = await repository._exceptions([event])
    assert len(grouped[event.id]) == 2
    assert await repository._exceptions([]) == {}

    session.scalar.return_value = None
    await repository._require_new_exception(event.id, event.starts_at)
    session.scalar.return_value = uuid4()
    with pytest.raises(InvalidCalendarChange, match="already has"):
        await repository._require_new_exception(event.id, event.starts_at)


async def test_commitment_decision_and_team_change_authority_branches() -> None:
    actor = Actor(
        id=uuid4(),
        username="admin-test",
        display_name="Synthetic Analyst",
        role=UserRole.DELIVERY_SPECIALIST,
        scope="OSG Team",
    )
    event = calendar_event(actor.id, kind=CalendarEventKind.COMMITMENT)
    event.commitment_status = CommitmentStatus.PENDING
    calendar = MagicMock()
    calendar.session = MagicMock()
    calendar.locked_event = AsyncMock(return_value=event)
    calendar.set_commitment = AsyncMock(return_value=event)
    workspaces = MagicMock()
    service = CalendarService(calendar, workspaces)

    acknowledged = await service.decide_commitment(
        actor,
        event.id,
        CommitmentDecisionCommand(expectedVersion=1, reason=None),
        acknowledge=True,
    )
    assert acknowledged.event_id == event.id
    event.commitment_status = CommitmentStatus.PENDING
    await service.decide_commitment(
        actor,
        event.id,
        CommitmentDecisionCommand(
            expectedVersion=1, reason="Required synthetic dispute reason."
        ),
        acknowledge=False,
    )

    team_id, grant_id = uuid4(), uuid4()
    event.kind = CalendarEventKind.TEAM
    event.team_id = team_id
    event.subject_user_id = uuid4()
    workspaces.require_read = AsyncMock(
        return_value=TeamWorkspaceAccess(
            teamId=team_id,
            teamCode="OSG_TEAM",
            teamName="OSG Team",
            grantId=None,
            permissions=[],
        )
    )
    with pytest.raises(CalendarItemNotFound):
        await service._authorise_event_change(actor, event)

    workspaces.require_read.return_value = TeamWorkspaceAccess(
        teamId=team_id,
        teamCode="OSG_TEAM",
        teamName="OSG Team",
        grantId=grant_id,
        permissions=[ManagementAction.CALENDAR],
    )
    service._authorise = AsyncMock()  # type: ignore[method-assign]
    await service._authorise_event_change(actor, event)
    service._authorise.assert_awaited_once_with(  # type: ignore[attr-defined]
        actor, team_id, grant_id, ManagementAction.CALENDAR
    )


async def test_repository_cancel_command_strips_reason() -> None:
    user_id = uuid4()
    event = calendar_event(user_id)
    repository = SqlAlchemyCalendarRepository(MagicMock())
    command = OccurrenceCancelCommand(
        expectedVersion=1,
        occurrenceStart=event.starts_at,
        reason="  Required synthetic cancellation reason.  ",
    )
    result = await repository.cancel_event(event, command.reason)
    assert result.commitment_reason == "Required synthetic cancellation reason."


async def test_roster_disposition_checks_work_then_commitments() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=uuid4())
    with pytest.raises(InvalidRosterChange, match="service work"):
        await reject_active_roster_assignments(
            session, uuid4(), datetime.now(UTC) + timedelta(days=1)
        )

    session.scalar.side_effect = [None, uuid4()]
    with pytest.raises(InvalidRosterChange, match="commitments"):
        await reject_active_roster_assignments(
            session, uuid4(), datetime.now(UTC) + timedelta(days=1)
        )

    session.scalar.side_effect = [None, None, None, None]
    await reject_active_roster_assignments(
        session, uuid4(), datetime.now(UTC) + timedelta(days=1)
    )
