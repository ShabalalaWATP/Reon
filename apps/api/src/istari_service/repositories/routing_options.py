"""Request-pinned routing path and immediate-child option projection."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_request_policy import (
    RequestConfigurationPolicy,
)
from istari_service.models import RequestStatus
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
)
from istari_service.repositories.configuration_policies import (
    load_request_configuration_policy,
)
from istari_service.schemas.organisation import (
    OrganisationUnitView,
    RoutingOptionsWorkspace,
    RoutingPathUnit,
)


async def routing_workspace(
    session: AsyncSession,
    request_id: UUID,
    status: RequestStatus,
) -> RoutingOptionsWorkspace:
    parent_position, expected_kind = _option_spec(status)
    if parent_position is None or expected_kind is None:
        return RoutingOptionsWorkspace(route=[], items=[])
    rows = (
        await session.execute(
            select(
                RequestRouteSelection.position,
                RequestRouteSelection.unit_id,
            )
            .where(
                RequestRouteSelection.request_id == request_id,
                RequestRouteSelection.position <= parent_position,
            )
            .order_by(RequestRouteSelection.position)
        )
    ).all()
    selections = [(row.position, row.unit_id) for row in rows]
    if not selections or selections[-1][0] != parent_position:
        return RoutingOptionsWorkspace(route=[], items=[])
    policy = await load_request_configuration_policy(session, request_id)
    route = await _route_path(session, selections, policy)
    parent_id = selections[-1][1]
    items = (
        policy.routing_options(parent_id, expected_kind)
        if policy is not None
        else await _legacy_options(session, parent_id, expected_kind)
    )
    return RoutingOptionsWorkspace(route=route, items=items)


async def _route_path(
    session: AsyncSession,
    selections: list[tuple[int, UUID]],
    policy: RequestConfigurationPolicy | None,
) -> list[RoutingPathUnit]:
    if policy is not None:
        path: list[RoutingPathUnit] = []
        for _, unit_id in selections:
            unit = policy.units.get(unit_id)
            if unit is None:
                raise RuntimeError("the pinned request route is invalid")
            path.append(
                RoutingPathUnit(
                    id=unit.unit_id,
                    code=unit.code,
                    name=unit.name,
                    kind=unit.kind,
                )
            )
        return path
    unit_ids = [unit_id for _, unit_id in selections]
    units = {
        unit.id: unit
        for unit in await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.id.in_(unit_ids))
        )
    }
    if len(units) != len(unit_ids):
        raise RuntimeError("the legacy request route is invalid")
    return [
        RoutingPathUnit(
            id=unit.id,
            code=unit.code,
            name=unit.name,
            kind=unit.kind,
        )
        for _, unit_id in selections
        for unit in (units[unit_id],)
    ]


async def _legacy_options(
    session: AsyncSession,
    parent_id: UUID,
    expected_kind: OrganisationKind,
) -> list[OrganisationUnitView]:
    units = (
        await session.scalars(
            select(OrganisationUnit)
            .where(
                OrganisationUnit.parent_id == parent_id,
                OrganisationUnit.kind == expected_kind,
                OrganisationUnit.is_configured.is_(True),
            )
            .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
        )
    ).all()
    return [OrganisationUnitView.model_validate(unit) for unit in units]


def _option_spec(
    status: RequestStatus,
) -> tuple[int | None, OrganisationKind | None]:
    return {
        RequestStatus.TRIAGE_REVIEW: (0, OrganisationKind.COMMAND),
        RequestStatus.COORDINATION_REVIEW: (1, OrganisationKind.OPS_GROUP),
        RequestStatus.ALLOCATION_REVIEW: (2, OrganisationKind.TEAM),
    }.get(status, (None, None))
