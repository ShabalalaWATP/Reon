"""Managed-content idempotency, fencing and scan race boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_types import (
    ScanDecision,
    ScanResult,
    StoredObject,
)
from mist_service.schemas.products import PackageView, VersionCommand
from mist_service.services.product_content_phases import ProductContentPhases
from mist_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)
from product_phase_test_support import (
    CHECKSUM,
    DATA,
    TOKEN,
    repository,
    service,
)


def content_operation(*, uploaded_at: datetime | None = None) -> ContentOperation:
    _actor, package, _request, _artefact, intent, _view = DATA
    return ContentOperation(
        package.id,
        intent.id,
        intent.object_key,
        package.version,
        intent.expected_size_bytes,
        intent.expected_checksum,
        ProductContentPhases._token_hash(TOKEN),
        "owner",
        1,
        uploaded_at,
        package.version,
    )


async def test_content_claim_and_receipt_are_idempotent_but_fail_closed() -> None:
    actor, package, _request, artefact, intent, _view = DATA
    missing = repository(upload_intent=AsyncMock(return_value=None))
    with pytest.raises(ProductNotFound):
        await service(ProductContentPhases, missing).claim_content(
            actor,
            package.id,
            intent.id,
            expected_version=1,
            upload_token=TOKEN,
            lease_ttl=timedelta(minutes=2),
        )

    uploaded_at = datetime.now(UTC)
    uploaded = replace(intent, uploaded_at=uploaded_at)
    retry_repository = repository(
        upload_intent=AsyncMock(return_value=(artefact, uploaded))
    )
    operation = await service(ProductContentPhases, retry_repository).claim_content(
        actor,
        package.id,
        intent.id,
        expected_version=1,
        upload_token=TOKEN,
        lease_ttl=timedelta(minutes=2),
    )
    receipt = ProductContentPhases.receipt_for_existing(
        operation, StoredObject(10, "application/pdf", CHECKSUM)
    )
    assert receipt.uploaded_at == uploaded_at
    with pytest.raises(ProductConflict):
        ProductContentPhases.receipt_for_existing(
            replace(operation, uploaded_at=None),
            StoredObject(10, "application/pdf", CHECKSUM),
        )

    with pytest.raises(ProductNotFound):
        await service(ProductContentPhases, repository()).claim_content(
            actor,
            package.id,
            intent.id,
            expected_version=1,
            upload_token="wrong-token",
            lease_ttl=timedelta(minutes=2),
        )


async def test_content_finalisation_and_release_revalidate_fenced_state() -> None:
    actor, package, _request, _artefact, intent, _view = DATA
    operation = content_operation()
    stored = StoredObject(10, "application/pdf", CHECKSUM)
    missing = repository(upload_intent=AsyncMock(return_value=None))
    with pytest.raises(ProductNotFound):
        await service(ProductContentPhases, missing).finalise_content(
            actor, operation, stored
        )
    stale = repository(package=AsyncMock(return_value=replace(package, version=2)))
    with pytest.raises(ProductConflict):
        await service(ProductContentPhases, stale).finalise_content(
            actor, operation, stored
        )

    phases = service(ProductContentPhases, repository())
    await phases.release_operation(intent.id, None, None)
    await phases.release_operation(intent.id, "owner", 1)
    phases._repository.release_intent_operation.assert_awaited_once()
    with pytest.raises(ProductConflict):
        phases._required_lease(replace(operation, owner=None))


async def test_scan_claim_and_finalisation_fail_closed_after_races() -> None:
    actor, package, _request, artefact, intent, view = DATA
    command = VersionCommand(expectedVersion=1, idempotencyKey=uuid4())
    missing = service(
        ProductContentPhases,
        repository(upload_intent=AsyncMock(return_value=None)),
    )
    with pytest.raises(ProductNotFound):
        await missing.claim_scan(
            actor, package.id, intent.id, command, lease_ttl=timedelta(minutes=2)
        )
    consumed = replace(intent, consumed_at=datetime.now(UTC))
    consumed_repository = repository(
        upload_intent=AsyncMock(return_value=(artefact, consumed)),
        view=AsyncMock(return_value=view),
    )
    assert isinstance(
        await service(ProductContentPhases, consumed_repository).claim_scan(
            actor, package.id, intent.id, command, lease_ttl=timedelta(minutes=2)
        ),
        PackageView,
    )
    with pytest.raises(ProductConflict, match="unavailable"):
        await service(ProductContentPhases, repository()).claim_scan(
            actor, package.id, intent.id, command, lease_ttl=timedelta(minutes=2)
        )

    scan_operation = ScanOperation(
        package.id,
        intent.id,
        artefact.id,
        intent.object_key,
        artefact.filename or "",
        artefact.media_type or "",
        intent.expected_size_bytes,
        intent.expected_checksum,
        1,
        uuid4(),
        "owner",
        1,
    )
    decision = ScanDecision(ScanResult.CLEAN, "synthetic", "1")
    with pytest.raises(ProductNotFound):
        await missing.finalise_scan(actor, scan_operation, decision, "released/key")
    stale = repository(package=AsyncMock(return_value=replace(package, version=2)))
    with pytest.raises(ProductConflict):
        await service(ProductContentPhases, stale).finalise_scan(
            actor, scan_operation, decision, "released/key"
        )
