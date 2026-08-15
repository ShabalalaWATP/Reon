"""Final-boundary checks for work that must be disposed before roster moves."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.board_models import (
    CapacityReservation,
    ReservationStatus,
    WorkPackage,
    WorkPackageStatus,
)
from mist_service.calendar_models import (
    CalendarEvent,
    CalendarEventKind,
    CalendarEventStatus,
    CommitmentStatus,
)
from mist_service.errors import InvalidRosterChange
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.request_participant_models import RequestParticipant

TERMINAL_REQUEST_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


async def reject_active_roster_assignments(
    session: AsyncSession, user_id: UUID, effective_at: datetime
) -> None:
    request_id = await session.scalar(
        select(ServiceRequest.id).where(
            ServiceRequest.assigned_specialist_id == user_id,
            ServiceRequest.status.not_in(TERMINAL_REQUEST_STATUSES),
        )
    )
    if request_id is not None:
        raise InvalidRosterChange(
            "Complete or reassign this Analyst's active service work first."
        )
    participant_request_id = await session.scalar(
        select(RequestParticipant.request_id)
        .join(ServiceRequest, ServiceRequest.id == RequestParticipant.request_id)
        .where(
            RequestParticipant.user_id == user_id,
            RequestParticipant.ended_at.is_(None),
            ServiceRequest.status.not_in(TERMINAL_REQUEST_STATUSES),
        )
    )
    if participant_request_id is not None:
        raise InvalidRosterChange(
            "Hand over this Member's active service participation first."
        )
    commitment_id = await session.scalar(
        select(CalendarEvent.id).where(
            CalendarEvent.subject_user_id == user_id,
            CalendarEvent.kind == CalendarEventKind.COMMITMENT,
            CalendarEvent.status == CalendarEventStatus.ACTIVE,
            CalendarEvent.commitment_status.in_(
                {CommitmentStatus.PENDING, CommitmentStatus.ACKNOWLEDGED}
            ),
            CalendarEvent.ends_at > effective_at,
        )
    )
    if commitment_id is not None:
        raise InvalidRosterChange(
            "Cancel, complete or dispute this Analyst's calendar commitments first."
        )
    package_id = await session.scalar(
        select(WorkPackage.id).where(
            WorkPackage.owner_user_id == user_id,
            WorkPackage.status.not_in(
                {WorkPackageStatus.DONE, WorkPackageStatus.CANCELLED}
            ),
        )
    )
    if package_id is not None:
        raise InvalidRosterChange(
            "Complete, cancel or reassign this Analyst's work packages first."
        )
    reservation_id = await session.scalar(
        select(CapacityReservation.id).where(
            CapacityReservation.user_id == user_id,
            CapacityReservation.status == ReservationStatus.ACTIVE,
            CapacityReservation.ends_at > effective_at,
        )
    )
    if reservation_id is not None:
        raise InvalidRosterChange(
            "Cancel or reassign this Analyst's capacity reservations first."
        )
