"""Framework-free request visibility, ownership and stage policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from istari_service.authorisation import (
    ALLOW,
    PolicyDecision,
    PolicyDenial,
    RequestOperation,
    deny,
)
from istari_service.models import RequestStatus, UserRole


class ActorLike(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def role(self) -> UserRole: ...

    @property
    def scope(self) -> str: ...

    @property
    def organisation_unit_ids(self) -> frozenset[UUID]: ...


class RequestLike(Protocol):
    @property
    def requester_id(self) -> UUID: ...

    @property
    def status(self) -> RequestStatus: ...

    @property
    def assigned_delivery_team(self) -> str | None: ...

    @property
    def assigned_delivery_team_id(self) -> UUID | None: ...

    @property
    def assigned_specialist_id(self) -> UUID | None: ...


class RequestOwnerLike(Protocol):
    @property
    def requester_id(self) -> UUID: ...


ROLE_BY_STAGE: Mapping[RequestStatus, UserRole] = {
    RequestStatus.TRIAGE_REVIEW: UserRole.INTAKE_TRIAGE,
    RequestStatus.INFORMATION_REQUIRED: UserRole.REQUESTER,
    RequestStatus.COORDINATION_REVIEW: UserRole.SERVICE_COORDINATION,
    RequestStatus.ON_HOLD: UserRole.SERVICE_COORDINATION,
    RequestStatus.ALLOCATION_REVIEW: UserRole.OPERATIONS_ALLOCATION,
    RequestStatus.DELIVERY_PLANNING: UserRole.DELIVERY_TEAM_LEAD,
    RequestStatus.IN_PROGRESS: UserRole.DELIVERY_SPECIALIST,
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: UserRole.REQUESTER,
    RequestStatus.LEAD_REVIEW: UserRole.DELIVERY_TEAM_LEAD,
    RequestStatus.REWORK_REQUIRED: UserRole.DELIVERY_SPECIALIST,
    RequestStatus.QUALITY_REVIEW: UserRole.QUALITY_RELEASE,
    RequestStatus.READY_FOR_RELEASE: UserRole.QUALITY_RELEASE,
}


def has_stage_role(actor: ActorLike, request: RequestLike) -> bool:
    """Return whether the actor holds the exact role for the current stage."""
    return ROLE_BY_STAGE.get(request.status) == actor.role


def has_self_request_conflict(actor: ActorLike, request: RequestOwnerLike) -> bool:
    """Prevent a staff context processing the same identity's Customer request."""
    return actor.role is not UserRole.REQUESTER and request.requester_id == actor.id


def is_object_scoped(actor: ActorLike, request: RequestLike) -> bool:
    """Apply ownership, team and assignment restrictions after role matching."""
    if has_self_request_conflict(actor, request):
        return False
    if actor.role == UserRole.REQUESTER:
        return request.requester_id == actor.id
    if actor.role == UserRole.DELIVERY_TEAM_LEAD:
        return (
            request.assigned_delivery_team_id in actor.organisation_unit_ids
            if request.assigned_delivery_team_id is not None
            else request.assigned_delivery_team == actor.scope
        )
    if actor.role == UserRole.DELIVERY_SPECIALIST:
        return actor.id in getattr(request, "participant_ids", frozenset()) or (
            request.assigned_specialist_id == actor.id
        )
    return actor.role in {
        UserRole.INTAKE_TRIAGE,
        UserRole.SERVICE_COORDINATION,
        UserRole.OPERATIONS_ALLOCATION,
        UserRole.QUALITY_RELEASE,
    }


def can_access_work(actor: ActorLike, request: RequestLike) -> bool:
    """Work visibility always requires both role and object scope."""
    return has_stage_role(actor, request) and is_object_scoped(actor, request)


def _request_is_visible(actor: ActorLike, request: RequestLike) -> bool:
    if has_self_request_conflict(actor, request):
        return False
    if actor.role == UserRole.REQUESTER:
        return request.requester_id == actor.id
    if actor.role is UserRole.DELIVERY_SPECIALIST and actor.id in getattr(
        request, "participant_ids", frozenset()
    ):
        return True
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        return (
            request.assigned_delivery_team_id in actor.organisation_unit_ids
            if request.assigned_delivery_team_id is not None
            else request.assigned_delivery_team == actor.scope
        )
    if (
        request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        and actor.role is UserRole.DELIVERY_SPECIALIST
    ):
        return request.assigned_specialist_id == actor.id
    return can_access_work(actor, request)


def decide_request_access(
    actor: ActorLike,
    operation: RequestOperation | str,
    request: RequestLike | None = None,
) -> PolicyDecision:
    """Decide one request operation without exposing the denial category."""
    if operation in {RequestOperation.CREATE, RequestOperation.LIST}:
        return ALLOW if actor.role is UserRole.REQUESTER else deny(PolicyDenial.ROLE)
    if request is None:
        return deny(PolicyDenial.OBJECT_SCOPE)
    if operation is RequestOperation.VIEW:
        return (
            ALLOW
            if _request_is_visible(actor, request)
            else deny(PolicyDenial.OBJECT_SCOPE)
        )
    if operation in {
        RequestOperation.CANCEL,
        RequestOperation.FEEDBACK,
        RequestOperation.DOWNLOAD_PRODUCT,
    }:
        if actor.role is not UserRole.REQUESTER:
            return deny(PolicyDenial.ROLE)
        return (
            ALLOW
            if request.requester_id == actor.id
            else deny(PolicyDenial.OBJECT_SCOPE)
        )
    if not _request_is_visible(actor, request):
        return deny(PolicyDenial.OBJECT_SCOPE)
    if operation is RequestOperation.VIEW_UNRELEASED_PRODUCT:
        return (
            ALLOW if actor.role is not UserRole.REQUESTER else deny(PolicyDenial.ROLE)
        )
    if operation is RequestOperation.VIEW_CLARIFICATIONS:
        return (
            ALLOW
            if actor.role
            in {
                UserRole.REQUESTER,
                UserRole.DELIVERY_SPECIALIST,
                UserRole.DELIVERY_TEAM_LEAD,
            }
            else deny(PolicyDenial.ROLE)
        )
    return deny(PolicyDenial.ACTION)


def can_view_request(actor: ActorLike, request: RequestLike) -> bool:
    """Compatibility predicate derived from the typed request policy."""
    return decide_request_access(actor, RequestOperation.VIEW, request).allowed
