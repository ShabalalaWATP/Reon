"""Persistence reads for tightly authorised managed-product inspection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import ServiceRequest
from istari_service.organisation_models import OrganisationUnit
from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductPackage,
)
from istari_service.product_types import ReleaseAccessRecord
from istari_service.repositories.product_records import artefact_record
from istari_service.team_models import TeamMembership, WorkspacePosition


class ProductReviewAccessRepositoryMixin:
    session: AsyncSession

    async def review_access(self, artefact_id: UUID) -> ReleaseAccessRecord | None:
        row = (
            await self.session.execute(
                select(
                    ProductArtefact,
                    ProductPackage,
                    ServiceRequest,
                    ExternalProductLink,
                )
                .select_from(ProductArtefact)
                .join(ProductPackage, ProductPackage.id == ProductArtefact.package_id)
                .join(ServiceRequest, ServiceRequest.id == ProductPackage.request_id)
                .outerjoin(
                    ExternalProductLink,
                    ExternalProductLink.artefact_id == ProductArtefact.id,
                )
                .where(ProductArtefact.id == artefact_id)
            )
        ).one_or_none()
        return (
            ReleaseAccessRecord(
                request_id=row[2].id,
                package_id=row[1].id,
                artefact=artefact_record(row[0], row[3]),
            )
            if row
            else None
        )

    async def live_delivery_membership(
        self,
        actor_id: UUID,
        team_id: UUID | None,
        team_name: str | None,
        *,
        manager: bool,
    ) -> bool:
        now = datetime.now(UTC)
        query = (
            select(TeamMembership.id)
            .join(OrganisationUnit, OrganisationUnit.id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == actor_id,
                TeamMembership.effective_from <= now,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > now,
                ),
                OrganisationUnit.is_configured.is_(True),
            )
        )
        if manager:
            query = query.where(
                TeamMembership.workspace_position == WorkspacePosition.MANAGER
            )
        else:
            query = query.where(
                TeamMembership.workspace_position == WorkspacePosition.MEMBER
            )
        query = query.where(
            OrganisationUnit.id == team_id
            if team_id is not None
            else OrganisationUnit.name == team_name
        )
        return await self.session.scalar(query) is not None
