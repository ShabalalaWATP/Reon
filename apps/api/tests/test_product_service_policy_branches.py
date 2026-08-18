"""Focused package submission and authorisation boundary branches."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mist_service.models import UserRole
from mist_service.product_errors import (
    ProductConflict,
    ProductNotFound,
    ProductValidationFailed,
)
from mist_service.product_types import ReleaseAccessRecord
from mist_service.schemas.products import (
    AcceptanceCommand,
    PackageCreate,
    SubmitPackageCommand,
)
from mist_service.services.product_service import ProductService
from product_phase_test_support import DATA, repository
from product_test_support import product_service_repositories


def _service(
    repository_value: object,
    *,
    maximum_package_bytes: int = 100,
    audit: object | None = None,
) -> ProductService:
    placeholder = SimpleNamespace()
    return ProductService(
        product_service_repositories(repository_value),
        placeholder,
        placeholder,
        placeholder,
        audit or placeholder,
        maximum_package_bytes=maximum_package_bytes,
    )


async def test_submit_rejects_a_clean_manifest_over_the_package_limit() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    repository_value = repository(
        package_digest=AsyncMock(return_value=("a" * 64, 1, 10)),
        freeze=AsyncMock(),
    )
    with pytest.raises(ProductValidationFailed, match="configured limit"):
        await _service(repository_value, maximum_package_bytes=5).submit(
            actor,
            package.id,
            SubmitPackageCommand(
                expected_version=1,
                idempotency_key=uuid4(),
                covering_note="Synthetic Customer note.",
            ),
        )
    repository_value.freeze.assert_not_awaited()


async def test_package_creation_conceals_an_unknown_request() -> None:
    actor, _package, request, _artefact, _intent, _view = DATA
    service = _service(repository(request=AsyncMock(return_value=None)))
    with pytest.raises(ProductNotFound):
        await service.create_package(
            actor,
            PackageCreate(
                request_id=request.id,
                expected_version=request.version,
                idempotency_key=uuid4(),
            ),
        )


async def test_stale_package_version_is_rejected_before_digest() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    repository_value = repository(package_digest=AsyncMock())
    with pytest.raises(ProductConflict):
        await _service(repository_value).submit(
            actor,
            package.id,
            SubmitPackageCommand(
                expected_version=2,
                idempotency_key=uuid4(),
                covering_note="Synthetic Customer note.",
            ),
        )
    repository_value.package_digest.assert_not_awaited()


async def test_missing_request_conceals_an_existing_package() -> None:
    actor, package, _request, _artefact, _intent, _view = DATA
    service = _service(repository(request=AsyncMock(return_value=None)))
    with pytest.raises(ProductNotFound):
        await service.packages._authorised_package(actor, package.id, lock=False)


async def test_non_file_staff_review_is_audited_as_unavailable() -> None:
    actor, package, request, artefact, _intent, _view = DATA
    unavailable = replace(artefact, released_key=None)
    access = ReleaseAccessRecord(request.id, package.id, unavailable)
    audit = SimpleNamespace(record=AsyncMock())
    repository_value = repository(review_access=AsyncMock(return_value=access))
    with pytest.raises(ProductNotFound):
        await _service(repository_value, audit=audit).authorise_review(
            actor, artefact.id, "synthetic-correlation"
        )
    assert audit.record.await_args.args[0].reason_code == "STAFF_REVIEW_UNAVAILABLE"


async def test_customer_release_and_acceptance_fail_if_projection_disappears() -> None:
    actor, _package, request, _artefact, _intent, _view = DATA
    customer = replace(actor, role=UserRole.REQUESTER, scope="Customer")
    customer_request = replace(request, requester_id=customer.id)
    no_release = repository(
        request=AsyncMock(return_value=customer_request),
        release_view=AsyncMock(return_value=None),
    )
    with pytest.raises(ProductNotFound):
        await _service(no_release).customer_release(customer, request.id)

    package_id = uuid4()
    disappearing = repository(
        release_view=AsyncMock(
            side_effect=[SimpleNamespace(package_id=package_id), None]
        ),
        accept=AsyncMock(),
    )
    with pytest.raises(ProductNotFound):
        await _service(disappearing).accept_product(
            customer,
            request.id,
            AcceptanceCommand(idempotency_key=uuid4()),
        )
    disappearing.accept.assert_awaited_once()


async def test_authorised_download_rechecks_required_storage_metadata() -> None:
    actor, package, request, artefact, _intent, _view = DATA
    access = ReleaseAccessRecord(
        request.id, package.id, replace(artefact, released_key=None)
    )
    with pytest.raises(ProductNotFound):
        await _service(repository()).download_authorised(actor, access, None)
