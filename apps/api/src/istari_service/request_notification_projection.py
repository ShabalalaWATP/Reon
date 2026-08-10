"""Notification outbox publication and recipient reconciliation for requests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
)
from istari_service.models import (
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
)
from istari_service.notification_catalog import render_subject
from istari_service.notification_event_types import notification_spec
from istari_service.notification_rule_serialisation import (
    deserialise_rule,
    serialise_rule,
)
from istari_service.organisation_models import (
    RequestRouteSelection,
)
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.request_participants import active_participant_ids
from istari_service.request_action_projection import action_audiences, as_utc
from istari_service.team_models import TeamMembership


async def publish_request_notification(
    session: AsyncSession, event: RequestEvent, request: ServiceRequest
) -> None:
    notification = notification_spec(event)
    if notification is None:
        return
    event_type, group = notification
    normalised, subject = render_subject(event_type, request.reference)
    rules = (
        await cancellation_recipient_rules(session, event, request)
        if normalised == "REQUEST_CANCELLED"
        else await recipient_rules_for(session, normalised, request)
    )
    await SqlAlchemyNotificationProjectionRepository(session).publish_event(
        stable_key=f"request-event:{event.event_hash}",
        event_type=normalised,
        event_group=group,
        source_version=request.audit_event_count,
        request_id=request.id,
        safe_subject=subject,
        deep_link=f"/requests/{request.id}",
        audience=[serialise_rule(rule) for rule in rules],
        occurred_at=as_utc(event.created_at),
    )


async def reconcile_pending_notifications(
    session: AsyncSession,
    *,
    limit: int = 100,
    now: datetime | None = None,
) -> int:
    projection = SqlAlchemyNotificationProjectionRepository(session)
    current = now or datetime.now(UTC)
    events = await projection.pending_events(limit=limit, available_at=current)
    for event in events:
        rules = [deserialise_rule(rule) for rule in event.audience]
        await projection.project_event(
            event.id,
            rules,
            projected_at=current,
            update_checkpoint=False,
        )
    if events:
        await projection.update_projection_checkpoint(
            events[-1],
            projected_at=current,
        )
    return len(events)


async def recipient_rules(
    session: AsyncSession, event: NotificationEvent
) -> list[RecipientRule]:
    request = await session.get(ServiceRequest, event.request_id)
    if request is None:
        return []
    return await recipient_rules_for(session, event.event_type, request)


async def recipient_rules_for(
    session: AsyncSession, event_type: str, request: ServiceRequest
) -> list[RecipientRule]:
    if event_type in {
        "REQUEST_WITHDRAWN",
        "REQUEST_CLOSED",
        "PRODUCT_DISSEMINATED",
        "PRODUCT_REPLACED",
        "PRODUCT_WITHDRAWN",
        "FEEDBACK_REQUESTED",
        "FEEDBACK_RECEIVED",
        "CLARIFICATION_REQUESTED",
    }:
        return [_requester_rule(request)]
    if (
        event_type
        in {
            "CLARIFICATION_ANSWERED",
            "MANAGER_REVIEW_RETURNED",
            "QC_REVIEW_RETURNED",
        }
        and request.assigned_specialist_id
    ):
        return [_assignee_rule(request)]
    rules: list[RecipientRule] = []
    for audience in await action_audiences(session, request):
        if audience.recipient_user_id is not None:
            rules.append(_direct_rule(request, audience.recipient_user_id))
        elif audience.organisation_unit_id is not None and audience.candidate_role:
            rules.extend(
                await _route_rules(
                    session, audience.organisation_unit_id, audience.candidate_role
                )
            )
        elif audience.required_scope and audience.candidate_role:
            rules.extend(
                await _scope_rules(
                    session, audience.required_scope, audience.candidate_role
                )
            )
    if event_type in {"TASK_ASSIGNED", "TASK_REASSIGNED", "TASK_RETURNED"}:
        rules.extend(
            _participant_rule(user_id)
            for user_id in await active_participant_ids(session, request.id)
        )
    return rules


async def cancellation_recipient_rules(
    session: AsyncSession,
    event: RequestEvent,
    request: ServiceRequest,
) -> list[RecipientRule]:
    rules = [_requester_rule(request)]
    selections = list(
        (
            await session.execute(
                select(RequestRouteSelection.position, RequestRouteSelection.unit_id)
                .where(RequestRouteSelection.request_id == request.id)
                .order_by(RequestRouteSelection.position)
            )
        ).tuples()
    )
    roles_by_position: dict[int, tuple[UserRole, ...]] = {
        0: (UserRole.INTAKE_TRIAGE,),
        1: (UserRole.SERVICE_COORDINATION,),
        2: (UserRole.OPERATIONS_ALLOCATION,),
        3: (UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST),
    }
    for position, unit_id in selections:
        for role in roles_by_position.get(position, ()):
            rules.extend(await _route_rules(session, unit_id, role))
    if request.assigned_specialist_id is not None:
        rules.append(_assignee_rule(request))
    rules.extend(
        _participant_rule(user_id)
        for user_id in await active_participant_ids(session, request.id)
    )
    if event.prior_status in {
        RequestStatus.QUALITY_REVIEW,
        RequestStatus.READY_FOR_RELEASE,
    }:
        scopes = list(
            await session.scalars(
                select(User.scope)
                .where(
                    User.role == UserRole.QUALITY_RELEASE,
                    User.is_active.is_(True),
                )
                .distinct()
            )
        )
        for scope in scopes:
            rules.extend(await _scope_rules(session, scope, UserRole.QUALITY_RELEASE))
    return rules


async def _route_rules(
    session: AsyncSession, unit_id: UUID, role: UserRole
) -> list[RecipientRule]:
    users = (
        (
            await session.execute(
                select(User.id, User.scope)
                .join(
                    TeamMembership,
                    TeamMembership.user_id == User.id,
                )
                .where(
                    TeamMembership.team_id == unit_id,
                    TeamMembership.effective_from <= datetime.now(UTC),
                    (
                        TeamMembership.effective_until.is_(None)
                        | (TeamMembership.effective_until > datetime.now(UTC))
                    ),
                    User.role == role,
                    User.is_active.is_(True),
                )
            )
        )
        .tuples()
        .all()
    )
    return [
        RecipientRule(
            user_id,
            NotificationAccessKind.ROUTE_MEMBER,
            role,
            required_scope=scope,
            organisation_unit_id=unit_id,
        )
        for user_id, scope in users
    ]


async def _scope_rules(
    session: AsyncSession, scope: str, role: UserRole
) -> list[RecipientRule]:
    user_ids = await session.scalars(
        select(User.id).where(
            User.scope == scope, User.role == role, User.is_active.is_(True)
        )
    )
    return [
        RecipientRule(
            user_id,
            NotificationAccessKind.ROLE_SCOPE,
            role,
            required_scope=scope,
        )
        for user_id in user_ids
    ]


def _requester_rule(request: ServiceRequest) -> RecipientRule:
    return RecipientRule(
        request.requester_id,
        NotificationAccessKind.REQUESTER,
        UserRole.REQUESTER,
    )


def _assignee_rule(request: ServiceRequest) -> RecipientRule:
    if request.assigned_specialist_id is None:
        raise ValueError("an assigned user is required for this notification policy")
    return RecipientRule(
        request.assigned_specialist_id,
        NotificationAccessKind.ASSIGNEE,
        UserRole.DELIVERY_SPECIALIST,
    )


def _participant_rule(user_id: UUID) -> RecipientRule:
    return RecipientRule(
        user_id,
        NotificationAccessKind.ASSIGNEE,
        UserRole.DELIVERY_SPECIALIST,
    )


def _direct_rule(request: ServiceRequest, user_id: UUID) -> RecipientRule:
    return (
        _requester_rule(request)
        if user_id == request.requester_id
        else _assignee_rule(request)
    )
