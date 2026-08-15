"""Validated product-side commands for durable human workflow actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from mist_service.models import RequestStatus
from mist_service.schemas.work import CompletionPayload


class WorkCommandType(StrEnum):
    CLAIM_TASK = "CLAIM_TASK"
    COMPLETE_TASK = "COMPLETE_TASK"


@dataclass(frozen=True, slots=True)
class RoutingSelection:
    unit_id: UUID
    unit_code: str
    unit_name: str
    position: int
    candidate_groups: tuple[str, ...]
    staffed: bool

    def __post_init__(self) -> None:
        if (
            not self.unit_code.strip()
            or not self.unit_name.strip()
            or self.position not in {1, 2, 3}
        ):
            raise ValueError("invalid routing selection")
        if not self.candidate_groups or any(
            not group.strip() for group in self.candidate_groups
        ):
            raise ValueError("routing candidate groups must not be empty")


@dataclass(frozen=True, slots=True)
class PendingWorkCommand:
    outbox_id: UUID
    command_type: WorkCommandType
    work_id: UUID
    task_key: str
    process_instance_key: str
    element_id: str
    actor_id: UUID
    request_version: int
    request_status: RequestStatus
    attempts: int
    completion: CompletionPayload | None = None
    routing: RoutingSelection | None = None


_COMPLETION_ADAPTER: TypeAdapter[CompletionPayload] = TypeAdapter(CompletionPayload)


def command_payload(
    *,
    work_id: UUID,
    task_key: str,
    process_instance_key: str,
    element_id: str,
    actor_id: UUID,
    request_version: int,
    request_status: RequestStatus,
    completion: CompletionPayload | None = None,
    routing: RoutingSelection | None = None,
) -> dict[str, Any]:
    """Serialise only validated action data and opaque workflow identifiers."""

    payload: dict[str, Any] = {
        "workId": str(work_id),
        "taskKey": task_key,
        "processInstanceKey": process_instance_key,
        "elementId": element_id,
        "actorId": str(actor_id),
        "requestVersion": request_version,
        "requestStatus": request_status.value,
    }
    if completion is not None:
        payload["completion"] = completion.model_dump(mode="json", by_alias=False)
    if routing is not None:
        payload["routing"] = {
            "unitId": str(routing.unit_id),
            "unitCode": routing.unit_code,
            "unitName": routing.unit_name,
            "position": routing.position,
            "candidateGroups": list(routing.candidate_groups),
            "staffed": routing.staffed,
        }
    return payload


def parse_command(
    outbox_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    attempts: int,
) -> PendingWorkCommand:
    """Fail closed when a stored command no longer matches the pinned contract."""

    command_type = WorkCommandType(event_type)
    raw_completion = payload.get("completion")
    completion = (
        _COMPLETION_ADAPTER.validate_python(raw_completion)
        if raw_completion is not None
        else None
    )
    raw_routing = payload.get("routing")
    routing = _parse_routing(raw_routing) if raw_routing is not None else None
    if command_type is WorkCommandType.COMPLETE_TASK and completion is None:
        raise ValueError("completion payload is required")
    if command_type is WorkCommandType.CLAIM_TASK and (
        completion is not None or routing is not None
    ):
        raise ValueError("claim commands cannot contain completion data")
    _validate_routing_contract(completion, routing)
    return PendingWorkCommand(
        outbox_id=outbox_id,
        command_type=command_type,
        work_id=UUID(payload["workId"]),
        task_key=str(payload["taskKey"]),
        process_instance_key=str(payload["processInstanceKey"]),
        element_id=str(payload["elementId"]),
        actor_id=UUID(payload["actorId"]),
        request_version=int(payload["requestVersion"]),
        request_status=RequestStatus(payload["requestStatus"]),
        attempts=attempts,
        completion=completion,
        routing=routing,
    )


def _parse_routing(value: object) -> RoutingSelection:
    if not isinstance(value, dict):
        raise ValueError("routing must be an object")
    groups = value.get("candidateGroups")
    if not isinstance(groups, list) or any(
        not isinstance(item, str) for item in groups
    ):
        raise ValueError("routing candidate groups must be strings")
    return RoutingSelection(
        unit_id=UUID(str(value["unitId"])),
        unit_code=str(value["unitCode"]),
        unit_name=str(value["unitName"]),
        position=int(value["position"]),
        candidate_groups=tuple(groups),
        staffed=value["staffed"] is True,
    )


def _validate_routing_contract(
    completion: CompletionPayload | None,
    routing: RoutingSelection | None,
) -> None:
    expected = {
        "progress": (1, 1),
        "send_to_allocation": (2, 1),
        "allocate": (3, 2),
    }.get(completion.action if completion else "")
    if expected is None:
        if routing is not None:
            raise ValueError("routing is not valid for this completion")
        return
    if routing is None or (routing.position, len(routing.candidate_groups)) != expected:
        raise ValueError("completion routing does not match the action")
