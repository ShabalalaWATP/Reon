"""Workload aggregation shared by organisation workspace read models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.analytics_models import RequestAnalyticsFact
from mist_service.board_models import WorkPackage, WorkPackageStatus
from mist_service.management_models import OrganisationClosure
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.organisation_models import OrganisationKind

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


async def overview_work_counts(
    session: AsyncSession, team_id: UUID, kind: OrganisationKind
) -> tuple[int, int, int]:
    """Count active, near-due and overdue work for one authorised workspace scope."""

    today = datetime.now(UTC).date()
    active = RequestAnalyticsFact.current_status.not_in(TERMINAL_REQUEST_STATUSES)
    scope = (
        RequestAnalyticsFact.team_unit_id == team_id
        if kind is OrganisationKind.TEAM
        else RequestAnalyticsFact.team_unit_id.in_(
            select(OrganisationClosure.descendant_id).where(
                OrganisationClosure.ancestor_id == team_id
            )
        )
    )
    row = (
        await session.execute(
            select(
                func.count(RequestAnalyticsFact.request_id).filter(active),
                func.count(RequestAnalyticsFact.request_id).filter(
                    active,
                    RequestAnalyticsFact.required_by >= today,
                    RequestAnalyticsFact.required_by <= today + timedelta(days=7),
                ),
                func.count(RequestAnalyticsFact.request_id).filter(
                    active, RequestAnalyticsFact.required_by < today
                ),
            ).where(scope)
        )
    ).one()
    return row[0], row[1], row[2]
