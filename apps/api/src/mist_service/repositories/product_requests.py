"""Request and actor lookups for managed-product persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.identity_context import active_actor_condition
from mist_service.models import Deliverable, ProductMode, ServiceRequest, User
from mist_service.organisation_models import RequestRouteSelection
from mist_service.product_errors import ProductConflict
from mist_service.product_types import ProductRequestRecord
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.request_participants import active_participant_ids
from mist_service.request_event_audience import RequestEventAudience


class ProductRequestRepositoryMixin:
    session: AsyncSession

    async def require_managed_product_request(self, request_id: UUID) -> None:
        request = await self.session.get(ServiceRequest, request_id)
        legacy_product = await self.session.scalar(
            select(Deliverable.id).where(Deliverable.request_id == request_id).limit(1)
        )
        if (
            request is None
            or request.product_mode is not ProductMode.MANAGED
            or legacy_product is not None
        ):
            raise ProductConflict("A legacy product already exists for this request.")

    async def record_managed_package_started(
        self,
        request_id: UUID,
        actor_id: UUID,
        package_id: UUID,
        package_version: int,
    ) -> None:
        request = await self.session.get(ServiceRequest, request_id)
        if request is None:  # pragma: no cover - locked request invariant
            raise ProductConflict()
        await append_request_event(
            self.session,
            request_id=request.id,
            actor_id=actor_id,
            event_type="PRODUCT_PACKAGE_STARTED",
            message="A managed product package was started for this request.",
            prior_status=request.status,
            next_status=request.status,
            audience=RequestEventAudience.STAFF_ONLY,
            details={
                "packageId": str(package_id),
                "packageVersion": package_version,
                "productMode": ProductMode.MANAGED.value,
            },
        )

    async def request(
        self, request_id: UUID, *, lock: bool
    ) -> ProductRequestRecord | None:
        query = (
            select(ServiceRequest, RequestRouteSelection.unit_id)
            .outerjoin(
                RequestRouteSelection,
                (RequestRouteSelection.request_id == ServiceRequest.id)
                & (RequestRouteSelection.position == 3),
            )
            .where(ServiceRequest.id == request_id)
        )
        if lock:
            # PostgreSQL refuses an unqualified FOR UPDATE when a query contains
            # a left join because the nullable route-selection side cannot be
            # locked. The request is the mutation fence; the route row is only
            # projection context.
            query = query.with_for_update(of=ServiceRequest)
        row = (await self.session.execute(query)).one_or_none()
        request = row[0] if row else None
        route_team_id = row[1] if row else None
        if request is None:
            return None
        if (
            request.assigned_delivery_team_id is not None
            and request.assigned_delivery_team_id != route_team_id
        ):
            return None
        return ProductRequestRecord(
            id=request.id,
            requester_id=request.requester_id,
            status=request.status.value,
            product_mode=request.product_mode.value,
            assigned_team=request.assigned_delivery_team,
            assigned_team_id=request.assigned_delivery_team_id,
            assigned_specialist_id=request.assigned_specialist_id,
            version=request.version,
            participant_ids=await active_participant_ids(self.session, request.id),
        )

    async def active_actor(self, actor: Actor) -> bool:
        return bool(
            await self.session.scalar(
                select(User.id).where(
                    active_actor_condition(actor),
                )
            )
        )
