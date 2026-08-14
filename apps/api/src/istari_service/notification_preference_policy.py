"""Context-bound notification preference policy and suppression query."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationEventGroup,
    NotificationPreference,
)
from istari_service.models import IdentityContext, UserRole

MANDATORY_GROUPS = frozenset(
    {NotificationEventGroup.RELEASE, NotificationEventGroup.ACCOUNT_SECURITY}
)
MANDATORY_EVENT_TYPES = frozenset({"TASK_HASTENER"})


class RecipientContextRule(Protocol):
    @property
    def user_id(self) -> UUID: ...

    @property
    def required_role(self) -> UserRole: ...


def required_context(role: UserRole) -> IdentityContext:
    if role is UserRole.REQUESTER:
        return IdentityContext.CUSTOMER
    return IdentityContext.STAFF


def role_is_current(required_role: UserRole, user: tuple[UserRole, str, bool]) -> bool:
    stored_role, _scope, customer_context_enabled = user
    if required_role is not UserRole.REQUESTER:
        return stored_role is required_role
    return stored_role is UserRole.REQUESTER or (
        stored_role is not UserRole.PLATFORM_ADMIN and customer_context_enabled
    )


async def disabled_recipient_contexts(
    session: AsyncSession,
    rules: Sequence[RecipientContextRule],
    group: NotificationEventGroup,
    event_type: str,
) -> set[tuple[UUID, IdentityContext]]:
    mandatory = group in MANDATORY_GROUPS or event_type in MANDATORY_EVENT_TYPES
    if not rules or mandatory:
        return set()
    user_ids = {rule.user_id for rule in rules}
    contexts = {required_context(rule.required_role) for rule in rules}
    rows = await session.execute(
        select(
            NotificationPreference.user_id,
            NotificationPreference.identity_context,
        ).where(
            NotificationPreference.user_id.in_(user_ids),
            NotificationPreference.event_group == group,
            NotificationPreference.identity_context.in_(contexts),
            NotificationPreference.enabled.is_(False),
        )
    )
    return set(rows.tuples())
