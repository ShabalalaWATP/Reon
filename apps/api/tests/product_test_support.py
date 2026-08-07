"""Shared managed-product service fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from istari_service.configuration_models import ConfigurationWorkflowTemplate
from istari_service.domain import Actor
from istari_service.models import RequestStatus, ServiceRequest, User
from istari_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from istari_service.product_storage import InMemoryPrivateObjectStorage
from istari_service.product_types import AccessAuditRecord
from istari_service.repositories.auth import actor_from_user
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.repositories.request_route_initialisation import (
    initialise_request_route,
)
from istari_service.services.product_service import ProductService

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
                desired_outcome="A safe managed product.",
                background_context="Synthetic context only.",
                required_by=datetime.now(UTC).date() + timedelta(days=7),
                required_by_reason="Synthetic review date.",
                preferred_deliverable_type="PDF",
                success_criteria="The synthetic product passes review.",
                requesting_business_area=requester.scope,
                intended_recipients=["Synthetic Customer"],
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
        template = await session.scalar(
            select(ConfigurationWorkflowTemplate)
            .order_by(ConfigurationWorkflowTemplate.created_at.desc())
            .limit(1)
        )
        assert template is not None
        template.approved_link_domains = list(approved_link_domains)
        await session.flush()
        await SqlAlchemyConfigurationPinRepository(session).pin_request(request_id)
    return request_id


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
