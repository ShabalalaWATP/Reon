"""Column-count queries for the team board projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.board_models import BoardColumn, WorkPackage
from istari_service.board_projection import PACKAGE_COLUMNS, REQUEST_COLUMNS
from istari_service.models import ServiceRequest
from istari_service.repositories.board_page_filters import (
    TERMINAL_REQUEST_STATUSES,
    includes,
    package_filters,
    request_filters,
)
from istari_service.schemas.board import BoardFilters, BoardItemType


class SqlAlchemyBoardCountQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def column_count(
        self,
        team_id: UUID,
        column: BoardColumn,
        *,
        exclude_package_id: UUID,
    ) -> int:
        request_statuses = [
            status
            for status, projected in REQUEST_COLUMNS.items()
            if projected is column
        ]
        package_statuses = [
            status
            for status, projected in PACKAGE_COLUMNS.items()
            if projected is column
        ]
        request_count = 0
        if request_statuses:
            request_count = int(
                await self._session.scalar(
                    select(func.count(ServiceRequest.id))
                    .join(
                        RequestAnalyticsFact,
                        RequestAnalyticsFact.request_id == ServiceRequest.id,
                    )
                    .where(
                        RequestAnalyticsFact.team_unit_id == team_id,
                        ServiceRequest.status.in_(request_statuses),
                    )
                )
                or 0
            )
        package_count = 0
        if package_statuses:
            package_count = int(
                await self._session.scalar(
                    select(func.count(WorkPackage.id)).where(
                        WorkPackage.team_id == team_id,
                        WorkPackage.status.in_(package_statuses),
                        WorkPackage.id != exclude_package_id,
                    )
                )
                or 0
            )
        return request_count + package_count

    async def filtered_column_counts(
        self, team_id: UUID, filters: BoardFilters
    ) -> dict[BoardColumn, int]:
        """Count columns after filters and before cursor pagination."""
        counts = dict.fromkeys(BoardColumn, 0)
        completed_cutoff = datetime.now(UTC) - timedelta(days=30)
        if includes(filters, BoardItemType.SERVICE_REQUEST):
            request_rows = (
                await self._session.execute(
                    select(ServiceRequest.status, func.count(ServiceRequest.id))
                    .join(
                        RequestAnalyticsFact,
                        RequestAnalyticsFact.request_id == ServiceRequest.id,
                    )
                    .where(
                        RequestAnalyticsFact.team_unit_id == team_id,
                        ServiceRequest.status.in_(list(REQUEST_COLUMNS)),
                        or_(
                            ServiceRequest.status.not_in(TERMINAL_REQUEST_STATUSES),
                            ServiceRequest.updated_at >= completed_cutoff,
                        ),
                        *request_filters(filters),
                    )
                    .group_by(ServiceRequest.status)
                )
            ).all()
            for status, count in request_rows:
                counts[REQUEST_COLUMNS[status]] += int(count)
        if includes(filters, BoardItemType.WORK_PACKAGE):
            package_rows = (
                await self._session.execute(
                    select(WorkPackage.status, func.count(WorkPackage.id))
                    .where(
                        WorkPackage.team_id == team_id,
                        WorkPackage.status.in_(list(PACKAGE_COLUMNS)),
                        *package_filters(filters),
                    )
                    .group_by(WorkPackage.status)
                )
            ).all()
            for status, count in package_rows:
                counts[PACKAGE_COLUMNS[status]] += int(count)
        return counts
