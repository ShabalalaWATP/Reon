"""Stable serialisation for durable notification recipient rules."""

from __future__ import annotations

from uuid import UUID

from istari_service.action_notification_models import NotificationAccessKind
from istari_service.models import UserRole
from istari_service.notification_ports import RecipientRule


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
