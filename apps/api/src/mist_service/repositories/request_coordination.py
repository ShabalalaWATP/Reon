"""Persistence queries for request-scoped coordination."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.models import ServiceRequest, UserRole
from mist_service.organisation_models import OrganisationUnit, RequestRouteSelection
from mist_service.repositories.route_access import (
    ROUTE_POSITION_BY_ROLE,
    route_membership_condition,
)
from mist_service.request_coordination_ports import ReturnRouteTarget


class RequestCoordinationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def request(self, request_id: UUID) -> ServiceRequest | None:
        return await self._session.get(ServiceRequest, request_id)

    async def has_route_membership(self, actor: Actor, request_id: UUID) -> bool:
        membership = route_membership_condition(actor)
        if membership is None:
            return False
        return bool(
            await self._session.scalar(
                select(ServiceRequest.id).where(
                    ServiceRequest.id == request_id, membership
                )
            )
        )

    @staticmethod
    def route_position(role: UserRole) -> int | None:
        return ROUTE_POSITION_BY_ROLE.get(role)

    async def route_target(
        self, request_id: UUID, unit_id: UUID
    ) -> ReturnRouteTarget | None:
        row = (
            await self._session.execute(
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
        return (
            ReturnRouteTarget(name=row.OrganisationUnit.name, position=row.position)
            if row
            else None
        )
