"""Persistence access for immutable per-request configuration policies."""

from __future__ import annotations

from collections.abc import Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_models import RequestConfigurationPin
from istari_service.configuration_request_policy import (
    PinnedProductPolicy,
    RequestConfigurationPolicy,
    parse_request_configuration_policy,
)

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
    return parse_request_configuration_policy(pin.snapshot)


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
    return policies


async def load_request_product_policy(
    session: AsyncSession,
    request_id: UUID,
) -> PinnedProductPolicy | None:
    policy = await load_request_configuration_policy(session, request_id)
    return policy.product if policy is not None else None
