"""Immutable review, QC dissemination and Customer-access service journeys."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_models import ProductDissemination
from mist_service.product_types import AccessOutcome, PackageStatus
from mist_service.request_event_models import RequestEvent
from mist_service.schemas.products import (
    ApprovalCommand,
    DisseminationCommand,
    ExternalLinkCreate,
    ManagedArtefactCreate,
    PackageCreate,
    SubmitPackageCommand,
    VersionCommand,
    WithdrawalCommand,
)
from product_test_support import (
    PDF_MEDIA,
    RecordingAudit,
    add_claimed_lead_review_task,
    add_claimed_release_task,
    chunks,
    create_product_request,
    product_actors,
    product_service,
)


async def test_pdf_package_review_release_download_and_withdrawal(
    api_harness: ApiHarness,
) -> None:
    requester, other_customer, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage, audit = InMemoryPrivateObjectStorage(), RecordingAudit()
    package_key, artefact_key = uuid4(), uuid4()
    pdf = b"%PDF-1.7\nSynthetic managed product"
    checksum = hashlib.sha256(pdf).hexdigest()

    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, audit)
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=package_key,
            ),
        )
        assert package.status is PackageStatus.DRAFT
        assert package.version == 1
        assert package.request_reference.startswith("SR-2026-")
        intent = await service.add_managed(
            analyst,
            package.id,
            ManagedArtefactCreate(
                expected_version=1,
                label="Synthetic PDF product",
                filename="synthetic-report.pdf",
                media_type=PDF_MEDIA,
                size_bytes=len(pdf),
                sha256=checksum,
                idempotency_key=artefact_key,
            ),
        )
        assert intent.package.version == 2
        receipt = await service.upload_content(
            analyst,
            package.id,
            intent.upload_intent.id,
            expected_version=2,
            upload_token=intent.upload_intent.upload_token,
            chunks=chunks(pdf[:4], pdf[4:17], pdf[17:]),
        )
        assert receipt.package_version == 3
        repeated_receipt = await service.upload_content(
            analyst,
            package.id,
            intent.upload_intent.id,
            expected_version=2,
            upload_token=intent.upload_intent.upload_token,
            chunks=chunks(b"retry-body-is-not-consumed"),
        )
        assert repeated_receipt.sha256 == receipt.sha256
        completion = VersionCommand(expected_version=3, idempotency_key=uuid4())
        scanned = await service.complete_upload(
            analyst,
            package.id,
            intent.upload_intent.id,
            completion,
        )
        assert scanned.version == 4
        assert scanned.artefacts[0].scan_result.value == "CLEAN"
        repeated_scan = await service.complete_upload(
            analyst, package.id, intent.upload_intent.id, completion
        )
        assert repeated_scan.version == scanned.version
        submitted = await service.submit(
            analyst,
            package.id,
            SubmitPackageCommand(
                expected_version=4,
                idempotency_key=uuid4(),
                covering_note="Synthetic note for the Customer.",
            ),
        )
        assert submitted.status is PackageStatus.REVIEW_READY
        package_checksum = submitted.package_checksum
        assert package_checksum is not None

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.LEAD_REVIEW
        await add_claimed_lead_review_task(session, request_id, manager.id)
        approved = await product_service(session, storage, audit).manager_approve(
            manager,
            package.id,
            ApprovalCommand(
                expected_version=5,
                package_checksum=package_checksum,
                idempotency_key=uuid4(),
            ),
        )
        assert approved.status is PackageStatus.MANAGER_APPROVED
        assert approved.manager_approved_by == manager.display_name

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc.id)
        release_key = uuid4()
        release_command = DisseminationCommand(
            expected_version=6,
            package_checksum=package_checksum,
            external_link_attested=False,
            idempotency_key=release_key,
        )
        released = await product_service(session, storage, audit).disseminate(
            qc,
            package.id,
            release_command,
        )
        assert released.status is PackageStatus.DISSEMINATED
        assert released.artefacts[0].released_at is not None
        repeated = await product_service(session, storage, audit).disseminate(
            qc, package.id, release_command
        )
        assert repeated.version == released.version
        for unauthorised_actor in (requester, manager, analyst):
            with pytest.raises(ProductNotFound):
                await product_service(session, storage, audit).disseminate(
                    unauthorised_actor, package.id, release_command
                )

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.COMPLETED

    async with api_harness.sessions() as session:
        service = product_service(session, storage, audit)
        customer_view = await service.customer_release(requester, request_id)
        assert customer_view.released_by == qc.display_name
        download = await service.download(
            requester, customer_view.artefacts[0].id, "correlation-safe"
        )
        assert b"".join([part async for part in download.chunks]) == pdf
        with pytest.raises(ProductNotFound):
            await service.download(other_customer, customer_view.artefacts[0].id, None)
    assert [record.outcome for record in audit.records] == [
        AccessOutcome.ALLOWED,
        AccessOutcome.DENIED,
    ]

    async with api_harness.sessions() as session, session.begin():
        withdrawn = await product_service(session, storage, audit).withdraw(
            qc,
            package.id,
            WithdrawalCommand(
                expected_version=7,
                reason="The synthetic product is no longer current.",
                idempotency_key=uuid4(),
            ),
        )
        assert withdrawn.status is PackageStatus.WITHDRAWN
        assert withdrawn.withdrawal_reason is not None
        dissemination = await session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.package_id == package.id
            )
        )
        assert dissemination is not None
        assert dissemination.withdrawn_at is not None

    async with api_harness.sessions() as session:
        events = (
            await session.scalars(
                select(RequestEvent.type).where(RequestEvent.request_id == request_id)
            )
        ).all()
    assert {
        "PRODUCT_SUBMITTED",
        "MANAGER_REVIEW_APPROVED",
        "PRODUCT_DISSEMINATED",
        "PRODUCT_WITHDRAWN",
    }.issubset(events)


async def test_external_link_requires_qc_attestation_and_safe_customer_redirect(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage, audit = InMemoryPrivateObjectStorage(), RecordingAudit()

    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, audit)
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        linked = await service.add_external(
            analyst,
            package.id,
            ExternalLinkCreate(
                expected_version=1,
                label="Synthetic external product",
                url="https://products.example.test/item?q=synthetic",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                idempotency_key=uuid4(),
            ),
        )
        submitted = await service.submit(
            analyst,
            package.id,
            SubmitPackageCommand(
                expected_version=2,
                idempotency_key=uuid4(),
                covering_note="Synthetic external product note.",
            ),
        )
        assert linked.artefacts[0].destination_domain == "products.example.test"

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.LEAD_REVIEW
        await add_claimed_lead_review_task(session, request_id, manager.id)
        approved = await product_service(session, storage, audit).manager_approve(
            manager,
            package.id,
            ApprovalCommand(
                expected_version=3,
                package_checksum=submitted.package_checksum or "",
                idempotency_key=uuid4(),
            ),
        )

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc.id)
        service = product_service(session, storage, audit)
        with pytest.raises(ProductNotFound):
            await service.disseminate(
                qc,
                package.id,
                DisseminationCommand(
                    expected_version=4,
                    package_checksum=approved.package_checksum or "",
                    external_link_attested=False,
                    idempotency_key=uuid4(),
                ),
            )
        released = await service.disseminate(
            qc,
            package.id,
            DisseminationCommand(
                expected_version=4,
                package_checksum=approved.package_checksum or "",
                external_link_attested=True,
                idempotency_key=uuid4(),
            ),
        )

    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.COMPLETED

    async with api_harness.sessions() as session:
        destination = await product_service(session, storage, audit).redirect(
            requester, released.artefacts[0].id, None
        )
    assert destination == "https://products.example.test/item?q=synthetic"


async def test_product_package_access_and_version_conflicts_are_non_enumerating(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    rid = request_id
    key = uuid4()
    storage, audit = InMemoryPrivateObjectStorage(), RecordingAudit()
    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, audit)
        with pytest.raises(ProductConflict):
            await service.create_package(
                analyst,
                PackageCreate(request_id=rid, expected_version=2, idempotency_key=key),
            )
        package = await service.create_package(
            analyst,
            PackageCreate(request_id=rid, expected_version=3, idempotency_key=key),
        )
        with pytest.raises(ProductNotFound):
            await service.get_package(requester, package.id)
        with pytest.raises(ProductConflict):
            await service.add_managed(
                analyst,
                package.id,
                ManagedArtefactCreate(
                    expected_version=99,
                    label="Synthetic PDF",
                    filename="report.pdf",
                    media_type=PDF_MEDIA,
                    size_bytes=10,
                    sha256="a" * 64,
                    idempotency_key=uuid4(),
                ),
            )
