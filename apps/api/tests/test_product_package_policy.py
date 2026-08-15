"""Immutable compatibility rules for legacy and current product drafts."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.product_errors import ProductConflict, ProductValidationFailed
from mist_service.product_models import ProductPackage
from mist_service.product_package_policy import require_supported_policy
from mist_service.schemas.products import (
    ExternalLinkCreate,
    ManagedArtefactCreate,
    PackageCreate,
    SubmitPackageCommand,
)
from product_test_support import (
    RecordingAudit,
    create_product_request,
    product_actors,
    product_service,
)


async def _package(api_harness: ApiHarness, *, legacy: bool):
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    session = api_harness.sessions()
    await session.begin()
    service = product_service(session, InMemoryPrivateObjectStorage(), RecordingAudit())
    package = await service.create_package(
        analyst,
        PackageCreate(
            request_id=request_id,
            expected_version=3,
            idempotency_key=uuid4(),
        ),
    )
    if legacy:
        row = await session.get(ProductPackage, package.id)
        assert row is not None
        row.policy_version = 1
        await session.flush()
    return session, service, analyst, package


async def test_legacy_package_rejects_image_at_intent_boundary(
    api_harness: ApiHarness,
) -> None:
    session, service, analyst, package = await _package(api_harness, legacy=True)
    try:
        content = b"synthetic-png"
        with pytest.raises(ProductValidationFailed, match="pinned policy"):
            await service.add_managed(
                analyst,
                package.id,
                ManagedArtefactCreate(
                    expected_version=1,
                    label="Synthetic image",
                    filename="image.png",
                    media_type="image/png",
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    idempotency_key=uuid4(),
                ),
            )
    finally:
        await session.rollback()
        await session.close()


@pytest.mark.parametrize("legacy", [False, True])
async def test_covering_note_contract_follows_pinned_policy(
    api_harness: ApiHarness, legacy: bool
) -> None:
    session, service, analyst, package = await _package(api_harness, legacy=legacy)
    try:
        linked = await service.add_external(
            analyst,
            package.id,
            ExternalLinkCreate(
                expected_version=1,
                label="Synthetic link",
                url="https://products.example.test/policy",
                idempotency_key=uuid4(),
            ),
        )
        command = SubmitPackageCommand(
            expected_version=linked.version,
            covering_note=None,
            idempotency_key=uuid4(),
        )
        if not legacy:
            with pytest.raises(ProductValidationFailed, match="covering note"):
                await service.submit(analyst, package.id, command)
            return
        submitted = await service.submit(analyst, package.id, command)
        assert submitted.covering_note is None
        assert submitted.policy_version == 1
    finally:
        await session.rollback()
        await session.close()


async def test_new_package_accepts_current_image_type(
    api_harness: ApiHarness,
) -> None:
    session, service, analyst, package = await _package(api_harness, legacy=False)
    try:
        content = b"synthetic-png"
        intent = await service.add_managed(
            analyst,
            package.id,
            ManagedArtefactCreate(
                expected_version=1,
                label="Synthetic image",
                filename="image.png",
                media_type="image/png",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                idempotency_key=uuid4(),
            ),
        )
        assert intent.artefact.media_type == "image/png"
        assert package.policy_version == 2
    finally:
        await session.rollback()
        await session.close()


def test_unknown_package_policy_fails_closed() -> None:
    with pytest.raises(ProductConflict, match="unsupported"):
        require_supported_policy(999)
