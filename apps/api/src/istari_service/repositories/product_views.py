"""Managed-product read-model construction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import ServiceRequest, User
from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
    ProductScan,
)
from istari_service.schemas.products import (
    ArtefactView,
    CustomerReleaseView,
    PackageView,
)


async def artefact_views(
    session: AsyncSession,
    package_id: UUID,
    *,
    include_review_details: bool = False,
) -> list[ArtefactView]:
    released_at = await session.scalar(
        select(ProductPackage.disseminated_at).where(ProductPackage.id == package_id)
    )
    rows = (
        await session.execute(
            select(ProductArtefact, ExternalProductLink, ProductScan)
            .outerjoin(
                ExternalProductLink,
                ExternalProductLink.artefact_id == ProductArtefact.id,
            )
            .outerjoin(ProductScan, ProductScan.artefact_id == ProductArtefact.id)
            .where(ProductArtefact.package_id == package_id)
            .order_by(ProductArtefact.position, ProductScan.created_at.desc())
        )
    ).all()
    unique: dict[UUID, ArtefactView] = {}
    for artefact, link, scan in rows:
        if artefact.id not in unique:
            unique[artefact.id] = ArtefactView(
                id=artefact.id,
                package_id=artefact.package_id,
                position=artefact.position,
                kind=artefact.kind,
                lifecycle=artefact.lifecycle,
                label=artefact.label,
                filename=artefact.filename,
                media_type=artefact.media_type,
                size_bytes=artefact.size_bytes,
                sha256=artefact.checksum,
                version=artefact.version,
                destination_domain=link.normalised_domain if link else None,
                review_destination_url=(
                    link.destination_url
                    if link is not None and include_review_details
                    else None
                ),
                review_url=(
                    f"/api/v1/product-packages/artefacts/{artefact.id}/review"
                    if include_review_details
                    and artefact.kind.value == "MANAGED_FILE"
                    and artefact.lifecycle.value == "CLEAN"
                    else None
                ),
                expires_at=link.expires_at if link else None,
                scan_result=scan.result if scan else None,
                scan_reason=scan.reason_code if scan else None,
                released_at=released_at,
            )
    return list(unique.values())


async def package_view(
    session: AsyncSession,
    package: ProductPackage,
    *,
    include_review_details: bool = False,
) -> PackageView:
    request = await session.get(ServiceRequest, package.request_id)
    author_name = await session.scalar(
        select(User.display_name).where(User.id == package.author_user_id)
    )
    manager_name = (
        await session.scalar(
            select(User.display_name).where(
                User.id == package.manager_approved_by_user_id
            )
        )
        if package.manager_approved_by_user_id
        else None
    )
    releasing_name = (
        await session.scalar(
            select(User.display_name).where(User.id == package.disseminated_by_user_id)
        )
        if package.disseminated_by_user_id
        else None
    )
    if request is None or author_name is None:
        raise LookupError("product package ownership is incomplete")
    return PackageView(
        id=package.id,
        request_id=package.request_id,
        request_reference=request.reference,
        request_title=request.title,
        request_status=request.status,
        author_display_name=author_name,
        package_version=package.package_version,
        policy_version=package.policy_version,
        status=package.status,
        covering_note=package.covering_note,
        package_checksum=package.package_checksum,
        version=package.version,
        artefacts=await artefact_views(
            session,
            package.id,
            include_review_details=include_review_details,
        ),
        manager_approved_at=package.manager_approved_at,
        manager_approved_by=manager_name,
        disseminated_at=package.disseminated_at,
        disseminated_by=releasing_name,
        withdrawal_reason=package.withdrawal_reason,
    )


async def customer_release_view(
    session: AsyncSession, package: ProductPackage
) -> CustomerReleaseView:
    releasing_name = await session.scalar(
        select(User.display_name).where(User.id == package.disseminated_by_user_id)
    )
    if package.disseminated_at is None or releasing_name is None:
        raise LookupError("release evidence is incomplete")
    accepted_at = await session.scalar(
        select(ProductDissemination.accepted_at).where(
            ProductDissemination.package_id == package.id
        )
    )
    return CustomerReleaseView(
        package_id=package.id,
        request_id=package.request_id,
        package_version=package.package_version,
        status=package.status,
        released_at=package.disseminated_at,
        released_by=releasing_name,
        covering_note=(
            package.covering_note
            or "No covering note was recorded for this historical package."
        ),
        accepted_at=accepted_at,
        artefacts=await artefact_views(session, package.id),
    )
