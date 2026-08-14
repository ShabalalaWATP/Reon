"""Managed-product preparation and grant-finalisation race boundaries."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from istari_service.product_errors import ProductConflict
from istari_service.product_types import ProductStorageUsage, UploadGrant
from istari_service.services.product_managed_phases import ProductManagedPhases
from istari_service.services.product_transfer_types import ManagedPreparation
from product_phase_test_support import DATA, TOKEN, command, repository, service


async def test_managed_preparation_reuses_only_matching_metadata() -> None:
    actor, package, _request, artefact, intent, _view = DATA
    create = command()
    retry_repository = repository(
        managed_retry=AsyncMock(return_value=(artefact, intent))
    )
    phases = service(ProductManagedPhases, retry_repository)
    plan = await phases.prepare_managed(actor, package.id, create)
    assert plan.object_key == intent.object_key

    mismatches = (
        replace(artefact, filename="different.pdf"),
        replace(artefact, media_type="application/vnd.ms-powerpoint"),
        replace(artefact, size_bytes=11),
        replace(artefact, checksum="b" * 64),
    )
    for mismatch in mismatches:
        with pytest.raises(ProductConflict, match="different upload metadata"):
            phases._require_matching_metadata(
                mismatch, "synthetic.pdf", "application/pdf", create
            )


async def test_managed_preparation_and_finalisation_reject_stale_races() -> None:
    actor, package, _request, artefact, intent, view = DATA
    create = command()
    stale_repository = repository(
        package=AsyncMock(return_value=replace(package, version=2))
    )
    with pytest.raises(ProductConflict):
        await service(ProductManagedPhases, stale_repository).prepare_managed(
            actor, package.id, create
        )

    plan = ManagedPreparation(
        package.id, create, "synthetic.pdf", "application/pdf", intent.object_key
    )
    mismatch_repository = repository(
        managed_retry=AsyncMock(return_value=(artefact, intent))
    )
    with pytest.raises(ProductConflict):
        await service(ProductManagedPhases, mismatch_repository).finalise_managed(
            actor,
            plan,
            UploadGrant("different-key", TOKEN, intent.expires_at),
        )

    success_repository = repository(
        managed_retry=AsyncMock(return_value=(artefact, intent)),
        refresh_upload_grant=AsyncMock(return_value=intent),
        view=AsyncMock(return_value=view),
    )
    result = await service(ProductManagedPhases, success_repository).finalise_managed(
        actor,
        plan,
        UploadGrant(intent.object_key, TOKEN, intent.expires_at),
    )
    assert result.upload_intent.id == intent.id

    final_stale = repository(
        package=AsyncMock(return_value=replace(package, version=2))
    )
    with pytest.raises(ProductConflict):
        await service(ProductManagedPhases, final_stale).finalise_managed(
            actor,
            plan,
            UploadGrant(intent.object_key, TOKEN, intent.expires_at),
        )


async def test_managed_preparation_rejects_package_quota_before_grant() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    quota_repository = repository(
        storage_usage=AsyncMock(
            return_value=ProductStorageUsage(95, 95, 95, 95, 0, 0, 0, 0)
        )
    )
    phases = service(
        ProductManagedPhases,
        quota_repository,
        maximum_package_bytes=100,
    )
    with pytest.raises(ProductConflict, match="package storage limit"):
        await phases.prepare_managed(actor, package.id, command(sizeBytes=10))


async def test_managed_preparation_rejects_active_intent_count_limit() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    quota_repository = repository(
        storage_usage=AsyncMock(
            return_value=ProductStorageUsage(0, 0, 0, 0, 10, 10, 10, 10)
        )
    )
    with pytest.raises(ProductConflict, match="package active-upload limit"):
        await service(ProductManagedPhases, quota_repository).prepare_managed(
            actor, package.id, command(sizeBytes=1)
        )
