"""Fail-closed comparison of immutable and mutable workflow start identity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PinnedWorkflowIdentity:
    process_id: str
    process_version: int
    process_checksum: str


def pinned_workflow_identity(
    snapshot: Mapping[str, Any],
) -> PinnedWorkflowIdentity | None:
    process_id = snapshot.get("processId")
    process_version = snapshot.get("processVersion")
    process_checksum = snapshot.get("processChecksum")
    if (
        not isinstance(process_id, str)
        or not 0 < len(process_id) <= 160
        or not isinstance(process_version, int)
        or isinstance(process_version, bool)
        or process_version < 1
        or not isinstance(process_checksum, str)
        or len(process_checksum) != 64
    ):
        return None
    return PinnedWorkflowIdentity(
        process_id=process_id,
        process_version=process_version,
        process_checksum=process_checksum,
    )


def pinned_start_identity_matches(
    snapshot: Mapping[str, Any],
    outbox_payload: Mapping[str, Any],
    *,
    instance_process_id: str | None,
    instance_process_version: int | None,
    instance_process_checksum: str | None,
) -> bool:
    pinned = pinned_workflow_identity(snapshot)
    return bool(
        pinned is not None
        and outbox_payload.get("processId") == pinned.process_id
        and outbox_payload.get("processVersion") == pinned.process_version
        and outbox_payload.get("processChecksum") == pinned.process_checksum
        and instance_process_id == pinned.process_id
        and instance_process_version == pinned.process_version
        and instance_process_checksum == pinned.process_checksum
    )
