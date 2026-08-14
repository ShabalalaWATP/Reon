"""Compensation after product storage succeeds but metadata finalisation fails."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from istari_service.product_types import ScanDecision, ScanResult, StoredObject
from istari_service.services.product_content_transfer import ProductContentTransfer
from istari_service.services.product_scan_transfer import ProductScanTransfer
from istari_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)
from product_phase_test_support import CHECKSUM, DATA


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def begin(self):
        return self


def sessions():
    return Session()


def content_operation() -> ContentOperation:
    _actor, package, _request, _artefact, intent, _view = DATA
    return ContentOperation(
        package.id,
        intent.id,
        intent.object_key,
        1,
        intent.expected_size_bytes,
        intent.expected_checksum,
        "token-hash",
        "owner",
        1,
        None,
        1,
    )


def scan_operation() -> ScanOperation:
    _actor, package, _request, artefact, intent, _view = DATA
    return ScanOperation(
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


async def test_content_finalisation_failure_deletes_written_quarantine() -> None:
    actor, _package, _request, _artefact, _intent, _view = DATA
    operation = content_operation()
    phases = SimpleNamespace(
        claim_content=AsyncMock(return_value=operation),
        finalise_content=AsyncMock(side_effect=RuntimeError("database failed")),
    )
    storage = SimpleNamespace(
        write_quarantine=AsyncMock(
            return_value=StoredObject(
                operation.expected_size, "application/pdf", CHECKSUM
            )
        )
    )
    context = SimpleNamespace(
        sessions=sessions,
        fence=AsyncMock(),
        content_phases=lambda _session: phases,
        runtime=SimpleNamespace(
            storage=storage,
            maximum_file_bytes=operation.expected_size,
        ),
        lease_ttl=None,
        release_after_failure=AsyncMock(),
        discard_quarantine=AsyncMock(),
    )
    with pytest.raises(RuntimeError, match="database failed"):
        await ProductContentTransfer(context).upload_content(
            actor,
            operation.package_id,
            operation.intent_id,
            expected_version=operation.expected_version,
            upload_token="token",
            chunks=AsyncMock(),
        )
    context.release_after_failure.assert_awaited_once_with(operation)
    context.discard_quarantine.assert_awaited_once_with(operation.object_key)


async def test_scan_finalisation_failure_deletes_promoted_object() -> None:
    actor, _package, _request, _artefact, _intent, _view = DATA
    operation = scan_operation()
    phases = SimpleNamespace(
        claim_scan=AsyncMock(return_value=operation),
        finalise_scan=AsyncMock(side_effect=RuntimeError("database failed")),
    )
    storage = SimpleNamespace(
        stream_quarantine=lambda _key: AsyncMock(),
        promote=AsyncMock(),
    )
    scanner = SimpleNamespace(
        scan=AsyncMock(return_value=ScanDecision(ScanResult.CLEAN, "test", "1"))
    )
    context = SimpleNamespace(
        sessions=sessions,
        fence=AsyncMock(),
        content_phases=lambda _session: phases,
        runtime=SimpleNamespace(storage=storage, scanner=scanner),
        lease_ttl=None,
        release_after_failure=AsyncMock(),
        discard_released=AsyncMock(),
    )
    with pytest.raises(RuntimeError, match="database failed"):
        await ProductScanTransfer(context).complete_upload(
            actor,
            operation.package_id,
            operation.intent_id,
            SimpleNamespace(),
        )
    released = f"released/{operation.package_id}/{operation.artefact_id}"
    context.discard_released.assert_awaited_once_with(released)
    context.release_after_failure.assert_awaited_once_with(operation)
