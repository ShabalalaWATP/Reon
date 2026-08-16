"""Persistence access for immutable per-request configuration policies.

A pin fixes the structure a request is routed through: which units exist,
their hierarchy, staffing and candidate groups. A unit's name is only what
people read, so it is overlaid from the live organisation on load; a rename
made after the pin then reaches this request too, instead of showing one name
here and another everywhere else. The stored pin itself never changes.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import replace
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.configuration_models import RequestConfigurationPin
from mist_service.configuration_request_policy import (
    PinnedProductPolicy,
    RequestConfigurationPolicy,
    parse_request_configuration_policy,
)
from mist_service.organisation_models import OrganisationUnit

PIN_QUERY_BATCH_SIZE = 500


async def load_request_configuration_policy(
    session: AsyncSession,
    request_id: UUID,
) -> RequestConfigurationPolicy | None:
    pin = await session.scalar(
        select(RequestConfigurationPin).where(
            RequestConfigurationPin.request_id == request_id
        )
    )
    if pin is None or "requestPolicySchema" not in pin.snapshot:
        return None
    policy = parse_request_configuration_policy(pin.snapshot)
    names = await _live_unit_names(session, set(policy.units))
    return _with_display_names(policy, names)


async def load_request_configuration_policies(
    session: AsyncSession,
    request_ids: Set[UUID],
) -> dict[UUID, RequestConfigurationPolicy]:
    """Load request policies in bounded batches, avoiding per-request queries."""

    if not request_ids:
        return {}
    policies: dict[UUID, RequestConfigurationPolicy] = {}
    ordered_ids = sorted(request_ids, key=str)
    for offset in range(0, len(ordered_ids), PIN_QUERY_BATCH_SIZE):
        pins = await session.scalars(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id.in_(
                    ordered_ids[offset : offset + PIN_QUERY_BATCH_SIZE]
                )
            )
        )
        policies.update(
            {
                pin.request_id: parse_request_configuration_policy(pin.snapshot)
                for pin in pins
                if "requestPolicySchema" in pin.snapshot
            }
        )
    unit_ids = {unit_id for policy in policies.values() for unit_id in policy.units}
    names = await _live_unit_names(session, unit_ids)
    return {
        request_id: _with_display_names(policy, names)
        for request_id, policy in policies.items()
    }


async def load_request_product_policy(
    session: AsyncSession,
    request_id: UUID,
) -> PinnedProductPolicy | None:
    policy = await load_request_configuration_policy(session, request_id)
    return policy.product if policy is not None else None


async def _live_unit_names(
    session: AsyncSession, unit_ids: Set[UUID]
) -> dict[UUID, str]:
    if not unit_ids:
        return {}
    rows = await session.execute(
        select(OrganisationUnit.id, OrganisationUnit.name).where(
            OrganisationUnit.id.in_(unit_ids)
        )
    )
    return {unit_id: str(name) for unit_id, name in rows.all()}


def _with_display_names(
    policy: RequestConfigurationPolicy, names: Mapping[UUID, str]
) -> RequestConfigurationPolicy:
    """Units without a live row keep their pinned name."""

    return replace(
        policy,
        units=MappingProxyType(
            {
                unit_id: replace(unit, name=names.get(unit_id, unit.name))
                for unit_id, unit in policy.units.items()
            }
        ),
    )
