"""Persistence queries for request-scoped coordination."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.models import ServiceRequest
from istari_service.organisation_models import OrganisationUnit, RequestRouteSelection
from istari_service.repositories.organisation import route_membership_condition


class RequestCoordinationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request(self, request_id: UUID) -> ServiceRequest | None:
        return await self.session.get(ServiceRequest, request_id)

    async def has_route_membership(self, actor: Actor, request_id: UUID) -> bool:
        membership = route_membership_condition(actor)
        if membership is None:
            return False
        return bool(
            await self.session.scalar(
                select(ServiceRequest.id).where(
                    ServiceRequest.id == request_id, membership
                )
            )
        )

    async def route_target(
        self, request_id: UUID, unit_id: UUID
    ) -> tuple[OrganisationUnit, int] | None:
        row = (
            await self.session.execute(
                select(OrganisationUnit, RequestRouteSelection.position)
                .join(
                    RequestRouteSelection,
                    RequestRouteSelection.unit_id == OrganisationUnit.id,
                )
                .where(
                    RequestRouteSelection.request_id == request_id,
                    RequestRouteSelection.unit_id == unit_id,
                )
            )
        ).one_or_none()
        return (row.OrganisationUnit, row.position) if row else None
