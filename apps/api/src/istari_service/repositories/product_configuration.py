"""Per-request immutable product-policy lookups."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.repositories.configuration_policies import (
    load_request_product_policy,
)


class ProductConfigurationRepositoryMixin:
    session: AsyncSession

    async def approved_link_domains(self, request_id: UUID) -> frozenset[str] | None:
        policy = await load_request_product_policy(self.session, request_id)
        return policy.approved_link_domains if policy is not None else None
