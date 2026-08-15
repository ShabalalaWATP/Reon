"""Shared managed-product service fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.configuration_digest import configuration_digest
from mist_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationRegistry,
    ConfigurationWorkflowTemplate,
)
from mist_service.domain import Actor
from mist_service.models import (
    ProductMode,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from mist_service.product_types import AccessAuditRecord
from mist_service.repositories.auth import actor_from_user
from mist_service.repositories.configuration import SqlAlchemyConfigurationRepository
from mist_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.repositories.request_route_initialisation import (
    initialise_request_route,
)
from mist_service.services.product_service import ProductService

PDF_MEDIA = "application/pdf"


class RecordingAudit:
    def __init__(self) -> None:
        self.records: list[AccessAuditRecord] = []

    async def record(self, record: AccessAuditRecord) -> None:
        self.records.append(record)


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def product_actors(
    harness: ApiHarness,
) -> tuple[Actor, Actor, Actor, Actor, Actor]:
    async with harness.sessions() as session:
        users = (
            await session.scalars(
                select(User).where(
                    User.username.in_(
                        {"admin2", "admin3", "admin8", "admin11", "admin15"}
                    )
                )
            )
        ).all()
    by_name = {user.username: actor_from_user(user) for user in users}
    return (
        by_name["admin2"],
        by_name["admin3"],
        by_name["admin8"],
        by_name["admin11"],
        by_name["admin15"],
    )


async def create_product_request(
    harness: ApiHarness,
    requester: Actor,
    analyst: Actor,
    *,
    approved_link_domains: tuple[str, ...] = ("products.example.test",),
) -> UUID:
    request_id = uuid4()
    async with harness.sessions() as session, session.begin():
        session.add(
            ServiceRequest(
                id=request_id,
                reference=f"SR-2026-{request_id.hex[:8].upper()}",
                requester_id=requester.id,
                title="Synthetic managed product request",
                service_category="Research support",
                description="A synthetic description for product testing.",
                question_to_answer="What does the synthetic evidence show?",
                desired_outcome="A safe managed product.",
                background_context="Synthetic context only.",
                subject_area_or_location="Synthetic subject area",
                coverage_start=datetime.now(UTC).date(),
                coverage_end=datetime.now(UTC).date() + timedelta(days=1),
                customer_urgency="ROUTINE",
                supported_activity_or_decision="A fictional planning decision.",
                required_by=datetime.now(UTC).date() + timedelta(days=7),
                required_by_reason="Synthetic review date.",
                preferred_deliverable_type="PDF",
                product_mode=ProductMode.MANAGED,
                success_criteria="The synthetic product passes review.",
                constraints_or_caveats="No known constraints.",
                supporting_information="No supporting material is available.",
                sensitivity="STANDARD",
                handling_instructions="Synthetic handling only.",
                status=RequestStatus.IN_PROGRESS,
                current_owner=analyst.display_name,
                assigned_delivery_team=analyst.scope,
                assigned_specialist_id=analyst.id,
                version=3,
            )
        )
        await session.flush()
        await initialise_request_route(session, request_id)
        await set_synthetic_active_link_domains(session, approved_link_domains)
        await SqlAlchemyConfigurationPinRepository(session).pin_request(request_id)
    return request_id


async def add_claimed_release_task(
    session: AsyncSession, request_id: UUID, assignee_id: UUID
) -> WorkflowTask:
    return await _add_claimed_task(
        session,
        request_id,
        assignee_id,
        element_id="release",
        expected_status=RequestStatus.READY_FOR_RELEASE,
        name="Release product",
        key_prefix="release",
        candidate_role=UserRole.QUALITY_RELEASE,
    )


async def add_claimed_quality_review_task(
    session: AsyncSession, request_id: UUID, assignee_id: UUID
) -> WorkflowTask:
    return await _add_claimed_task(
        session,
        request_id,
        assignee_id,
        element_id="quality_review",
        expected_status=RequestStatus.QUALITY_REVIEW,
        name="Quality review",
        key_prefix="quality",
        candidate_role=UserRole.QUALITY_RELEASE,
    )


async def add_claimed_lead_review_task(
    session: AsyncSession, request_id: UUID, assignee_id: UUID
) -> WorkflowTask:
    return await _add_claimed_task(
        session,
        request_id,
        assignee_id,
        element_id="lead_review",
        expected_status=RequestStatus.LEAD_REVIEW,
        name="Lead review",
        key_prefix="lead",
        candidate_role=UserRole.DELIVERY_TEAM_LEAD,
    )


async def seed_claimed_lead_review_task(
    harness: ApiHarness, request_id: UUID, username: str
) -> None:
    async with harness.sessions() as session, session.begin():
        await add_claimed_lead_review_task(
            session, request_id, await harness.user_id(username)
        )


async def seed_claimed_release_task(
    harness: ApiHarness, request_id: UUID, username: str
) -> None:
    async with harness.sessions() as session, session.begin():
        await add_claimed_release_task(
            session, request_id, await harness.user_id(username)
        )


async def _add_claimed_task(
    session: AsyncSession,
    request_id: UUID,
    assignee_id: UUID,
    *,
    element_id: str,
    expected_status: RequestStatus,
    name: str,
    key_prefix: str,
    candidate_role: UserRole,
) -> WorkflowTask:
    instance = await session.scalar(
        select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
    )
    if instance is None:
        instance = WorkflowInstance(
            request_id=request_id,
            process_id="service-request-v1",
            process_instance_key=f"{key_prefix}-{uuid4()}",
            status=WorkflowInstanceStatus.ACTIVE,
        )
        session.add(instance)
        await session.flush()
    task = WorkflowTask(
        request_id=request_id,
        workflow_instance_id=instance.id,
        task_key=f"{key_prefix}-{uuid4()}",
        element_id=element_id,
        name=name,
        candidate_role=candidate_role,
        expected_status=expected_status,
        status=WorkflowTaskStatus.CLAIMED,
        assignee_user_id=assignee_id,
        claimed_at=datetime.now(UTC),
    )
    session.add(task)
    await session.flush()
    return task


async def set_synthetic_active_link_domains(
    session: AsyncSession,
    domains: tuple[str, ...],
) -> None:
    """Reseal the isolated SQLite fixture after a product-policy variation."""

    registry = await session.get(ConfigurationRegistry, 1)
    assert registry is not None and registry.active_version_id is not None
    template = await session.scalar(
        select(ConfigurationWorkflowTemplate).where(
            ConfigurationWorkflowTemplate.configuration_version_id
            == registry.active_version_id
        )
    )
    assert template is not None
    template.approved_link_domains = list(domains)
    await session.flush()
    bundle = await SqlAlchemyConfigurationRepository(session).bundle(
        registry.active_version_id
    )
    digest = configuration_digest(bundle.specification())
    # Tests need independently pinned domain policies without constructing an
    # entire administrator journey. Core updates deliberately bypass the ORM's
    # append-only fixture guard; PostgreSQL sealing still denies this in runtime.
    await session.execute(
        update(ConfigurationApproval)
        .where(
            ConfigurationApproval.configuration_version_id == registry.active_version_id
        )
        .values(snapshot_digest=digest)
    )
    await session.execute(
        update(ConfigurationActivation)
        .where(
            ConfigurationActivation.configuration_version_id
            == registry.active_version_id
        )
        .values(snapshot_digest=digest)
    )
    await session.flush()


def product_service(
    session: AsyncSession,
    storage: InMemoryPrivateObjectStorage,
    audit: RecordingAudit,
) -> ProductService:
    return ProductService(
        SqlAlchemyProductRepository(session),
        storage,
        SafeDocumentScanner(),
        AllowedHttpsLinkPolicy(frozenset({"products.example.test"})),
        audit,
    )
