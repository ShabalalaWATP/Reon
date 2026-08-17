"""Live exact-team authorisation for QC product and workflow boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from mist_service.models import RequestStatus, ServiceRequest, User, WorkflowInstance
from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_models import ProductPackage
from mist_service.product_types import PackageStatus
from mist_service.qc_membership import QC_TEAM_ID
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.repositories.requests import SqlAlchemyRequestRepository
from mist_service.repositories.work import SqlAlchemyWorkRepository
from mist_service.schemas.products import (
    ApprovalCommand,
    DisseminationCommand,
    ExternalLinkCreate,
)
from mist_service.team_models import TeamMembership, WorkspacePosition
from product_test_support import (
    RecordingAudit,
    add_claimed_lead_review_task,
    add_claimed_release_task,
    create_product_request,
    product_actors,
    product_service,
)


async def test_wrong_team_qc_role_cannot_read_managed_product(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    ssg_team_id = await api_harness.unit_id("SSG_TEAM")
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.QUALITY_REVIEW
        assert await product_service(
            session, InMemoryPrivateObjectStorage(), RecordingAudit()
        ).get_package(qc, package.id)
        membership = await _qc_membership(session, qc.id)
        await session.delete(membership)
        session.add(
            TeamMembership(
                user_id=qc.id,
                team_id=ssg_team_id,
                workspace_position=WorkspacePosition.MANAGER,
                effective_from=datetime.now(UTC) - timedelta(days=1),
                start_reason="Synthetic wrong-team security regression.",
            )
        )
        await session.flush()

        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).get_package(qc, package.id)


async def test_expired_qc_membership_blocks_exact_claimed_release(
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
        row.package_checksum = "a" * 64
        row.manager_approved_by_user_id = manager.id
        row.version = 2
        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc.id)
        membership = await _qc_membership(session, qc.id)
        membership.effective_from = datetime.now(UTC) - timedelta(days=2)
        membership.effective_until = datetime.now(UTC) - timedelta(days=1)
        await session.flush()

        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).disseminate(
                qc,
                package.id,
                DisseminationCommand(
                    expected_version=2,
                    package_checksum="a" * 64,
                    external_link_attested=False,
                    idempotency_key=uuid4(),
                ),
            )


async def test_expired_delivery_membership_blocks_stale_analyst_mutation(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        membership = await _delivery_membership(session, analyst.id)
        membership.effective_from = datetime.now(UTC) - timedelta(days=1)
        membership.effective_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.flush()

        service = product_service(
            session, InMemoryPrivateObjectStorage(), RecordingAudit()
        )
        with pytest.raises(ProductNotFound):
            await service.get_package(analyst, package.id)
        with pytest.raises(ProductConflict):
            await service.add_external(
                analyst,
                package.id,
                ExternalLinkCreate(
                    expected_version=1,
                    label="Synthetic blocked product",
                    url="https://products.example.test/blocked",
                    idempotency_key=uuid4(),
                ),
            )


async def test_manager_position_downgrade_blocks_claimed_approval(
    api_harness: ApiHarness,
) -> None:
    requester, _other, manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        row = await session.get(ProductPackage, package.id)
        request = await session.get(ServiceRequest, request_id)
        assert row is not None and request is not None
        row.status = PackageStatus.REVIEW_READY
        row.package_checksum = "b" * 64
        request.status = RequestStatus.LEAD_REVIEW
        await add_claimed_lead_review_task(session, request_id, manager.id)
        membership = await _delivery_membership(session, manager.id)
        membership.workspace_position = WorkspacePosition.MEMBER
        await session.flush()

        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).manager_approve(
                manager,
                package.id,
                ApprovalCommand(
                    expected_version=1,
                    package_checksum="b" * 64,
                    idempotency_key=uuid4(),
                ),
            )


async def test_removed_qc_membership_hides_claimed_work_from_stale_actor(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        user = await session.get(User, qc.id)
        assert request is not None and user is not None
        request.status = RequestStatus.READY_FOR_RELEASE
        task = await add_claimed_release_task(session, request_id, qc.id)
        instance = await session.get(WorkflowInstance, task.workflow_instance_id)
        assert instance is not None
        instance.current_element_id = task.element_id
        stale_actor = await actor_from_user_with_memberships(session, user)
        assert QC_TEAM_ID in stale_actor.organisation_unit_ids
        requests = SqlAlchemyRequestRepository(session, process_id="service-request-v1")
        assert await requests.get_record_for_actor(request_id, stale_actor) is not None
        await session.delete(await _qc_membership(session, qc.id))
        await session.flush()

        items = await SqlAlchemyWorkRepository(
            session, managed_products_enabled=True
        ).list_for_actor(stale_actor)

        assert items == []
        assert await requests.get_record_for_actor(request_id, stale_actor) is None


async def test_qc_notifications_recheck_membership_before_projection_and_read(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.READY_FOR_RELEASE
        task = await add_claimed_release_task(session, request_id, qc.id)
        instance = await session.get(WorkflowInstance, task.workflow_instance_id)
        assert instance is not None
        instance.current_element_id = task.element_id
        projection = SqlAlchemyNotificationProjectionRepository(session)
        reads = SqlAlchemyNotificationRepository(session)
        rule = RecipientRule(
            qc.id,
            NotificationAccessKind.ROLE_SCOPE,
            qc.role,
            required_scope=qc.scope,
        )
        visible_event = await projection.publish_event(
            stable_key=f"qc-visible:{request_id}",
            event_type="TASK_ASSIGNED",
            event_group=NotificationEventGroup.ASSIGNMENT,
            source_version=1,
            request_id=request_id,
            safe_subject="A synthetic QC task is ready.",
            deep_link=f"/requests/{request_id}",
            audience=[],
            occurred_at=now,
        )
        assert (
            len(
                await projection.project_event(
                    visible_event.id, [rule], projected_at=now
                )
            )
            == 1
        )
        visible, _cursor = await reads.list_notifications(
            qc,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=20,
            cursor=None,
        )
        assert len(visible) == 1

        membership = await _qc_membership(session, qc.id)
        membership.effective_from = now - timedelta(days=2)
        membership.effective_until = now - timedelta(days=1)
        await session.flush()
        items, _cursor = await reads.list_notifications(
            qc,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=20,
            cursor=None,
        )
        assert items == []

        expired_event = await projection.publish_event(
            stable_key=f"qc-expired:{request_id}",
            event_type="TASK_ASSIGNED",
            event_group=NotificationEventGroup.ASSIGNMENT,
            source_version=2,
            request_id=request_id,
            safe_subject="An expired QC membership must not receive this task.",
            deep_link=f"/requests/{request_id}",
            audience=[],
            occurred_at=now,
        )
        assert (
            await projection.project_event(expired_event.id, [rule], projected_at=now)
            == []
        )


async def _qc_membership(session: AsyncSession, user_id: UUID) -> TeamMembership:
    membership = await session.scalar(
        select(TeamMembership).where(
            TeamMembership.user_id == user_id,
            TeamMembership.team_id == QC_TEAM_ID,
            TeamMembership.effective_until.is_(None),
        )
    )
    assert membership is not None
    return membership


async def _delivery_membership(session: AsyncSession, user_id: UUID) -> TeamMembership:
    membership = await session.scalar(
        select(TeamMembership).where(
            TeamMembership.user_id == user_id,
            TeamMembership.effective_until.is_(None),
        )
    )
    assert membership is not None
    return membership
