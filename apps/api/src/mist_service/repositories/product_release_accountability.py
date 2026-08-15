"""Persistence evidence for independent managed-product decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import RequestStatus, WorkflowTask, WorkflowTaskStatus
from mist_service.product_errors import ProductNotFound
from mist_service.product_models import ProductPackage
from mist_service.qc_membership import is_live_qc_manager
from mist_service.workflow.projection import (
    LEAD_REVIEW_ELEMENT_ID,
    QUALITY_REVIEW_ELEMENT_ID,
    RELEASE_ELEMENT_ID,
)


class ProductReleaseAccountabilityRepositoryMixin:
    session: AsyncSession

    async def live_qc_manager(self, actor_id: UUID) -> bool:
        return await is_live_qc_manager(self.session, actor_id, at=datetime.now(UTC))

    async def manager_task_claimed_by(self, package_id: UUID, actor_id: UUID) -> bool:
        return await self._task_claimed_by(
            package_id,
            actor_id,
            LEAD_REVIEW_ELEMENT_ID,
            RequestStatus.LEAD_REVIEW,
        )

    async def release_task_claimed_by(self, package_id: UUID, actor_id: UUID) -> bool:
        """Require the exact active release task to be claimed by the releaser."""

        return await self._task_claimed_by(
            package_id,
            actor_id,
            RELEASE_ELEMENT_ID,
            RequestStatus.READY_FOR_RELEASE,
        )

    async def quality_task_claimed_by(self, package_id: UUID, actor_id: UUID) -> bool:
        return await self._task_claimed_by(
            package_id,
            actor_id,
            QUALITY_REVIEW_ELEMENT_ID,
            RequestStatus.QUALITY_REVIEW,
        )

    async def _task_claimed_by(
        self,
        package_id: UUID,
        actor_id: UUID,
        element_id: str,
        expected_status: RequestStatus,
    ) -> bool:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        task_id = await self.session.scalar(
            select(WorkflowTask.id).where(
                WorkflowTask.request_id == package.request_id,
                WorkflowTask.element_id == element_id,
                WorkflowTask.expected_status == expected_status,
                WorkflowTask.status == WorkflowTaskStatus.CLAIMED,
                WorkflowTask.assignee_user_id == actor_id,
            )
        )
        return task_id is not None

    async def release_excluded_actor_ids(self, package_id: UUID) -> frozenset[UUID]:
        """Return people already accountable for this exact release cycle."""

        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        completed = {
            await self.session.scalar(
                select(WorkflowTask.assignee_user_id)
                .where(
                    WorkflowTask.request_id == package.request_id,
                    WorkflowTask.element_id == element_id,
                    WorkflowTask.status == WorkflowTaskStatus.COMPLETED,
                    WorkflowTask.assignee_user_id.is_not(None),
                )
                .order_by(WorkflowTask.completed_at.desc(), WorkflowTask.id.desc())
                .limit(1)
            )
            for element_id in ("lead_review", "quality_review")
        }
        values = {
            package.author_user_id,
            package.manager_approved_by_user_id,
            *completed,
        }
        return frozenset(value for value in values if value is not None)
