"""Bind managed-product evidence to the human workflow lifecycle."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.errors import InvalidAction
from mist_service.models import ServiceRequest
from mist_service.product_models import ProductDissemination, ProductPackage
from mist_service.product_types import PackageStatus
from mist_service.schemas.work import (
    ApproveWork,
    ChangesRequired,
    CompletionPayload,
    ReleaseDeliverable,
    SubmitDeliverable,
)


async def validate_product_workflow_effect(
    session: AsyncSession,
    request: ServiceRequest,
    actor_id: UUID,
    payload: CompletionPayload,
) -> bool:
    """Require the latest immutable package evidence for each managed stage."""

    if not isinstance(
        payload,
        (SubmitDeliverable, ApproveWork, ChangesRequired, ReleaseDeliverable),
    ):
        return False
    package = await session.scalar(
        select(ProductPackage)
        .where(ProductPackage.request_id == request.id)
        .order_by(ProductPackage.package_version.desc())
        .with_for_update()
        .limit(1)
    )
    if package is None:
        return False
    if isinstance(payload, (SubmitDeliverable, ReleaseDeliverable)) and not (
        payload.managed_product
    ):
        raise InvalidAction("Use the immutable managed product package.")
    if package.package_checksum is None:
        raise InvalidAction("An immutable managed product package is required.")
    if isinstance(payload, SubmitDeliverable):
        valid = (
            package.status is PackageStatus.REVIEW_READY
            and package.author_user_id == actor_id
        )
    elif isinstance(payload, ApproveWork):
        valid = package.status is PackageStatus.MANAGER_APPROVED
    elif isinstance(payload, ChangesRequired):
        valid = package.status in {
            PackageStatus.REVIEW_READY,
            PackageStatus.MANAGER_APPROVED,
        }
    elif isinstance(payload, ReleaseDeliverable):  # pragma: no branch
        valid = (
            package.status is PackageStatus.DISSEMINATED
            and await _is_exact_release(session, request, package)
        )
    if not valid:
        raise InvalidAction(
            "The managed product package is not ready for this workflow action."
        )
    return True


async def product_workflow_details(
    session: AsyncSession,
    request_id: UUID,
    payload: CompletionPayload,
) -> dict[str, str | int]:
    """Return immutable package identity for the workflow audit event."""

    if not isinstance(
        payload,
        (SubmitDeliverable, ApproveWork, ChangesRequired, ReleaseDeliverable),
    ):
        return {}
    package = await session.scalar(
        select(ProductPackage)
        .where(ProductPackage.request_id == request_id)
        .order_by(ProductPackage.package_version.desc())
        .limit(1)
    )
    if package is None or package.package_checksum is None:
        return {}
    return {
        "packageId": str(package.id),
        "packageVersion": package.package_version,
        "packageChecksum": package.package_checksum,
    }


async def _is_exact_release(
    session: AsyncSession,
    request: ServiceRequest,
    package: ProductPackage,
) -> bool:
    evidence = await session.scalar(
        select(ProductDissemination.id).where(
            ProductDissemination.package_id == package.id,
            ProductDissemination.recipient_user_id == request.requester_id,
            ProductDissemination.withdrawn_at.is_(None),
            ProductDissemination.package_checksum == package.package_checksum,
        )
    )
    return evidence is not None
