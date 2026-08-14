"""Independent, fail-safe persistence for content-free security outcomes."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.compliance_models import SecurityEvent, SecurityOutcome


@dataclass(frozen=True, slots=True)
class SecurityEventCommand:
    event_type: str
    outcome: SecurityOutcome
    reason_code: str
    actor_user_id: UUID | None = None
    subject: str | None = None
    source: str | None = None
    correlation_id: str | None = None
    request_method: str | None = None
    route_template: str | None = None


class SecurityEventRecorder:
    """Build atomic success evidence and independently retain rejected work."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        pseudonym_key: bytes,
    ) -> None:
        if len(pseudonym_key) < 32:
            raise ValueError("security-event pseudonym key must contain 32 bytes")
        self._sessions = sessions
        self._key = pseudonym_key

    async def record(self, command: SecurityEventCommand) -> None:
        async with self._sessions() as session, session.begin():
            session.add(self.build(command))

    def build(self, command: SecurityEventCommand) -> SecurityEvent:
        """Build an event that a caller can commit with protected state."""

        _validate(command)
        return SecurityEvent(**self._values(command))

    async def record_once(
        self,
        command: SecurityEventCommand,
        *,
        bucket_seconds: int = 300,
        now: datetime | None = None,
    ) -> bool:
        """Atomically retain only the first matching event in a time bucket."""

        _validate(command)
        if bucket_seconds < 1:
            raise ValueError("security-event bucket must be positive")
        instant = now or datetime.now(UTC)
        bucket = int(instant.timestamp()) // bucket_seconds
        values = self._values(command)
        values["deduplication_key"] = self._deduplication_key(command, bucket)
        async with self._sessions() as session, session.begin():
            dialect = session.get_bind().dialect.name
            insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
            result = await session.execute(
                insert(SecurityEvent)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["deduplication_key"])
                .returning(SecurityEvent.id)
            )
            return result.scalar_one_or_none() is not None

    def _values(self, command: SecurityEventCommand) -> dict[str, object | None]:
        return {
            "event_type": command.event_type,
            "outcome": command.outcome.value,
            "actor_user_id": command.actor_user_id,
            "subject_hash": self._digest(command.subject),
            "source_hash": self._digest(command.source),
            "reason_code": command.reason_code,
            "correlation_id": command.correlation_id,
            "request_method": command.request_method,
            "route_template": command.route_template,
        }

    def _deduplication_key(self, command: SecurityEventCommand, bucket: int) -> str:
        source_hash = self._digest(command.source) or ""
        if command.event_type == "AUTHORIZATION_DENIAL" and command.actor_user_id:
            source_hash = ""
        parts = (
            command.event_type,
            str(command.actor_user_id or ""),
            source_hash,
            command.request_method or "",
            command.route_template or "",
            command.reason_code,
            str(bucket),
        )
        return hmac.new(
            self._key, "\x1f".join(parts).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _digest(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = value.strip().casefold().encode("utf-8")
        return hmac.new(self._key, normalised, hashlib.sha256).hexdigest()


def _validate(command: SecurityEventCommand) -> None:
    for label, value, maximum in (
        ("event type", command.event_type, 80),
        ("reason code", command.reason_code, 80),
        ("correlation ID", command.correlation_id, 80),
        ("request method", command.request_method, 10),
        ("route template", command.route_template, 160),
    ):
        if value is not None and (not value or len(value) > maximum):
            raise ValueError(f"security-event {label} is invalid")
