"""Public contracts for personal actions and durable notifications."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator

from mist_service.action_notification_models import (
    ActionSection,
    ActionSourceType,
    NotificationEventGroup,
    ProjectionHealth,
)
from mist_service.schemas.common import ApiModel, StrictApiModel


class ActionColumn(StrEnum):
    REFERENCE = "REFERENCE"
    TITLE = "TITLE"
    CURRENT_OWNER = "CURRENT_OWNER"
    REQUIRED_BY = "REQUIRED_BY"
    AGE = "AGE"
    LAST_CHANGED = "LAST_CHANGED"


class ActionAccess(StrEnum):
    PERSONAL = "PERSONAL"
    SHARED = "SHARED"


class ActionFilters(StrictApiModel):
    sections: Annotated[list[ActionSection], Field(max_length=4)] = Field(
        default_factory=list
    )
    action_types: Annotated[list[str], Field(max_length=20)] = Field(
        default_factory=list
    )
    due_before: date | None = None

    @field_validator("action_types")
    @classmethod
    def bounded_action_types(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().upper() for value in values]
        if any(not value or len(value) > 80 for value in cleaned):
            raise ValueError("action types must contain 1 to 80 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("action types must be unique")
        return cleaned


class ProjectionFreshness(ApiModel):
    status: ProjectionHealth
    projected_at: datetime | None
    source_changed_at: datetime | None
    lag_seconds: int | None
    pending_count: int


class ActionItem(ApiModel):
    id: UUID
    section: ActionSection
    action_access: ActionAccess
    action_type: str
    source_type: ActionSourceType
    reference: str
    title: str | None
    current_owner: str
    required_by: date | None
    age_days: int
    last_changed_at: datetime
    deep_link: str | None
    source_version: int
    is_stale: bool


class ActionCounts(ApiModel):
    needs_my_action: int = 0
    waiting: int = 0
    due_soon: int = 0
    recently_completed: int = 0


class SavedActionViewResult(ApiModel):
    id: UUID
    name: str
    filters: ActionFilters
    visible_columns: list[ActionColumn]
    version: int


class ActionWorkspaceResult(ApiModel):
    items: list[ActionItem]
    counts: ActionCounts
    saved_views: list[SavedActionViewResult]
    next_cursor: str | None
    freshness: ProjectionFreshness


class SavedActionViewCommand(StrictApiModel):
    name: Annotated[str, Field(min_length=3, max_length=80)]
    filters: ActionFilters
    visible_columns: Annotated[list[ActionColumn], Field(min_length=1, max_length=6)]

    @field_validator("visible_columns")
    @classmethod
    def unique_columns(cls, values: list[ActionColumn]) -> list[ActionColumn]:
        if len(set(values)) != len(values):
            raise ValueError("visible columns must be unique")
        return values


class SavedActionViewUpdate(SavedActionViewCommand):
    expected_version: Annotated[int, Field(ge=1)]


class NotificationFilterState(StrEnum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"
    ACTION_COMPLETED = "ACTION_COMPLETED"


class NotificationItem(ApiModel):
    id: UUID
    event_type: str
    event_group: NotificationEventGroup
    subject: str
    occurred_at: datetime
    deep_link: str | None
    is_read: bool
    is_archived: bool
    is_action_completed: bool
    read_at: datetime | None
    archived_at: datetime | None
    action_completed_at: datetime | None
    version: int


class NotificationListResult(ApiModel):
    items: list[NotificationItem]
    unread_count: int
    next_cursor: str | None
    freshness: ProjectionFreshness


class NotificationCountResult(ApiModel):
    unread_count: int
    projected_at: datetime | None


class NotificationStateAction(StrEnum):
    MARK_READ = "MARK_READ"
    MARK_UNREAD = "MARK_UNREAD"
    ARCHIVE = "ARCHIVE"
    RESTORE = "RESTORE"
    COMPLETE_ACTION = "COMPLETE_ACTION"


class NotificationStateTarget(StrictApiModel):
    id: UUID
    expected_version: Annotated[int, Field(ge=1)]


class NotificationStateCommand(StrictApiModel):
    action: NotificationStateAction
    targets: Annotated[
        list[NotificationStateTarget], Field(min_length=1, max_length=100)
    ]

    @field_validator("targets")
    @classmethod
    def unique_targets(
        cls, values: list[NotificationStateTarget]
    ) -> list[NotificationStateTarget]:
        if len({target.id for target in values}) != len(values):
            raise ValueError("notification targets must be unique")
        return values


class NotificationStateResult(ApiModel):
    items: list[NotificationItem]


class NotificationPreferenceResult(ApiModel):
    event_group: NotificationEventGroup
    enabled: bool
    mandatory: bool
    reminder_days: list[int]
    version: int


class NotificationPreferencesResult(ApiModel):
    groups: list[NotificationPreferenceResult]


class NotificationPreferenceUpdate(StrictApiModel):
    enabled: bool
    reminder_days: Annotated[list[int], Field(max_length=5)]
    expected_version: Annotated[int, Field(ge=0)]

    @field_validator("reminder_days")
    @classmethod
    def valid_reminder_days(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 90 for value in values):
            raise ValueError("reminder days must be between 0 and 90")
        if values != sorted(set(values), reverse=True):
            raise ValueError("reminder days must be unique in descending order")
        return values
