"""Exact claimed-task and release-cycle product accountability."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.models import ProductMode, RequestStatus, ServiceRequest
from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
)
from mist_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    PackageStatus,
)
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.schemas.products import ApprovalCommand, DisseminationCommand
from product_test_support import (
    RecordingAudit,
    add_claimed_lead_review_task,
    add_claimed_quality_review_task,
    add_claimed_release_task,
    create_product_request,
    product_actors,
    product_service,
)


async def test_manager_and_releaser_must_own_the_exact_claimed_task(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage = InMemoryPrivateObjectStorage()
    audit = RecordingAudit()
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        row.status = PackageStatus.REVIEW_READY
        row.package_checksum = "a" * 64
        row.version = 2
        request.status = RequestStatus.LEAD_REVIEW
        service = product_service(session, storage, audit)
        approval = ApprovalCommand(
            expected_version=2,
            package_checksum="a" * 64,
            idempotency_key=uuid4(),
        )
        with pytest.raises(ProductNotFound):
            await service.manager_approve(manager, package.id, approval)
        lead_task = await add_claimed_lead_review_task(session, request_id, analyst.id)
        with pytest.raises(ProductNotFound):
            await service.manager_approve(manager, package.id, approval)
        lead_task.assignee_user_id = manager.id
        approved = await service.manager_approve(manager, package.id, approval)

        request.status = RequestStatus.READY_FOR_RELEASE
        release = DisseminationCommand(
            expected_version=approved.version,
            package_checksum="a" * 64,
            external_link_attested=False,
            idempotency_key=uuid4(),
        )
        with pytest.raises(ProductNotFound):
            await service.disseminate(qc, package.id, release)
        release_task = await add_claimed_release_task(session, request_id, manager.id)
        with pytest.raises(ProductNotFound):
            await service.disseminate(qc, package.id, release)
        release_task.assignee_user_id = qc.id
        disseminated = await service.disseminate(qc, package.id, release)
        assert disseminated.disseminated_by == qc.display_name


async def test_stale_approved_package_cannot_be_released_in_a_later_cycle(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        old = await repository.create_package(request_id, analyst.id, uuid4())
        old_row = await session.get(ProductPackage, old.id)
        assert old_row is not None
        old_row.status = PackageStatus.MANAGER_APPROVED
        old_row.package_checksum = "b" * 64
        old_row.manager_approved_by_user_id = manager.id
        old_row.version = 4
        current = await repository.create_package(request_id, analyst.id, uuid4())
        current_row = await session.get(ProductPackage, current.id)
        request = await session.get(ServiceRequest, request_id)
        assert current_row is not None and request is not None
        current_row.status = PackageStatus.MANAGER_APPROVED
        current_row.package_checksum = "c" * 64
        current_row.manager_approved_by_user_id = manager.id
        current_row.version = 4
        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc.id)
        command = DisseminationCommand(
            expected_version=4,
            package_checksum="b" * 64,
            external_link_attested=False,
            idempotency_key=uuid4(),
        )
        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).disseminate(qc, old.id, command)


async def test_legacy_request_cannot_start_a_managed_package(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.product_mode = ProductMode.LEGACY
        repository = SqlAlchemyProductRepository(session)
        with pytest.raises(ProductConflict):
            await repository.create_package(request_id, analyst.id, uuid4())
        package_count = await session.scalar(
            select(func.count())
            .select_from(ProductPackage)
            .where(ProductPackage.request_id == request_id)
        )
        assert package_count == 0
        assert request.product_mode is ProductMode.LEGACY


async def test_customer_product_queries_require_completed_workflow(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        artefact = ProductArtefact(
            package_id=package.id,
            position=1,
            creation_key=uuid4(),
            kind=ArtefactKind.MANAGED_FILE,
            lifecycle=ArtefactLifecycle.RELEASED,
            label="Synthetic release",
            filename="release.pdf",
            media_type="application/pdf",
            size_bytes=20,
            checksum="d" * 64,
            released_key="released/synthetic/release.pdf",
            version=1,
        )
        session.add(artefact)
        await session.flush()
        row.status = PackageStatus.DISSEMINATED
        row.package_checksum = "e" * 64
        row.disseminated_by_user_id = qc.id
        row.disseminated_at = datetime.now(UTC)
        request.status = RequestStatus.READY_FOR_RELEASE
        session.add(
            ProductDissemination(
                package_id=package.id,
                recipient_user_id=requester.id,
                disseminated_by_user_id=qc.id,
                idempotency_key=uuid4(),
                package_checksum="e" * 64,
            )
        )
        await session.flush()
        assert await repository.release_view(request_id, requester.id) is None
        assert await repository.access(artefact.id, requester.id) is None


async def test_exact_lead_and_qc_claimants_can_inspect_external_destination(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    destination = "https://products.example.test/exact-review?token=synthetic"
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        artefact = ProductArtefact(
            package_id=package.id,
            position=1,
            creation_key=uuid4(),
            kind=ArtefactKind.EXTERNAL_LINK,
            lifecycle=ArtefactLifecycle.CLEAN,
            label="Synthetic review link",
            version=1,
        )
        session.add(artefact)
        await session.flush()
        session.add(
            ExternalProductLink(
                artefact_id=artefact.id,
                destination_url=destination,
                normalised_domain="products.example.test",
            )
        )
        row.status = PackageStatus.REVIEW_READY
        request.status = RequestStatus.LEAD_REVIEW
        await add_claimed_lead_review_task(session, request_id, manager.id)
        service = product_service(
            session, InMemoryPrivateObjectStorage(), RecordingAudit()
        )
        lead_view = await service.get_package(manager, package.id)
        assert lead_view.artefacts[0].review_destination_url == destination

        request.status = RequestStatus.QUALITY_REVIEW
        await add_claimed_quality_review_task(session, request_id, qc.id)
        qc_view = await service.get_package(qc, package.id)
        assert qc_view.artefacts[0].review_destination_url == destination

        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc.id)
        release_view = await service.get_package(qc, package.id)
        assert release_view.artefacts[0].review_destination_url == destination
