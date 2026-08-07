"""Customer-release failure paths and fail-closed audit behaviour."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from istari_service.configuration_models import (
    ConfigurationWorkflowTemplate,
)
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.product_errors import (
    ProductConflict,
    ProductDependencyUnavailable,
    ProductNotFound,
)
from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
)
from istari_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from istari_service.product_storage import InMemoryPrivateObjectStorage
from istari_service.product_types import (
    AccessOutcome,
    ArtefactKind,
    ArtefactLifecycle,
    PackageStatus,
)
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.schemas.products import DisseminationCommand, WithdrawalCommand
from istari_service.services.product_service import ProductService
from product_test_support import (
    RecordingAudit,
    create_product_request,
    product_actors,
)


async def _released_package(
    harness: ApiHarness,
    requester_id: UUID,
    analyst_id: UUID,
    qc_id: UUID,
    *,
    approved_link_domains: tuple[str, ...] = ("products.example.test",),
) -> tuple[UUID, UUID, UUID, UUID]:
    request_id = uuid4()
    managed_id, external_id, package_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        session.add(
            ServiceRequest(
                id=request_id,
                reference=f"SR-2026-{request_id.hex[:8].upper()}",
                requester_id=requester_id,
                title="Synthetic released-product request",
                service_category="Research support",
                description="Synthetic release edge coverage.",
                desired_outcome="Safe Customer access.",
                background_context="Synthetic context only.",
                required_by=now.date() + timedelta(days=7),
                required_by_reason="Synthetic date.",
                preferred_deliverable_type="PDF",
                success_criteria="Release controls hold.",
                requesting_business_area="Requesting Area A",
                intended_recipients=["Synthetic Customer"],
                sensitivity="STANDARD",
                handling_instructions="Synthetic only.",
                status=RequestStatus.COMPLETED,
                current_owner="Quality release",
                assigned_delivery_team="Delivery Team A",
                assigned_specialist_id=analyst_id,
                version=8,
            )
        )
        session.add(
            ProductPackage(
                id=package_id,
                request_id=request_id,
                package_version=1,
                creation_key=uuid4(),
                author_user_id=analyst_id,
                status=PackageStatus.DISSEMINATED,
                package_checksum="a" * 64,
                manager_approved_by_user_id=None,
                manager_approved_at=now,
                disseminated_by_user_id=qc_id,
                disseminated_at=now,
                version=7,
            )
        )
        session.add_all(
            [
                ProductArtefact(
                    id=managed_id,
                    package_id=package_id,
                    position=1,
                    creation_key=uuid4(),
                    kind=ArtefactKind.MANAGED_FILE,
                    lifecycle=ArtefactLifecycle.RELEASED,
                    label="Synthetic managed file",
                    filename="report.pdf",
                    media_type="application/pdf",
                    size_bytes=10,
                    checksum="b" * 64,
                    released_key=f"released/{package_id}/{managed_id}",
                    version=4,
                ),
                ProductArtefact(
                    id=external_id,
                    package_id=package_id,
                    position=2,
                    creation_key=uuid4(),
                    kind=ArtefactKind.EXTERNAL_LINK,
                    lifecycle=ArtefactLifecycle.RELEASED,
                    label="Synthetic external link",
                    version=3,
                ),
            ]
        )
        session.add(
            ExternalProductLink(
                artefact_id=external_id,
                destination_url="https://products.example.test/item",
                normalised_domain="products.example.test",
                expires_at=now + timedelta(hours=1),
                qc_attested=True,
            )
        )
        session.add(
            ProductDissemination(
                package_id=package_id,
                recipient_user_id=requester_id,
                disseminated_by_user_id=qc_id,
                idempotency_key=uuid4(),
                package_checksum="a" * 64,
            )
        )
        await session.flush()
        template = await session.scalar(
            select(ConfigurationWorkflowTemplate)
            .order_by(ConfigurationWorkflowTemplate.created_at.desc())
            .limit(1)
        )
        assert template is not None
        template.approved_link_domains = list(approved_link_domains)
        await session.flush()
        await SqlAlchemyConfigurationPinRepository(session).pin_request(request_id)
    return request_id, package_id, managed_id, external_id


def _service(
    session,
    storage: InMemoryPrivateObjectStorage,
    audit: RecordingAudit,
    domains: frozenset[str],
) -> ProductService:
    return ProductService(
        SqlAlchemyProductRepository(session),
        storage,
        SafeDocumentScanner(),
        AllowedHttpsLinkPolicy(domains),
        audit,
    )


async def test_customer_access_failures_are_audited_without_disclosure(
    api_harness: ApiHarness,
) -> None:
    requester, other, _manager, analyst, qc = await product_actors(api_harness)
    request_id, package_id, managed_id, external_id = await _released_package(
        api_harness, requester.id, analyst.id, qc.id
    )
    storage, audit = InMemoryPrivateObjectStorage(), RecordingAudit()
    async with api_harness.sessions() as session:
        service = _service(
            session, storage, audit, frozenset({"products.example.test"})
        )
        with pytest.raises(ProductDependencyUnavailable):
            await service.download(requester, managed_id, "missing-storage")
        with pytest.raises(ProductNotFound):
            await service.download(requester, external_id, "wrong-kind")
        with pytest.raises(ProductNotFound):
            await service.redirect(requester, managed_id, "wrong-kind")
        with pytest.raises(ProductNotFound):
            await service.withdraw(
                requester,
                package_id,
                WithdrawalCommand(
                    expected_version=7,
                    reason="Customer cannot withdraw.",
                    idempotency_key=uuid4(),
                ),
            )
        with pytest.raises(ProductNotFound):
            await service.customer_release(analyst, request_id)
        with pytest.raises(ProductNotFound):
            await service.customer_release(other, request_id)
        with pytest.raises(ProductNotFound):
            await service.download(analyst, managed_id, "wrong-role")
    async with api_harness.sessions() as session:
        denied_policy = _service(session, storage, audit, frozenset())
        with pytest.raises(ProductNotFound):
            await denied_policy.redirect(requester, external_id, "policy-change")
    _pinned_request, _package, _managed, pinned_external = await _released_package(
        api_harness,
        requester.id,
        analyst.id,
        qc.id,
        approved_link_domains=(),
    )
    async with api_harness.sessions() as session:
        service = _service(
            session, storage, audit, frozenset({"products.example.test"})
        )
        with pytest.raises(ProductNotFound):
            await service.redirect(requester, pinned_external, "pinned-policy-change")
    async with api_harness.sessions() as session, session.begin():
        link = await session.scalar(
            select(ExternalProductLink).where(
                ExternalProductLink.artefact_id == external_id
            )
        )
        assert link is not None
        link.normalised_domain = "changed.example.test"
    async with api_harness.sessions() as session:
        service = _service(
            session, storage, audit, frozenset({"products.example.test"})
        )
        with pytest.raises(ProductNotFound):
            await service.redirect(requester, external_id, "domain-change")
    async with api_harness.sessions() as session, session.begin():
        link = await session.scalar(
            select(ExternalProductLink).where(
                ExternalProductLink.artefact_id == external_id
            )
        )
        assert link is not None
        link.normalised_domain = "products.example.test"
        link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    async with api_harness.sessions() as session:
        service = _service(
            session, storage, audit, frozenset({"products.example.test"})
        )
        with pytest.raises(ProductNotFound):
            await service.redirect(requester, external_id, "expired")
    outcomes = {record.outcome for record in audit.records}
    assert {AccessOutcome.DENIED, AccessOutcome.UNAVAILABLE}.issubset(outcomes)


async def test_dissemination_rejects_an_expired_external_link(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage, audit = InMemoryPrivateObjectStorage(), RecordingAudit()
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        await repository.create_external(
            package.id,
            label="Expired after approval",
            destination="https://products.example.test/expired",
            domain="products.example.test",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
            creation_key=uuid4(),
        )
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        row.status = PackageStatus.MANAGER_APPROVED
        row.package_checksum = "c" * 64
        row.manager_approved_by_user_id = manager.id
        row.version = 4
        request.status = RequestStatus.READY_FOR_RELEASE
        service = _service(
            session, storage, audit, frozenset({"products.example.test"})
        )
        with pytest.raises(ProductConflict):
            await service.disseminate(
                qc,
                package.id,
                DisseminationCommand(
                    expected_version=4,
                    package_checksum="c" * 64,
                    external_link_attested=True,
                    idempotency_key=uuid4(),
                ),
            )


async def test_customer_access_requires_exact_unwithdrawn_dissemination_evidence(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, qc = await product_actors(api_harness)
    request_id, package_id, managed_id, _external_id = await _released_package(
        api_harness, requester.id, analyst.id, qc.id
    )
    async with api_harness.sessions() as session, session.begin():
        dissemination = await session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.package_id == package_id
            )
        )
        assert dissemination is not None
        await session.delete(dissemination)
    async with api_harness.sessions() as session:
        repository = SqlAlchemyProductRepository(session)
        assert await repository.release_view(request_id, requester.id) is None
        assert await repository.access(managed_id, requester.id) is None
    async with api_harness.sessions() as session, session.begin():
        session.add(
            ProductDissemination(
                package_id=package_id,
                recipient_user_id=requester.id,
                disseminated_by_user_id=qc.id,
                idempotency_key=uuid4(),
                package_checksum="f" * 64,
            )
        )
    async with api_harness.sessions() as session:
        repository = SqlAlchemyProductRepository(session)
        assert await repository.release_view(request_id, requester.id) is None
        assert await repository.access(managed_id, requester.id) is None

    async with api_harness.sessions() as session, session.begin():
        dissemination = await session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.package_id == package_id
            )
        )
        assert dissemination is not None
        dissemination.package_checksum = "a" * 64
        dissemination.withdrawn_at = datetime.now(UTC)
    async with api_harness.sessions() as session:
        repository = SqlAlchemyProductRepository(session)
        assert await repository.release_view(request_id, requester.id) is None
        assert await repository.access(managed_id, requester.id) is None
