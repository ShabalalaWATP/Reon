"""Legacy transaction-scoped upload validation and scan error boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mist_service.product_errors import (
    ProductConflict,
    ProductNotFound,
    ProductValidationFailed,
)
from mist_service.product_types import ScanDecision, ScanResult, StoredObject
from mist_service.schemas.products import VersionCommand
from mist_service.services.product_upload_service import ProductUploadOperations
from product_phase_test_support import CHECKSUM, DATA, TOKEN, command, repository


async def chunks() -> AsyncIterator[bytes]:
    yield b"synthetic"


def operations(
    repository_value: object,
    *,
    storage: object | None = None,
    scanner: object | None = None,
    maximum_file_bytes: int = 50,
) -> ProductUploadOperations:
    placeholder = cast(Any, object())
    return ProductUploadOperations(
        cast(Any, repository_value),
        cast(Any, storage or SimpleNamespace()),
        cast(Any, scanner or SimpleNamespace()),
        placeholder,
        maximum_file_bytes=maximum_file_bytes,
    )


async def test_managed_upload_rejects_the_configured_size_limit() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    with pytest.raises(ProductValidationFailed, match="configured limit"):
        await operations(repository(), maximum_file_bytes=5).add_managed(
            actor, package.id, command()
        )


async def test_upload_content_handles_missing_invalid_and_mismatched_intents() -> None:
    actor, package, _request, _artefact, intent, _view = DATA
    missing = operations(repository(upload_intent=AsyncMock(return_value=None)))
    with pytest.raises(ProductNotFound):
        await missing.upload_content(
            actor,
            package.id,
            intent.id,
            expected_version=1,
            upload_token=TOKEN,
            chunks=chunks(),
        )

    with pytest.raises(ProductNotFound):
        await operations(repository()).upload_content(
            actor,
            package.id,
            intent.id,
            expected_version=1,
            upload_token="wrong-token",
            chunks=chunks(),
        )

    storage = SimpleNamespace(
        write_quarantine=AsyncMock(
            return_value=StoredObject(9, "application/pdf", CHECKSUM)
        ),
        delete_quarantine=AsyncMock(),
    )
    with pytest.raises(ProductValidationFailed, match="do not match"):
        await operations(repository(), storage=storage).upload_content(
            actor,
            package.id,
            intent.id,
            expected_version=1,
            upload_token=TOKEN,
            chunks=chunks(),
        )
    storage.delete_quarantine.assert_awaited_once_with(intent.object_key)


async def test_complete_upload_revalidates_every_mutable_boundary() -> None:
    actor, package, _request, artefact, intent, _view = DATA
    command_value = VersionCommand(expectedVersion=1, idempotencyKey=uuid4())
    missing = operations(repository(upload_intent=AsyncMock(return_value=None)))
    with pytest.raises(ProductNotFound):
        await missing.complete_upload(actor, package.id, intent.id, command_value)

    uploaded = replace(intent, uploaded_at=datetime.now(UTC))
    stale = operations(
        repository(
            package=AsyncMock(return_value=replace(package, version=2)),
            upload_intent=AsyncMock(return_value=(artefact, uploaded)),
        )
    )
    with pytest.raises(ProductConflict):
        await stale.complete_upload(actor, package.id, intent.id, command_value)

    with pytest.raises(ProductConflict, match="unavailable"):
        await operations(repository()).complete_upload(
            actor, package.id, intent.id, command_value
        )

    missing_metadata = operations(
        repository(
            upload_intent=AsyncMock(
                return_value=(replace(artefact, filename=None), uploaded)
            )
        )
    )
    with pytest.raises(ProductConflict):
        await missing_metadata.complete_upload(
            actor, package.id, intent.id, command_value
        )


async def test_non_clean_scan_records_failure_without_promoting_bytes() -> None:
    actor, package, _request, artefact, intent, view = DATA
    uploaded = replace(intent, uploaded_at=datetime.now(UTC))
    repository_value = repository(
        upload_intent=AsyncMock(return_value=(artefact, uploaded)),
        view=AsyncMock(return_value=view),
    )
    storage = SimpleNamespace(
        stream_quarantine=lambda _object_key: chunks(),
        promote=AsyncMock(),
    )
    scanner = SimpleNamespace(
        scan=AsyncMock(
            return_value=ScanDecision(
                ScanResult.FAILED,
                "synthetic-scanner",
                "1",
                "SYNTHETIC_REJECTION",
            )
        )
    )
    result = await operations(
        repository_value, storage=storage, scanner=scanner
    ).complete_upload(
        actor,
        package.id,
        intent.id,
        VersionCommand(expectedVersion=1, idempotencyKey=uuid4()),
    )
    assert result.id == package.id
    storage.promote.assert_not_awaited()
    repository_value.record_scan.assert_awaited_once()
