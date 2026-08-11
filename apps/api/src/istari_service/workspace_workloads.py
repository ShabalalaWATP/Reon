"""Workload aggregation shared by organisation workspace read models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import WorkPackage, WorkPackageStatus
from istari_service.models import RequestStatus, ServiceRequest

TERMINAL_REQUEST_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


async def active_work_counts(
    session: AsyncSession, user_ids: set[UUID]
) -> dict[UUID, int]:
    if not user_ids:
        return {}
    request_counts = (
        select(
            ServiceRequest.assigned_specialist_id.label("user_id"),
            func.count(ServiceRequest.id).label("active_count"),
        )
        .where(
            ServiceRequest.assigned_specialist_id.in_(user_ids),
            ServiceRequest.status.not_in(TERMINAL_REQUEST_STATUSES),
        )
        .group_by(ServiceRequest.assigned_specialist_id)
    )
    package_counts = (
        select(
            WorkPackage.owner_user_id.label("user_id"),
            func.count(WorkPackage.id).label("active_count"),
        )
        .where(
            WorkPackage.owner_user_id.in_(user_ids),
            WorkPackage.status.not_in(
                {WorkPackageStatus.DONE, WorkPackageStatus.CANCELLED}
            ),
        )
        .group_by(WorkPackage.owner_user_id)
    )
    combined = request_counts.union_all(package_counts).subquery()
    result = await session.execute(
        select(combined.c.user_id, func.sum(combined.c.active_count)).group_by(
            combined.c.user_id
        )
    )
    return {user_id: int(count) for user_id, count in result.tuples()}
