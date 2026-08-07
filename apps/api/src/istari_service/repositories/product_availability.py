"""Authoritative managed-product availability projections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    RequestStatus,
    ServiceRequest,
)
from istari_service.product_models import ProductDissemination, ProductPackage
from istari_service.product_types import PackageStatus


def disseminated_product_exists() -> ColumnElement[bool]:
    """Correlate availability to the request and its exact Customer recipient."""

    return exists(
        select(ProductDissemination.id)
        .join(
            ProductPackage,
            ProductPackage.id == ProductDissemination.package_id,
        )
        .where(
            ProductPackage.request_id == ServiceRequest.id,
            ServiceRequest.status == RequestStatus.COMPLETED,
            ProductPackage.status == PackageStatus.DISSEMINATED,
            ProductDissemination.recipient_user_id == ServiceRequest.requester_id,
            ProductDissemination.withdrawn_at.is_(None),
            ProductDissemination.package_checksum == ProductPackage.package_checksum,
        )
    )


def available_product_exists() -> ColumnElement[bool]:
    """Correlate either managed dissemination or a released legacy product."""

    released_legacy_product = exists(
        select(Deliverable.id).where(
            Deliverable.request_id == ServiceRequest.id,
            Deliverable.status == DeliverableStatus.RELEASED,
            Deliverable.released_at.is_not(None),
            ServiceRequest.status == RequestStatus.COMPLETED,
        )
    )
    return or_(disseminated_product_exists(), released_legacy_product)


async def has_disseminated_product(session: AsyncSession, request_id: UUID) -> bool:
    available = await session.scalar(
        select(disseminated_product_exists()).where(ServiceRequest.id == request_id)
    )
    return bool(available)


async def has_available_product(session: AsyncSession, request_id: UUID) -> bool:
    available = await session.scalar(
        select(available_product_exists()).where(ServiceRequest.id == request_id)
    )
    return bool(available)
