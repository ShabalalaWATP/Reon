"""Request and actor lookups for managed-product persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.models import ServiceRequest, User
from istari_service.organisation_models import RequestRouteSelection
from istari_service.product_types import ProductRequestRecord
from istari_service.repositories.request_participants import active_participant_ids


class ProductRequestRepositoryMixin:
    session: AsyncSession

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
            query = query.with_for_update()
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
                    User.id == actor.id,
                    User.is_active.is_(True),
                    User.role == actor.role,
                    User.scope == actor.scope,
                )
            )
        )
