"""Branch coverage for password-assistance policy decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mist_service.domain import Actor
from mist_service.errors import AdministrationAccessDenied, StaleVersion
from mist_service.models import UserRole
from mist_service.platform_security_models import PlatformClassification
from mist_service.schemas.platform_security import PlatformClassificationUpdate
from mist_service.services.platform_security_service import PlatformSecurityService


def repository() -> SimpleNamespace:
    return SimpleNamespace(
        classification=AsyncMock(),
        update_classification=AsyncMock(),
        lock_assistance_budget=AsyncMock(),
        attempt_count=AsyncMock(),
        add_attempt=AsyncMock(),
        prune_attempts=AsyncMock(),
        users_needing_assistance_index=AsyncMock(return_value=[]),
        set_assistance_index=AsyncMock(),
        assistance_index_is_complete=AsyncMock(return_value=True),
        pending_attempt=AsyncMock(return_value=None),
        active_user_by_email_hash=AsyncMock(return_value=None),
        has_recent_user_attempt=AsyncMock(return_value=False),
        match_attempt=AsyncMock(),
        retry_attempt=AsyncMock(),
        complete_attempt=AsyncMock(),
        active_administrator_ids=AsyncMock(return_value=[]),
    )


def publisher() -> SimpleNamespace:
    return SimpleNamespace(publish_password_assistance=AsyncMock())


def actor(role: UserRole) -> Actor:
    return Actor(uuid4(), "synthetic", "Synthetic User", role, "Synthetic")


def test_service_rejects_short_pseudonym_keys() -> None:
    repo = repository()
    with pytest.raises(ValueError, match="at least 32 bytes"):
        PlatformSecurityService(
            repo, repo, repo, repo, publisher(), pseudonym_key=b"short"
        )


@pytest.mark.asyncio
async def test_classification_mutation_checks_role_and_version() -> None:
    repo = repository()
    service = PlatformSecurityService(repo, repo, repo, repo, publisher())
    command = PlatformClassificationUpdate(
        classification=PlatformClassification.LEVEL_THREE,
        expected_version=2,
    )
    with pytest.raises(AdministrationAccessDenied):
        await service.update_classification(actor(UserRole.REQUESTER), command)

    repo.classification.return_value = SimpleNamespace(version=1)
    with pytest.raises(StaleVersion):
        await service.update_classification(actor(UserRole.PLATFORM_ADMIN), command)

    repo.classification.return_value = SimpleNamespace(
        classification=PlatformClassification.LEVEL_THREE,
        version=2,
        updated_at=datetime.now(UTC),
    )
    result = await service.update_classification(
        actor(UserRole.PLATFORM_ADMIN), command
    )
    assert result.classification is PlatformClassification.LEVEL_THREE


@pytest.mark.asyncio
async def test_assistance_budget_enforces_each_limit_and_records_allowed_work() -> None:
    repo = repository()
    service = PlatformSecurityService(
        repo, repo, repo, repo, publisher(), pseudonym_key=b"x" * 32
    )
    now = datetime.now(UTC)

    repo.attempt_count.side_effect = [5, 0]
    assert (
        await service.request_password_assistance(
            "one@example.test", source_key="a", now=now
        )
        is None
    )

    repo.attempt_count.side_effect = [0, 500]
    assert (
        await service.request_password_assistance(
            "two@example.test", source_key="b", now=now
        )
        is None
    )

    attempt_id = uuid4()
    repo.attempt_count.side_effect = [0, 0]
    repo.add_attempt.return_value = attempt_id
    assert (
        await service.request_password_assistance(
            " THREE@example.test ", source_key="c", now=now
        )
        == attempt_id
    )
    repo.add_attempt.assert_awaited_once()
    repo.prune_attempts.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_assistance_handles_indexing_key_rotation_and_empty_queue() -> (
    None
):
    repo = repository()
    service = PlatformSecurityService(
        repo, repo, repo, repo, publisher(), pseudonym_key_id="current"
    )

    repo.assistance_index_is_complete.return_value = False
    assert await service.process_pending_password_assistance() is True

    repo.assistance_index_is_complete.return_value = True
    repo.pending_attempt.return_value = None
    assert await service.process_pending_password_assistance() is False

    attempt = SimpleNamespace(id=uuid4(), email_key_id="old", email_hash="hash")
    repo.pending_attempt.return_value = attempt
    assert await service.process_pending_password_assistance() is True
    repo.retry_attempt.assert_awaited_once()


@pytest.mark.asyncio
async def test_assistance_indexing_updates_every_stale_user() -> None:
    repo = repository()
    first = SimpleNamespace(id=uuid4(), email=" One@example.test ")
    second = SimpleNamespace(id=uuid4(), email="two@example.test")
    repo.users_needing_assistance_index.return_value = [first, second]
    service = PlatformSecurityService(
        repo, repo, repo, repo, publisher(), pseudonym_key_id="current"
    )
    assert await service.reconcile_assistance_email_indexes() is True
    assert repo.set_assistance_index.await_count == 2


@pytest.mark.asyncio
async def test_pending_assistance_completes_matches_and_retries_failures() -> None:
    repo = repository()
    attempt = SimpleNamespace(id=uuid4(), email_key_id="current", email_hash="hash")
    user = SimpleNamespace(id=uuid4())
    repo.pending_attempt.return_value = attempt
    repo.active_user_by_email_hash.return_value = user
    service = PlatformSecurityService(
        repo, repo, repo, repo, publisher(), pseudonym_key_id="current"
    )
    service._publish_password_assistance = AsyncMock()  # type: ignore[method-assign]

    repo.has_recent_user_attempt.return_value = True
    assert await service.process_pending_password_assistance() is True
    repo.match_attempt.assert_awaited_once_with(attempt.id, user.id)
    service._publish_password_assistance.assert_not_awaited()
    repo.complete_attempt.assert_awaited_once()

    repo.complete_attempt.reset_mock()
    repo.has_recent_user_attempt.return_value = False
    await service.process_pending_password_assistance()
    service._publish_password_assistance.assert_awaited_once()
    repo.complete_attempt.assert_awaited_once()

    repo.complete_attempt.reset_mock()
    repo.active_user_by_email_hash.side_effect = RuntimeError("synthetic failure")
    await service.process_pending_password_assistance()
    repo.retry_attempt.assert_awaited()
    repo.complete_attempt.assert_not_awaited()
