"""Validated durable command used to start a request workflow."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

CHECKSUM_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class WorkflowStartCommand:
    request_id: UUID
    requester_id: UUID
    process_id: str
    process_version: int | None = None
    process_checksum: str | None = None

    def __post_init__(self) -> None:
        if (
            not 0 < len(self.process_id) <= 160
            or self.process_id.strip() != self.process_id
        ):
            raise ValueError("process ID must be a non-blank bounded string")
        if self.process_version is not None and (
            isinstance(self.process_version, bool) or self.process_version < 1
        ):
            raise ValueError("process version must be a positive integer")
        if self.process_checksum is not None and not CHECKSUM_PATTERN.fullmatch(
            self.process_checksum
        ):
            raise ValueError("process checksum must be a SHA-256 hexadecimal value")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "requestId": str(self.request_id),
            "requesterId": str(self.requester_id),
            "processId": self.process_id,
        }
        if self.process_version is not None:
            payload["processVersion"] = self.process_version
        if self.process_checksum is not None:
            payload["processChecksum"] = self.process_checksum
        return payload

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
        *,
        legacy_process_id: str | None = None,
    ) -> WorkflowStartCommand:
        try:
            request_id = UUID(_required_string(payload, "requestId"))
            requester_id = UUID(_required_string(payload, "requesterId"))
            process_id = _optional_string(payload, "processId") or legacy_process_id
            if process_id is None:
                raise ValueError("processId is required")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "workflow start payload has invalid identity fields"
            ) from error
        version = payload.get("processVersion")
        if version is not None and (
            not isinstance(version, int) or isinstance(version, bool)
        ):
            raise ValueError("workflow start payload has an invalid process version")
        checksum = payload.get("processChecksum")
        if checksum is not None and not isinstance(checksum, str):
            raise ValueError("workflow start payload has an invalid process checksum")
        return cls(request_id, requester_id, process_id, version, checksum)


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value
