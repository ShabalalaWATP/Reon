"""Validated workflow-board and independent work-package contracts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mist_service.board_models import (
    BoardColumn,
    IterationStatus,
    ReservationStatus,
    WorkPackageActivityType,
    WorkPackagePriority,
    WorkPackageStatus,
)

Title = Annotated[str, Field(min_length=3, max_length=160)]
Detail = Annotated[str, Field(min_length=1, max_length=4000)]
Reason = Annotated[str, Field(min_length=10, max_length=500)]


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(item.title() for item in rest)


class BoardModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )


class BoardItemType(StrEnum):
    SERVICE_REQUEST = "SERVICE_REQUEST"
    WORK_PACKAGE = "WORK_PACKAGE"


class BoardFilters(BoardModel):
    search: Annotated[str, Field(max_length=120)] = ""
    columns: list[BoardColumn] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    owner_user_id: UUID | None = None
    item_types: list[BoardItemType] = Field(default_factory=list)
    due_before: date | None = None


class BoardItem(BoardModel):
    id: UUID
    item_type: BoardItemType
    reference: str
    title: str
    column: BoardColumn
    priority: str
    due_on: date
    owner_user_id: UUID | None
    owner_display_name: str | None
    version: int
    linked_request_id: UUID | None
    available_columns: list[BoardColumn]
    changed_at: datetime


class SavedBoardViewResult(BoardModel):
    id: UUID
    name: str
    filters: BoardFilters
    version: int


class BoardResult(BoardModel):
    items: list[BoardItem]
    next_cursor: str | None
    column_counts: dict[BoardColumn, int]
    total_count: int = Field(ge=0)
    wip_limits: dict[str, int]
    configuration_version: int
    saved_views: list[SavedBoardViewResult]
    generated_at: datetime


class WorkPackageCommand(BoardModel):
    grant_id: UUID | None = None
    title: Title
    description: Detail
    owner_user_id: UUID
    contributor_ids: Annotated[list[UUID], Field(max_length=50)]
    estimate_points: Annotated[int, Field(ge=1, le=100)]
    remaining_effort_minutes: Annotated[int, Field(ge=0, le=100_000)]
    due_on: date
    priority: WorkPackagePriority
    blockers: Detail
    acceptance_criteria: Detail
    linked_request_id: UUID | None
    dependency_ids: Annotated[list[UUID], Field(max_length=50)]
    iteration_id: UUID | None

    @model_validator(mode="after")
    def unique_links(self) -> WorkPackageCommand:
        if len(set(self.contributor_ids)) != len(self.contributor_ids):
            raise ValueError("Contributors must be unique.")
        if len(set(self.dependency_ids)) != len(self.dependency_ids):
            raise ValueError("Dependencies must be unique.")
        return self


class WorkPackageUpdate(WorkPackageCommand):
    expected_version: Annotated[int, Field(ge=1)]


class WorkPackageMove(BoardModel):
    grant_id: UUID | None = None
    expected_version: Annotated[int, Field(ge=1)]
    target: WorkPackageStatus
    reason: Reason


class WorkPackageContributorResult(BoardModel):
    user_id: UUID
    display_name: str


class WorkPackageActivityResult(BoardModel):
    id: UUID
    type: WorkPackageActivityType
    summary: str
    actor_display_name: str
    created_at: datetime


class CapacityReservationResult(BoardModel):
    id: UUID
    user_id: UUID
    user_display_name: str
    starts_at: datetime
    ends_at: datetime
    minutes: int
    status: ReservationStatus
    reason: str
    version: int


class WorkPackageResult(BoardModel):
    id: UUID
    team_id: UUID
    linked_request_id: UUID | None
    iteration_id: UUID | None
    title: str
    description: str
    owner_user_id: UUID
    owner_display_name: str
    contributors: list[WorkPackageContributorResult]
    estimate_points: int
    remaining_effort_minutes: int
    due_on: date
    priority: WorkPackagePriority
    status: WorkPackageStatus
    blockers: str
    acceptance_criteria: str
    dependency_ids: list[UUID]
    version: int
    activities: list[WorkPackageActivityResult]
    reservations: list[CapacityReservationResult]


class WorkPackageList(BoardModel):
    items: list[WorkPackageResult]


class BoardConfigurationCommand(BoardModel):
    grant_id: UUID
    expected_version: Annotated[int, Field(ge=0)]
    wip_limits: dict[BoardColumn, Annotated[int, Field(ge=1, le=100)]]

    @model_validator(mode="after")
    def active_columns_only(self) -> BoardConfigurationCommand:
        disallowed = {
            BoardColumn.COMPLETED,
            BoardColumn.CANCELLED,
            BoardColumn.BACKLOG,
        }
        if set(self.wip_limits) & disallowed:
            raise ValueError("WIP limits apply only to active delivery columns.")
        return self


class BoardConfigurationResult(BoardModel):
    wip_limits: dict[str, int]
    version: int


class SavedBoardViewCommand(BoardModel):
    name: Annotated[str, Field(min_length=3, max_length=80)]
    filters: BoardFilters


class SavedBoardViewUpdate(SavedBoardViewCommand):
    expected_version: Annotated[int, Field(ge=1)]


class ReservationCommand(BoardModel):
    grant_id: UUID | None = None
    user_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: Reason

    @model_validator(mode="after")
    def valid_window(self) -> ReservationCommand:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Reservation times require a time zone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("The reservation end must follow its start.")
        if self.ends_at - self.starts_at > timedelta(days=31):
            raise ValueError("Reservations are limited to 31 days.")
        return self


class ReservationCancelCommand(BoardModel):
    grant_id: UUID | None = None
    expected_version: Annotated[int, Field(ge=1)]
    reason: Reason


class IterationCommand(BoardModel):
    grant_id: UUID
    name: Annotated[str, Field(min_length=3, max_length=100)]
    goal: Detail
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def valid_window(self) -> IterationCommand:
        if self.ends_on < self.starts_on:
            raise ValueError("The iteration end cannot precede its start.")
        if (self.ends_on - self.starts_on).days > 90:
            raise ValueError("Iterations are limited to 91 days.")
        return self


class IterationCloseCommand(BoardModel):
    grant_id: UUID
    expected_version: Annotated[int, Field(ge=1)]
    completion_summary: Detail


class IterationResult(BoardModel):
    id: UUID
    name: str
    goal: str
    starts_on: date
    ends_on: date
    status: IterationStatus
    completion_summary: str | None
    version: int


class IterationList(BoardModel):
    items: list[IterationResult]


class BoardMoveAttempt(BoardModel):
    grant_id: UUID | None = None
    item_type: BoardItemType
    item_id: UUID
    target: BoardColumn
    expected_version: Annotated[int, Field(ge=1)]
    reason: Reason


class DeleteSavedViewCommand(BoardModel):
    expected_version: Annotated[int, Field(ge=1)]


def normalise_filters(value: dict[str, Any]) -> BoardFilters:
    return BoardFilters.model_validate(value)
