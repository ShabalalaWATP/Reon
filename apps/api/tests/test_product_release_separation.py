"""Separation of QC review and managed-product dissemination."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.domain import Actor
from mist_service.models import (
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.product_errors import ProductNotFound
from mist_service.product_models import ProductPackage
from mist_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from mist_service.product_types import PackageStatus
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.schemas.products import DisseminationCommand
from mist_service.services.product_service import ProductService
from product_test_support import (
    RecordingAudit,
    add_claimed_release_task,
    create_product_request,
    product_actors,
)


async def test_dissemination_excludes_prior_product_decision_makers(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        row.status = PackageStatus.MANAGER_APPROVED
        row.package_checksum = "d" * 64
        row.manager_approved_by_user_id = manager.id
        row.version = 4
        request.status = RequestStatus.READY_FOR_RELEASE
        instance = WorkflowInstance(
            request_id=request_id,
            process_id="service-request-v1",
            process_instance_key=f"test-{uuid4()}",
            status=WorkflowInstanceStatus.ACTIVE,
        )
        session.add(instance)
        await session.flush()
        session.add(
            WorkflowTask(
                request_id=request_id,
                workflow_instance_id=instance.id,
                task_key=f"quality-{uuid4()}",
                element_id="quality_review",
                name="QC Review",
                candidate_role=UserRole.QUALITY_RELEASE,
                expected_status=RequestStatus.QUALITY_REVIEW,
                status=WorkflowTaskStatus.COMPLETED,
                assignee_user_id=qc.id,
                completed_at=datetime.now(UTC),
            )
        )
        await session.flush()
        await add_claimed_release_task(session, request_id, qc.id)
        service = ProductService(
            repository,
            InMemoryPrivateObjectStorage(),
            SafeDocumentScanner(),
            AllowedHttpsLinkPolicy(frozenset({"products.example.test"})),
            RecordingAudit(),
        )
        command = DisseminationCommand(
            expected_version=4,
            package_checksum="d" * 64,
            external_link_attested=False,
            idempotency_key=uuid4(),
        )
        for identity in (analyst, manager, qc):
            active_qc_context = Actor(
                identity.id,
                identity.username,
                identity.display_name,
                UserRole.QUALITY_RELEASE,
                "Combined QC Team",
            )
            with pytest.raises(ProductNotFound):
                await service.disseminate(active_qc_context, package.id, command)
