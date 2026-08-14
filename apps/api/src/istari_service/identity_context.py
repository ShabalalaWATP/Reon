"""Central identity-context predicates for current-account validation."""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, or_

from istari_service.domain import Actor
from istari_service.models import IdentityContext, User, UserRole


def actor_identity_context(actor: Actor) -> IdentityContext:
    """Return the bounded context represented by an effective actor."""

    if actor.role is UserRole.REQUESTER:
        return IdentityContext.CUSTOMER
    return IdentityContext.STAFF


def require_staff_context(actor: Actor, error: Exception) -> None:
    """Reject effective Customer actors before consulting staff identity grants."""

    if actor.role is UserRole.REQUESTER:
        raise error


def active_actor_condition(actor: Actor) -> ColumnElement[bool]:
    """Match an effective actor to its active underlying account."""

    identity = and_(User.role == actor.role, User.scope == actor.scope)
    if actor.role is UserRole.REQUESTER:
        identity = or_(
            User.role == UserRole.REQUESTER,
            and_(
                User.role != UserRole.PLATFORM_ADMIN,
                User.customer_context_enabled.is_(True),
            ),
        )
    return and_(User.id == actor.id, User.is_active.is_(True), identity)


def customer_context_entitlement() -> ColumnElement[bool]:
    """Match stable accounts permitted to act through Customer context."""

    return or_(
        User.role == UserRole.REQUESTER,
        and_(
            User.role != UserRole.PLATFORM_ADMIN,
            User.customer_context_enabled.is_(True),
        ),
    )


def user_matches_actor(user: User, actor: Actor) -> bool:
    if user.id != actor.id or not user.is_active:
        return False
    if actor.role is UserRole.REQUESTER:
        return user.role is UserRole.REQUESTER or (
            user.role is not UserRole.PLATFORM_ADMIN and user.customer_context_enabled
        )
    return user.role is actor.role and user.scope == actor.scope
