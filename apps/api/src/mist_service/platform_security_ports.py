"""Persistence-independent platform-security application contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.platform_security_types import PlatformClassification
from mist_service.schemas.platform_security import PlatformClassificationView


@dataclass(frozen=True, slots=True)
class ClassificationRecord:
    id: UUID
    classification: PlatformClassification
    version: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AssistanceUserRecord:
    id: UUID
    username: str
    email: str


@dataclass(frozen=True, slots=True)
class AssistanceAttemptRecord:
    id: UUID
    email_hash: str | None
    email_key_id: str | None


class ClassificationPort(Protocol):
    async def classification(self, *, lock: bool = False) -> ClassificationRecord: ...

    async def update_classification(
        self,
        setting: ClassificationRecord,
        *,
        classification: PlatformClassification,
        actor_id: UUID,
    ) -> PlatformClassificationView: ...


class AssistanceBudgetPort(Protocol):
    async def lock_assistance_budget(self) -> None: ...

    async def attempt_count(
        self, *, since: datetime, source_key: str | None = None
    ) -> int: ...

    async def add_attempt(
        self,
        *,
        source_key: str,
        matched_user_id: UUID | None,
        email_hash: str | None = None,
        email_key_id: str | None = None,
    ) -> UUID: ...

    async def prune_attempts(self, before: datetime) -> None: ...


class AssistanceDirectoryPort(Protocol):
    async def active_user_by_email_hash(
        self, email_hash: str, key_id: str
    ) -> AssistanceUserRecord | None: ...

    async def has_recent_user_attempt(self, user_id: UUID, since: datetime) -> bool: ...

    async def match_attempt(self, attempt_id: UUID, user_id: UUID) -> None: ...

    async def active_administrator_ids(self) -> list[UUID]: ...

    async def users_needing_assistance_index(
        self, key_id: str
    ) -> list[AssistanceUserRecord]: ...

    async def set_assistance_index(
        self, user_id: UUID, *, email_hash: str, key_id: str
    ) -> None: ...

    async def assistance_index_is_complete(self, key_id: str) -> bool: ...


class AssistanceQueuePort(Protocol):
    async def pending_attempt(
        self, now: datetime
    ) -> AssistanceAttemptRecord | None: ...

    async def complete_attempt(self, attempt_id: UUID, now: datetime) -> None: ...

    async def retry_attempt(self, attempt_id: UUID, now: datetime) -> None: ...


class PasswordAssistancePublisherPort(Protocol):
    async def publish_password_assistance(
        self,
        attempt_id: UUID,
        user: AssistanceUserRecord,
        administrator_ids: list[UUID],
        occurred_at: datetime,
    ) -> None: ...
