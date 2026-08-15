"""Persistence queries for exact-team task hasteners."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from mist_service.models import ServiceRequest, User, UserRole
from mist_service.notification_catalog import render_subject
from mist_service.notification_ports import RecipientRule
from mist_service.notification_rule_serialisation import serialise_rule
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.notification_projection import (
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from mist_service.request_event_audience import RequestEventAudience
from mist_service.request_participant_models import RequestParticipant
from mist_service.task_hastener_ports import (
    TaskHastenerEventRecord,
    TaskHastenerRecipientRecord,
    TaskHastenerRequestRecord,
    TaskHastenerWorkspaceRecord,
)
from mist_service.team_models import TeamMembership


class SqlAlchemyTaskHastenerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request_for_team(
        self, team_id: UUID, request_id: UUID
    ) -> TaskHastenerRequestRecord | None:
        request = cast(
            ServiceRequest | None,
            await self.session.scalar(
                select(ServiceRequest)
                .where(
                    ServiceRequest.id == request_id,
                    ServiceRequest.assigned_delivery_team_id == team_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if request is None:
            return None
        return TaskHastenerRequestRecord(
            id=request.id,
            requester_id=request.requester_id,
            status=request.status,
            reference=request.reference,
        )

    async def active_recipients(
        self, team_id: UUID, request_id: UUID
    ) -> list[TaskHastenerRecipientRecord]:
        now = datetime.now(UTC)
        rows = (
            await self.session.execute(
                select(User.id, User.display_name, RequestParticipant.role)
                .join(RequestParticipant, RequestParticipant.user_id == User.id)
                .join(
                    TeamMembership,
                    TeamMembership.user_id == User.id,
                )
                .where(
                    RequestParticipant.request_id == request_id,
                    RequestParticipant.ended_at.is_(None),
                    TeamMembership.team_id == team_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    User.is_active.is_(True),
                )
            )
        ).all()
        unique = {
            user_id: TaskHastenerRecipientRecord(
                user_id=user_id,
                display_name=display_name,
                assignment_role=assignment_role,
            )
            for user_id, display_name, assignment_role in rows
        }
        return sorted(
            unique.values(),
            key=lambda item: (
                0 if item.assignment_role.value == "LEAD" else 1,
                item.display_name.casefold(),
            ),
        )


class SqlAlchemyTaskHastenerWorkspaceReader:
    def __init__(self, session: AsyncSession) -> None:
        self._workspaces = SqlAlchemyTeamWorkspaceRepository(session)

    async def require_read(
        self, actor_id: UUID, team_id: UUID
    ) -> TaskHastenerWorkspaceRecord:
        access = await self._workspaces.require_read(actor_id, team_id)
        return TaskHastenerWorkspaceRecord(
            unit_kind=access.unit_kind,
            workspace_position=access.workspace_position,
        )


class SqlAlchemyTaskHastenerEventWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        request: TaskHastenerRequestRecord,
        actor_id: UUID,
        message: str,
        recipient_ids: list[UUID],
        audience: str,
    ) -> TaskHastenerEventRecord:
        event = await append_request_event(
            self._session,
            request_id=request.id,
            actor_id=actor_id,
            event_type="task_hastener",
            message=message,
            prior_status=request.status,
            next_status=request.status,
            audience=RequestEventAudience.STAFF_ONLY,
            details={
                "audience": audience,
                "recipientCount": len(recipient_ids),
                "recipientUserIds": [str(user_id) for user_id in recipient_ids],
            },
        )
        current = await self._session.get(ServiceRequest, request.id)
        if current is None:
            raise LookupError("request audit anchor is unavailable")
        return TaskHastenerEventRecord(
            id=event.id,
            event_hash=event.event_hash,
            source_version=current.audit_event_count,
            created_at=event.created_at,
        )


class SqlAlchemyTaskHastenerNotifier:
    def __init__(self, session: AsyncSession) -> None:
        self._projection = SqlAlchemyNotificationProjectionRepository(session)

    async def notify(
        self,
        *,
        request: TaskHastenerRequestRecord,
        team_id: UUID,
        event: TaskHastenerEventRecord,
        recipients: list[TaskHastenerRecipientRecord],
    ) -> frozenset[UUID]:
        event_type, subject = render_subject("TASK_HASTENER", request.reference)
        rules = [
            RecipientRule(
                item.user_id,
                NotificationAccessKind.ROUTE_MEMBER,
                UserRole.DELIVERY_SPECIALIST,
                organisation_unit_id=team_id,
            )
            for item in recipients
        ]
        notification = await self._projection.publish_event(
            stable_key=f"request-event:{event.event_hash}",
            event_type=event_type,
            event_group=NotificationEventGroup.ASSIGNMENT,
            source_version=event.source_version,
            request_id=request.id,
            safe_subject=subject,
            deep_link=f"/teams/{team_id}/board?itemId={request.id}",
            audience=[serialise_rule(rule) for rule in rules],
            occurred_at=event.created_at,
        )
        projected = await self._projection.project_event(
            notification.id,
            rules,
            projected_at=event.created_at,
        )
        return frozenset(item.recipient_user_id for item in projected)
