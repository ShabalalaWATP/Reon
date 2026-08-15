"""Independent activation-evidence security branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import mist_service.services.configuration_activation_service as activation_module
from mist_service.config import Environment, Settings
from mist_service.configuration_types import (
    ApprovalDecision,
    ConfigurationStatus,
    FindingSeverity,
)
from mist_service.domain import Actor
from mist_service.errors import InvalidAdministrationChange
from mist_service.models import UserRole
from mist_service.schemas.configuration import ConfigurationReasonCommand
from mist_service.services.configuration_activation_service import (
    ConfigurationActivationService,
)


def _actor(actor_id=None) -> Actor:
    return Actor(
        actor_id or uuid4(),
        "configuration.reviewer@example.test",
        "Configuration Reviewer",
        UserRole.PLATFORM_ADMIN,
        "Platform",
    )


def _bundle(*, creator_id, approval_actor_id, decision, reviewed_version=4):
    return SimpleNamespace(
        version=SimpleNamespace(
            status=ConfigurationStatus.AWAITING_APPROVAL,
            created_by_user_id=creator_id,
            version=5,
        ),
        approval=SimpleNamespace(
            actor_user_id=approval_actor_id,
            decision=decision,
            reviewed_version=reviewed_version,
        ),
    )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("rejected", "rejected version"),
        ("creator_approved", "approval is not independent"),
        ("stale", "approval does not cover"),
    ],
)
def test_activation_rejects_invalid_approval_evidence(case: str, message: str) -> None:
    creator_id = uuid4()
    reviewer = _actor()
    approval_actor_id = reviewer.id
    decision = ApprovalDecision.APPROVED
    reviewed_version = 4
    if case == "rejected":
        decision = ApprovalDecision.REJECTED
    elif case == "creator_approved":
        approval_actor_id = creator_id
    else:
        reviewed_version = 3
    bundle = _bundle(
        creator_id=creator_id,
        approval_actor_id=approval_actor_id,
        decision=decision,
        reviewed_version=reviewed_version,
    )

    with pytest.raises(InvalidAdministrationChange, match=message):
        ConfigurationActivationService._require_activation_authority(reviewer, bundle)


def test_activation_accepts_current_independent_approval() -> None:
    reviewer = _actor()
    ConfigurationActivationService._require_activation_authority(
        reviewer,
        _bundle(
            creator_id=uuid4(),
            approval_actor_id=reviewer.id,
            decision=ApprovalDecision.APPROVED,
        ),
    )


async def test_activation_rejects_fresh_error_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewer = _actor()
    version = SimpleNamespace(
        id=uuid4(),
        effective_from=datetime.now(UTC) - timedelta(minutes=1),
        status=ConfigurationStatus.AWAITING_APPROVAL,
        created_by_user_id=uuid4(),
        version=5,
    )
    bundle = SimpleNamespace(
        version=version,
        approval=SimpleNamespace(
            actor_user_id=reviewer.id,
            decision=ApprovalDecision.APPROVED,
            reviewed_version=4,
        ),
    )
    repository = SimpleNamespace(
        locked_version=AsyncMock(return_value=version),
        bundle=AsyncMock(return_value=bundle),
    )
    findings = AsyncMock(return_value=[SimpleNamespace(severity=FindingSeverity.ERROR)])
    monkeypatch.setattr(activation_module, "configuration_findings", findings)
    service = ConfigurationActivationService(
        repository,
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            configuration_admin_enabled=True,
        ),
    )

    with pytest.raises(InvalidAdministrationChange, match="Validate the current"):
        await service.activate(
            reviewer,
            version.id,
            ConfigurationReasonCommand(
                expected_version=version.version,
                reason="Reject the configuration because validation failed.",
            ),
        )

    findings.assert_awaited_once_with(repository, bundle)
