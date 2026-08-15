"""Canonical personal and authorised shared-team calendar routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from mist_service.calendar_composition import calendar_service
from mist_service.dependencies import (
    DatabaseSession,
    StaffActor,
    StaffMutationActor,
)
from mist_service.schemas.calendar import (
    CalendarEventResult,
    CalendarEventUpdate,
    CalendarOccurrenceList,
    CapacityCommitCommand,
    CapacityPreview,
    CapacityPreviewCommand,
    CapacitySnapshot,
    CommitmentCommand,
    CommitmentDecisionCommand,
    FutureSplitCommand,
    OccurrenceCancelCommand,
    OccurrenceEditCommand,
    PersonalEventCommand,
    TeamEventCommand,
)
from mist_service.services.calendar_service import CalendarService

router = APIRouter(tags=["calendar"])


def _service(session: DatabaseSession) -> CalendarService:
    return calendar_service(session)


@router.get("/calendar/personal", response_model=CalendarOccurrenceList)
async def personal_calendar(
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    actor: StaffActor,
    session: DatabaseSession,
) -> CalendarOccurrenceList:
    return CalendarOccurrenceList(
        items=await _service(session).personal(actor, start, end)
    )


@router.post("/calendar/events", response_model=CalendarEventResult)
async def create_personal_event(
    command: PersonalEventCommand, actor: StaffMutationActor, session: DatabaseSession
) -> CalendarEventResult:
    return await _service(session).create_personal(actor, command)


@router.put("/calendar/events/{event_id}", response_model=CalendarEventResult)
async def update_event(
    event_id: UUID,
    command: CalendarEventUpdate,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).update(actor, event_id, command)


@router.post("/calendar/events/{event_id}/cancel", response_model=CalendarEventResult)
async def cancel_event(
    event_id: UUID,
    command: OccurrenceCancelCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).cancel(actor, event_id, command)


@router.post(
    "/calendar/events/{event_id}/occurrences/cancel", response_model=CalendarEventResult
)
async def cancel_occurrence(
    event_id: UUID,
    command: OccurrenceCancelCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).cancel_occurrence(actor, event_id, command)


@router.post(
    "/calendar/events/{event_id}/occurrences/edit", response_model=CalendarEventResult
)
async def edit_occurrence(
    event_id: UUID,
    command: OccurrenceEditCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).edit_occurrence(actor, event_id, command)


@router.post("/calendar/events/{event_id}/split", response_model=CalendarEventResult)
async def split_series(
    event_id: UUID,
    command: FutureSplitCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).split(actor, event_id, command)


@router.post(
    "/calendar/events/{event_id}/acknowledge", response_model=CalendarEventResult
)
async def acknowledge_commitment(
    event_id: UUID,
    command: CommitmentDecisionCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).decide_commitment(
        actor, event_id, command, acknowledge=True
    )


@router.post("/calendar/events/{event_id}/dispute", response_model=CalendarEventResult)
async def dispute_commitment(
    event_id: UUID,
    command: CommitmentDecisionCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).decide_commitment(
        actor, event_id, command, acknowledge=False
    )


@router.get(
    "/team-workspaces/{team_id}/calendar", response_model=CalendarOccurrenceList
)
async def team_calendar(
    team_id: UUID,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    actor: StaffActor,
    session: DatabaseSession,
) -> CalendarOccurrenceList:
    return CalendarOccurrenceList(
        items=await _service(session).team(actor, team_id, start, end)
    )


@router.post(
    "/team-workspaces/{team_id}/calendar/events", response_model=CalendarEventResult
)
async def create_team_event(
    team_id: UUID,
    command: TeamEventCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).create_team(actor, team_id, command)


@router.post(
    "/team-workspaces/{team_id}/calendar/commitments",
    response_model=CalendarEventResult,
)
async def create_commitment(
    team_id: UUID,
    command: CommitmentCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CalendarEventResult:
    return await _service(session).create_commitment(actor, team_id, command)


@router.post(
    "/team-workspaces/{team_id}/capacity/previews", response_model=CapacityPreview
)
async def preview_capacity(
    team_id: UUID,
    command: CapacityPreviewCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CapacityPreview:
    return await _service(session).preview_capacity(actor, team_id, command)


@router.post(
    "/team-workspaces/{team_id}/capacity/commits", response_model=CapacitySnapshot
)
async def commit_capacity(
    team_id: UUID,
    command: CapacityCommitCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> CapacitySnapshot:
    return await _service(session).commit_capacity(actor, team_id, command)
