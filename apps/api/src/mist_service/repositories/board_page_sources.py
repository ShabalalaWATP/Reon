"""Bounded service-request and work-package board projection queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.analytics_models import RequestAnalyticsFact
from mist_service.board_models import WorkPackage
from mist_service.board_projection import (
    ProjectedBoardItem,
    package_projection,
    request_projection,
)
from mist_service.models import ServiceRequest, User
from mist_service.repositories.board_page_filters import (
    TERMINAL_REQUEST_STATUSES,
    cursor_filter,
    package_filters,
    package_statuses,
    request_filters,
    request_statuses,
)
from mist_service.schemas.board import BoardFilters, BoardItemType


class SqlAlchemyBoardProjectionQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def requests(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        statuses = request_statuses(filters)
        if not statuses:
            return []
        completed_cutoff = datetime.now(UTC) - timedelta(days=30)
        statement = (
            select(ServiceRequest, User.display_name)
            .join(
                RequestAnalyticsFact,
                RequestAnalyticsFact.request_id == ServiceRequest.id,
            )
            .outerjoin(User, User.id == ServiceRequest.assigned_specialist_id)
            .where(
                RequestAnalyticsFact.team_unit_id == team_id,
                ServiceRequest.status.in_(statuses),
                or_(
                    ServiceRequest.status.not_in(TERMINAL_REQUEST_STATUSES),
                    ServiceRequest.updated_at >= completed_cutoff,
                ),
                *request_filters(filters),
            )
        )
        if cursor is not None:
            statement = statement.where(
                cursor_filter(
                    ServiceRequest.updated_at,
                    ServiceRequest.id,
                    BoardItemType.SERVICE_REQUEST,
                    cursor,
                )
            )
        rows = (
            await self._session.execute(
                statement.order_by(
                    ServiceRequest.updated_at.desc(), ServiceRequest.id.desc()
                ).limit(fetch_limit)
            )
        ).all()
        return [
            item
            for request, owner in rows
            if (item := request_projection(request, owner)) is not None
        ]

    async def packages(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        statuses = package_statuses(filters)
        if not statuses:
            return []
        statement = (
            select(WorkPackage, User.display_name)
            .join(User, User.id == WorkPackage.owner_user_id)
            .where(
                WorkPackage.team_id == team_id,
                WorkPackage.status.in_(statuses),
                *package_filters(filters),
            )
        )
        if cursor is not None:
            statement = statement.where(
                cursor_filter(
                    WorkPackage.updated_at,
                    WorkPackage.id,
                    BoardItemType.WORK_PACKAGE,
                    cursor,
                )
            )
        rows = (
            await self._session.execute(
                statement.order_by(
                    WorkPackage.updated_at.desc(), WorkPackage.id.desc()
                ).limit(fetch_limit)
            )
        ).all()
        return [package_projection(package, owner) for package, owner in rows]
