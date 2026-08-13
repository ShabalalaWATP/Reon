"""Manager-only task hastener use case."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from istari_service.domain import Actor
from istari_service.errors import InvalidAction, TeamWorkspaceNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.notification_catalog import render_subject
from istari_service.notification_rule_serialisation import serialise_rule
from istari_service.organisation_models import OrganisationKind
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.task_hasteners import (
    SqlAlchemyTaskHastenerRepository,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.request_event_audience import RequestEventAudience
from istari_service.schemas.task_hasteners import (
    HastenerAudience,
    TaskHastenerCommand,
    TaskHastenerRecipient,
    TaskHastenerResult,
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
        repository: SqlAlchemyTaskHastenerRepository,
        workspaces: SqlAlchemyTeamWorkspaceRepository,
    ) -> None:
        self._repository = repository
        self._workspaces = workspaces

    async def send(
        self,
        actor: Actor,
        team_id: UUID,
        request_id: UUID,
        command: TaskHastenerCommand,
    ) -> TaskHastenerResult:
        access = await self._workspaces.require_read(actor.id, team_id)
        if (
            access.unit_kind is not OrganisationKind.TEAM
            or access.workspace_position is not WorkspacePosition.MANAGER
        ):
            raise TeamWorkspaceNotFound()
        request = await self._repository.request_for_team(team_id, request_id)
        if request is None:
            raise TeamWorkspaceNotFound()
        if request.status not in ACTIVE_PRODUCTION_STATUSES:
            raise InvalidAction(
                "Hasteners are available only while assigned production work is active."
            )
        available = await self._repository.active_recipients(team_id, request_id)
        recipients = _select_recipients(command, available)
        event_message = _event_message(command.message, recipients)
        event = await append_request_event(
            self._repository.session,
            request_id=request.id,
            actor_id=actor.id,
            event_type="task_hastener",
            message=event_message,
            prior_status=request.status,
            next_status=request.status,
            audience=RequestEventAudience.STAFF_ONLY,
            details={
                "audience": command.audience.value,
                "recipientCount": len(recipients),
                "recipientUserIds": [str(item.user_id) for item in recipients],
            },
        )
        notified_user_ids = await self._notify(
            request.reference,
            request.id,
            team_id,
            event.event_hash,
            request.audit_event_count,
            recipients,
            event.created_at,
        )
        _require_all_notified(recipients, notified_user_ids)
        return TaskHastenerResult(
            event_id=event.id,
            request_id=request.id,
            message=command.message,
            sender_display_name=actor.display_name,
            recipients=recipients,
            created_at=event.created_at,
        )

    async def _notify(
        self,
        reference: str,
        request_id: UUID,
        team_id: UUID,
        event_hash: str,
        source_version: int,
        recipients: list[TaskHastenerRecipient],
        occurred_at: datetime,
    ) -> frozenset[UUID]:
        projection = SqlAlchemyNotificationProjectionRepository(
            self._repository.session
        )
        event_type, subject = render_subject("TASK_HASTENER", reference)
        rules = [
            RecipientRule(
                item.user_id,
                NotificationAccessKind.ROUTE_MEMBER,
                UserRole.DELIVERY_SPECIALIST,
                organisation_unit_id=team_id,
            )
            for item in recipients
        ]
        event = await projection.publish_event(
            stable_key=f"request-event:{event_hash}",
            event_type=event_type,
            event_group=NotificationEventGroup.ASSIGNMENT,
            source_version=source_version,
            request_id=request_id,
            safe_subject=subject,
            deep_link=f"/teams/{team_id}/board?itemId={request_id}",
            audience=[serialise_rule(rule) for rule in rules],
            occurred_at=occurred_at,
        )
        projected = await projection.project_event(
            event.id, rules, projected_at=occurred_at
        )
        return frozenset(item.recipient_user_id for item in projected)


def _select_recipients(
    command: TaskHastenerCommand,
    available: list[TaskHastenerRecipient],
) -> list[TaskHastenerRecipient]:
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


def _event_message(message: str, recipients: list[TaskHastenerRecipient]) -> str:
    names = ", ".join(item.display_name for item in recipients)
    return f"Hastener sent to {names}: {message}"


def _require_all_notified(
    recipients: list[TaskHastenerRecipient], notified_user_ids: frozenset[UUID]
) -> None:
    if notified_user_ids != frozenset(item.user_id for item in recipients):
        raise InvalidAction(
            "The assigned Analysts changed while the hastener was being sent. "
            "Refresh the request and try again."
        )
