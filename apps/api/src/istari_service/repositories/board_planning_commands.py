"""Capacity reservation and iteration mutations for team planning."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from istari_service.board_models import (
    CapacityReservation,
    IterationStatus,
    ReservationStatus,
    TeamIteration,
    WorkPackage,
    WorkPackageActivity,
    WorkPackageActivityType,
)
from istari_service.errors import BoardItemNotFound, InvalidBoardChange, StaleVersion
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.schemas.board import (
    IterationCloseCommand,
    IterationCommand,
    ReservationCancelCommand,
    ReservationCommand,
)


class SqlAlchemyBoardPlanningCommandRepository:
    def __init__(self, board: SqlAlchemyBoardRepository) -> None:
        self.board = board
        self.session = board.session

    async def create_reservation(
        self,
        package: WorkPackage,
        actor_id: UUID,
        command: ReservationCommand,
    ) -> CapacityReservation:
        overlap = await self.session.scalar(
            select(CapacityReservation.id).where(
                CapacityReservation.user_id == command.user_id,
                CapacityReservation.status == ReservationStatus.ACTIVE,
                CapacityReservation.starts_at < command.ends_at,
                CapacityReservation.ends_at > command.starts_at,
            )
        )
        if overlap is not None:
            raise InvalidBoardChange(
                "This person already has an overlapping reservation."
            )
        minutes = round((command.ends_at - command.starts_at).total_seconds() / 60)
        reservation = CapacityReservation(
            package_id=package.id,
            team_id=package.team_id,
            user_id=command.user_id,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            minutes=minutes,
            status=ReservationStatus.ACTIVE,
            reason=command.reason.strip(),
            created_by_user_id=actor_id,
            cancelled_by_user_id=None,
            cancellation_reason=None,
            version=1,
        )
        self.session.add(reservation)
        package.version += 1
        self._activity(
            package,
            actor_id,
            WorkPackageActivityType.RESERVATION_CREATED,
            "Capacity reservation created.",
            {"userId": str(command.user_id), "minutes": minutes},
        )
        await self.session.flush()
        return reservation

    async def cancel_reservation(
        self,
        package: WorkPackage,
        reservation_id: UUID,
        actor_id: UUID,
        command: ReservationCancelCommand,
    ) -> CapacityReservation:
        reservation = await self.session.scalar(
            select(CapacityReservation)
            .where(
                CapacityReservation.id == reservation_id,
                CapacityReservation.package_id == package.id,
                CapacityReservation.team_id == package.team_id,
            )
            .with_for_update()
        )
        if reservation is None:
            raise BoardItemNotFound()
        if reservation.version != command.expected_version:
            raise StaleVersion()
        if reservation.status is ReservationStatus.CANCELLED:
            raise InvalidBoardChange("This reservation is already cancelled.")
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_by_user_id = actor_id
        reservation.cancellation_reason = command.reason.strip()
        reservation.version += 1
        package.version += 1
        self._activity(
            package,
            actor_id,
            WorkPackageActivityType.RESERVATION_CANCELLED,
            "Capacity reservation cancelled.",
            {"reason": command.reason.strip()},
        )
        return reservation

    async def create_iteration(
        self, actor_id: UUID, team_id: UUID, command: IterationCommand
    ) -> TeamIteration:
        today = datetime.now(UTC).date()
        status = (
            IterationStatus.ACTIVE
            if command.starts_on <= today <= command.ends_on
            else IterationStatus.PLANNED
        )
        iteration = TeamIteration(
            team_id=team_id,
            name=command.name.strip(),
            goal=command.goal.strip(),
            starts_on=command.starts_on,
            ends_on=command.ends_on,
            status=status,
            completion_summary=None,
            created_by_user_id=actor_id,
            version=1,
        )
        self.session.add(iteration)
        await self.session.flush()
        return iteration

    async def close_iteration(
        self,
        team_id: UUID,
        iteration_id: UUID,
        command: IterationCloseCommand,
    ) -> TeamIteration:
        iteration = await self.session.scalar(
            select(TeamIteration)
            .where(TeamIteration.id == iteration_id, TeamIteration.team_id == team_id)
            .with_for_update()
        )
        if iteration is None:
            raise BoardItemNotFound()
        if iteration.version != command.expected_version:
            raise StaleVersion()
        if iteration.status is IterationStatus.CLOSED:
            raise InvalidBoardChange("This iteration is already closed.")
        iteration.status = IterationStatus.CLOSED
        iteration.completion_summary = command.completion_summary.strip()
        iteration.version += 1
        return iteration

    def _activity(
        self,
        package: WorkPackage,
        actor_id: UUID,
        type_: WorkPackageActivityType,
        summary: str,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            WorkPackageActivity(
                package_id=package.id,
                team_id=package.team_id,
                actor_user_id=actor_id,
                type=type_,
                summary=summary,
                details=details,
            )
        )
