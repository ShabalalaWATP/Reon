"""Neutral application contracts for board and team-planning use cases."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from mist_service.board_models import BoardColumn, IterationStatus, WorkPackageStatus
from mist_service.management_models import ManagementAction
from mist_service.schemas.board import (
    BoardConfigurationCommand,
    BoardFilters,
    BoardItem,
    IterationCloseCommand,
    IterationCommand,
    IterationResult,
    ReservationCancelCommand,
    ReservationCommand,
    SavedBoardViewCommand,
    SavedBoardViewResult,
    SavedBoardViewUpdate,
    WorkPackageCommand,
    WorkPackageResult,
)


class WorkPackageRecord(Protocol):
    id: UUID
    team_id: UUID
    linked_request_id: UUID | None
    owner_user_id: UUID
    status: WorkPackageStatus
    version: int


class IterationRecord(Protocol):
    id: UUID
    name: str
    goal: str
    starts_on: date
    ends_on: date
    status: IterationStatus
    completion_summary: str | None
    version: int


class BoardConfigurationRecord(Protocol):
    wip_limits: dict[str, int]
    version: int


class SavedBoardViewRecord(Protocol):
    id: UUID
    name: str
    filters: dict[str, object]
    version: int


class BoardQueryPort(Protocol):
    async def board_page(
        self, team_id: UUID, filters: BoardFilters, cursor: str | None, limit: int
    ) -> tuple[list[BoardItem], str | None]: ...

    async def board_column_counts(
        self, team_id: UUID, filters: BoardFilters
    ) -> dict[BoardColumn, int]: ...

    async def configuration(self, team_id: UUID) -> BoardConfigurationRecord | None: ...

    async def saved_views(
        self, team_id: UUID, owner_id: UUID
    ) -> list[SavedBoardViewResult]: ...

    async def request_item(self, team_id: UUID, request_id: UUID) -> BoardItem: ...

    async def list_packages(
        self, team_id: UUID, limit: int
    ) -> list[WorkPackageResult]: ...

    async def package(self, team_id: UUID, package_id: UUID) -> WorkPackageResult: ...

    async def column_count(
        self,
        team_id: UUID,
        column: BoardColumn,
        *,
        exclude_package_id: UUID,
    ) -> int: ...


class BoardPlanningReadPort(Protocol):
    async def locked_package(
        self, team_id: UUID, package_id: UUID, expected_version: int
    ) -> WorkPackageRecord: ...

    async def lock_planning_aggregate(self, team_id: UUID) -> None: ...

    async def current_member_ids(self, team_id: UUID) -> set[UUID]: ...

    async def is_contributor(self, package_id: UUID, user_id: UUID) -> bool: ...

    async def package_contributor_ids(self, package_id: UUID) -> set[UUID]: ...

    async def request_belongs_to_team(
        self, team_id: UUID, request_id: UUID
    ) -> bool: ...

    async def request_requester_id(self, request_id: UUID) -> UUID | None: ...

    async def package_ids_in_team(
        self, team_id: UUID, package_ids: set[UUID]
    ) -> set[UUID]: ...

    async def iteration_in_team(self, team_id: UUID, iteration_id: UUID) -> bool: ...

    async def iterations(self, team_id: UUID) -> list[IterationResult]: ...

    async def has_management_authority(
        self,
        *,
        actor_id: UUID,
        grant_id: UUID,
        team_id: UUID,
        action: ManagementAction,
    ) -> bool: ...


class BoardCommandPort(Protocol):
    async def create_package(
        self, actor_id: UUID, team_id: UUID, command: WorkPackageCommand
    ) -> WorkPackageRecord: ...

    async def replace_package(
        self,
        package: WorkPackageRecord,
        actor_id: UUID,
        command: WorkPackageCommand,
    ) -> WorkPackageRecord: ...

    async def move_package(
        self,
        package: WorkPackageRecord,
        actor_id: UUID,
        target: WorkPackageStatus,
        reason: str,
    ) -> WorkPackageRecord: ...

    async def dependency_cycle(
        self, team_id: UUID, package_id: UUID, proposed: set[UUID]
    ) -> bool: ...

    async def set_configuration(
        self, team_id: UUID, command: BoardConfigurationCommand
    ) -> BoardConfigurationRecord: ...

    async def create_saved_view(
        self, actor_id: UUID, team_id: UUID, command: SavedBoardViewCommand
    ) -> SavedBoardViewRecord: ...

    async def update_saved_view(
        self,
        actor_id: UUID,
        team_id: UUID,
        view_id: UUID,
        command: SavedBoardViewUpdate,
    ) -> SavedBoardViewRecord: ...

    async def delete_saved_view(
        self, actor_id: UUID, team_id: UUID, view_id: UUID, expected_version: int
    ) -> None: ...


class BoardPlanningCommandPort(Protocol):
    async def create_reservation(
        self,
        package: WorkPackageRecord,
        actor_id: UUID,
        command: ReservationCommand,
    ) -> object: ...

    async def cancel_reservation(
        self,
        package: WorkPackageRecord,
        reservation_id: UUID,
        actor_id: UUID,
        command: ReservationCancelCommand,
    ) -> object: ...

    async def create_iteration(
        self, actor_id: UUID, team_id: UUID, command: IterationCommand
    ) -> IterationRecord: ...

    async def close_iteration(
        self,
        team_id: UUID,
        iteration_id: UUID,
        command: IterationCloseCommand,
    ) -> IterationRecord: ...


class BoardIterationAnalyticsPort(Protocol):
    async def project_closed_iteration(
        self, iteration: IterationRecord, *, occurred_at: datetime
    ) -> None: ...
