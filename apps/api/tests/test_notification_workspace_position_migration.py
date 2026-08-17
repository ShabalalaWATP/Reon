"""Schema and durable-rule contract for position-scoped QC notifications."""

from pathlib import Path
from uuid import uuid4

import pytest

from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationRecipient,
)
from mist_service.errors import InvalidAction
from mist_service.models import UserRole
from mist_service.notification_ports import RecipientRule
from mist_service.notification_rule_serialisation import (
    deserialise_rule,
    serialise_rule,
)
from mist_service.services.notification_service import _validate_recipient_rule
from mist_service.team_models import WorkspacePosition

MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0048_notification_workspace_position.py"
)


def test_notification_position_migration_backfills_legacy_qc_recipients() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0048_notification_position"' in source
    assert 'down_revision: str | None = "0047_action_view_contexts"' in source
    assert '"required_workspace_position"' in source
    assert "SET required_workspace_position = 'MANAGER'" in source
    assert 'op.drop_column("notification_recipients"' in source


def test_notification_position_model_and_serialisation_are_nullable() -> None:
    column = NotificationRecipient.__table__.c.required_workspace_position
    assert column.nullable
    rule = RecipientRule(
        uuid4(),
        NotificationAccessKind.ROUTE_MEMBER,
        UserRole.QUALITY_RELEASE,
        organisation_unit_id=uuid4(),
        required_workspace_position=WorkspacePosition.MANAGER,
    )

    assert deserialise_rule(serialise_rule(rule)) == rule


def test_legacy_qc_rule_without_position_remains_manager_only() -> None:
    legacy = {
        "userId": str(uuid4()),
        "accessKind": NotificationAccessKind.ROUTE_MEMBER.value,
        "requiredRole": UserRole.QUALITY_RELEASE.value,
        "requiredScope": None,
        "organisationUnitId": str(uuid4()),
    }

    assert (
        deserialise_rule(legacy).required_workspace_position
        is WorkspacePosition.MANAGER
    )
    explicit_review_rule = {**legacy, "requiredWorkspacePosition": None}
    assert deserialise_rule(explicit_review_rule).required_workspace_position is None


def test_only_qc_manager_can_be_a_position_scoped_notification_recipient() -> None:
    rule = RecipientRule(
        uuid4(),
        NotificationAccessKind.ROUTE_MEMBER,
        UserRole.QUALITY_RELEASE,
        organisation_unit_id=uuid4(),
        required_workspace_position=WorkspacePosition.MEMBER,
    )

    with pytest.raises(InvalidAction):
        _validate_recipient_rule(rule)
