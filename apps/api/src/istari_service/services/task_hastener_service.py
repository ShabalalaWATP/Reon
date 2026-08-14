"""Manager-only task hastener use case."""

from __future__ import annotations

from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import InvalidAction, TeamWorkspaceNotFound
from istari_service.identity_context import require_staff_context
from istari_service.models import RequestStatus
from istari_service.organisation_models import OrganisationKind
from istari_service.request_identity_policy import require_requester_excluded
from istari_service.schemas.task_hasteners import (
    HastenerAudience,
    TaskHastenerCommand,
    TaskHastenerRecipient,
    TaskHastenerResult,
)
from istari_service.task_hastener_ports import (
    TaskHastenerEventWriter,
    TaskHastenerNotifier,
    TaskHastenerRecipientRecord,
    TaskHastenerRequestReader,
    TaskHastenerWorkspaceReader,
)
from istari_service.team_models import WorkspacePosition

ACTIVE_PRODUCTION_STATUSES = {
    RequestStatus.IN_PROGRESS,
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
    RequestStatus.REWORK_REQUIRED,
}


class TaskHastenerService:
    def __init__(
        self,
        repository: TaskHastenerRequestReader,
        workspaces: TaskHastenerWorkspaceReader,
        events: TaskHastenerEventWriter,
        notifier: TaskHastenerNotifier,
    ) -> None:
        self._repository = repository
        self._workspaces = workspaces
        self._events = events
        self._notifier = notifier

    async def send(
        self,
        actor: Actor,
        team_id: UUID,
        request_id: UUID,
        command: TaskHastenerCommand,
    ) -> TaskHastenerResult:
        require_staff_context(actor, TeamWorkspaceNotFound())
        access = await self._workspaces.require_read(actor.id, team_id)
        if (
            access.unit_kind is not OrganisationKind.TEAM
            or access.workspace_position is not WorkspacePosition.MANAGER
        ):
            raise TeamWorkspaceNotFound()
        request = await self._repository.request_for_team(team_id, request_id)
        if request is None:
            raise TeamWorkspaceNotFound()
        require_requester_excluded(
            request.requester_id, [actor.id], TeamWorkspaceNotFound()
        )
        if request.status not in ACTIVE_PRODUCTION_STATUSES:
            raise InvalidAction(
                "Hasteners are available only while assigned production work is active."
            )
        available = await self._repository.active_recipients(team_id, request_id)
        recipients = _select_recipients(command, available)
        event_message = _event_message(command.message, recipients)
        event = await self._events.append(
            request=request,
            actor_id=actor.id,
            message=event_message,
            recipient_ids=[item.user_id for item in recipients],
            audience=command.audience.value,
        )
        notified_user_ids = await self._notifier.notify(
            request=request,
            team_id=team_id,
            event=event,
            recipients=recipients,
        )
        _require_all_notified(recipients, notified_user_ids)
        return TaskHastenerResult(
            event_id=event.id,
            request_id=request.id,
            message=command.message,
            sender_display_name=actor.display_name,
            recipients=[_recipient_result(item) for item in recipients],
            created_at=event.created_at,
        )


def _select_recipients(
    command: TaskHastenerCommand,
    available: list[TaskHastenerRecipientRecord],
) -> list[TaskHastenerRecipientRecord]:
    if not available:
        raise InvalidAction("This request has no active assigned Analysts.")
    if command.audience is HastenerAudience.ALL_ASSIGNED:
        return available
    selected = [item for item in available if item.user_id == command.recipient_user_id]
    if not selected:
        raise InvalidAction(
            "Select an active Analyst assigned to this request and team."
        )
    return selected


def _event_message(message: str, recipients: list[TaskHastenerRecipientRecord]) -> str:
    names = ", ".join(item.display_name for item in recipients)
    return f"Hastener sent to {names}: {message}"


def _require_all_notified(
    recipients: list[TaskHastenerRecipientRecord],
    notified_user_ids: frozenset[UUID],
) -> None:
    if notified_user_ids != frozenset(item.user_id for item in recipients):
        raise InvalidAction(
            "The assigned Analysts changed while the hastener was being sent. "
            "Refresh the request and try again."
        )


def _recipient_result(
    recipient: TaskHastenerRecipientRecord,
) -> TaskHastenerRecipient:
    return TaskHastenerRecipient(
        user_id=recipient.user_id,
        display_name=recipient.display_name,
        assignment_role=recipient.assignment_role,
    )
