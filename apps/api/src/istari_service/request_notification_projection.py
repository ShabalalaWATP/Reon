"""Notification outbox publication and recipient reconciliation for requests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
)
from istari_service.models import (
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
)
from istari_service.notification_catalog import render_subject
from istari_service.organisation_models import UserOrganisationMembership
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.request_action_projection import action_audiences, as_utc


async def publish_request_notification(
    session: AsyncSession, event: RequestEvent, request: ServiceRequest
) -> None:
    notification = notification_spec(event)
    if notification is None:
        return
    event_type, group = notification
    normalised, subject = render_subject(event_type, request.reference)
    rules = await recipient_rules_for(session, normalised, request)
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
        await projection.project_event(event.id, rules, projected_at=current)
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
    return rules


def serialise_rule(rule: RecipientRule) -> dict[str, str | None]:
    return {
        "userId": str(rule.user_id),
        "accessKind": rule.access_kind.value,
        "requiredRole": rule.required_role.value,
        "requiredScope": rule.required_scope,
        "organisationUnitId": (
            str(rule.organisation_unit_id) if rule.organisation_unit_id else None
        ),
    }


def deserialise_rule(value: dict[str, str | None]) -> RecipientRule:
    return RecipientRule(
        user_id=UUID(value["userId"] or ""),
        access_kind=NotificationAccessKind(value["accessKind"] or ""),
        required_role=UserRole(value["requiredRole"] or ""),
        required_scope=value.get("requiredScope"),
        organisation_unit_id=(
            UUID(value["organisationUnitId"])
            if value.get("organisationUnitId")
            else None
        ),
    )


async def _route_rules(
    session: AsyncSession, unit_id: UUID, role: UserRole
) -> list[RecipientRule]:
    users = (
        (
            await session.execute(
                select(User.id, User.scope)
                .join(
                    UserOrganisationMembership,
                    UserOrganisationMembership.user_id == User.id,
                )
                .where(
                    UserOrganisationMembership.unit_id == unit_id,
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


def _direct_rule(request: ServiceRequest, user_id: UUID) -> RecipientRule:
    return (
        _requester_rule(request)
        if user_id == request.requester_id
        else _assignee_rule(request)
    )


def notification_spec(
    event: RequestEvent,
) -> tuple[str, NotificationEventGroup] | None:
    raw = event.type.lower()
    if raw == "request_submitted":
        return "REQUEST_SUBMITTED", NotificationEventGroup.REQUEST_LIFECYCLE
    if raw in {"workflow_withdraw", "product_withdrawn"}:
        return (
            ("PRODUCT_WITHDRAWN", NotificationEventGroup.RELEASE)
            if raw.startswith("product")
            else ("REQUEST_WITHDRAWN", NotificationEventGroup.REQUEST_LIFECYCLE)
        )
    if raw == "workflow_close":
        return "REQUEST_CLOSED", NotificationEventGroup.REQUEST_LIFECYCLE
    if raw == "workflow_hold":
        return "REQUEST_HELD", NotificationEventGroup.REQUEST_LIFECYCLE
    if raw in {"workflow_request_information", "workflow_request_clarification"}:
        return "CLARIFICATION_REQUESTED", NotificationEventGroup.CLARIFICATION
    if raw in {"workflow_provide_information", "workflow_provide_clarification"}:
        return "CLARIFICATION_ANSWERED", NotificationEventGroup.CLARIFICATION
    if raw in {"workflow_submit", "product_package_submitted"}:
        return "MANAGER_REVIEW_REQUESTED", NotificationEventGroup.REVIEW
    if raw == "workflow_approve":
        return (
            ("MANAGER_REVIEW_APPROVED", NotificationEventGroup.REVIEW)
            if event.prior_status is RequestStatus.LEAD_REVIEW
            else ("QC_REVIEW_APPROVED", NotificationEventGroup.REVIEW)
        )
    if raw == "workflow_changes_required":
        return (
            ("MANAGER_REVIEW_RETURNED", NotificationEventGroup.REVIEW)
            if event.prior_status is RequestStatus.LEAD_REVIEW
            else ("QC_REVIEW_RETURNED", NotificationEventGroup.REVIEW)
        )
    if raw in {"workflow_release", "product_disseminated"}:
        return "PRODUCT_DISSEMINATED", NotificationEventGroup.RELEASE
    if raw == "feedback_submitted":
        return "FEEDBACK_RECEIVED", NotificationEventGroup.FEEDBACK
    if raw.startswith("workflow_"):
        return "TASK_ASSIGNED", NotificationEventGroup.ASSIGNMENT
    return None
