"""Content-minimised configuration lifecycle events and publisher port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ConfigurationEventType(StrEnum):
    AWAITING_REVIEW = "CONFIGURATION_AWAITING_REVIEW"
    ACTIVATED = "CONFIGURATION_ACTIVATED"
    REJECTED = "CONFIGURATION_REJECTED"
    SUPERSEDED = "CONFIGURATION_SUPERSEDED"


@dataclass(frozen=True, slots=True)
class ConfigurationLifecycleEvent:
    """A content-free signal containing identifiers and lifecycle metadata only."""

    type: ConfigurationEventType
    configuration_version_id: UUID
    configuration_sequence: int
    actor_user_id: UUID
    occurred_at: datetime
    source_version: int
    superseded_configuration_version_id: UUID | None = None


class ConfigurationEventPublisher(Protocol):
    async def publish(self, event: ConfigurationLifecycleEvent) -> None:
        """Persist or enqueue the event in the caller's unit of work."""


class NullConfigurationEventPublisher:
    async def publish(self, event: ConfigurationLifecycleEvent) -> None:
        del event
