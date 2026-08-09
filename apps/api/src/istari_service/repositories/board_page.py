"""Database-filtered, bounded team-board page projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.board_models import BoardColumn, WorkPackage
from istari_service.board_projection import (
    PACKAGE_COLUMNS,
    REQUEST_COLUMNS,
    ProjectedBoardItem,
    decode_cursor,
    package_projection,
    paginate,
    request_projection,
)
from istari_service.models import RequestStatus, ServiceRequest, User
from istari_service.schemas.board import BoardFilters, BoardItem, BoardItemType

TERMINAL_REQUEST_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


class SqlAlchemyBoardPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def page(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[BoardItem], str | None]:
        rows = await self.projected(team_id, filters, cursor, limit + 1)
        return paginate(rows, None, limit)

    async def projected(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: str | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        cursor_key = decode_cursor(cursor) if cursor else None
        if cursor_key is not None:
            changed_at, item_type, item_id = cursor_key
            cursor_key = (
                changed_at,
                BoardItemType(item_type).value,
                item_id,
            )
        rows: list[ProjectedBoardItem] = []
        if self._includes(filters, BoardItemType.SERVICE_REQUEST):
            rows.extend(await self._requests(team_id, filters, cursor_key, fetch_limit))
        if self._includes(filters, BoardItemType.WORK_PACKAGE):
            rows.extend(await self._packages(team_id, filters, cursor_key, fetch_limit))
        return rows

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

    async def _requests(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        statuses = [
            status
            for status, column in REQUEST_COLUMNS.items()
            if not filters.columns or column in filters.columns
        ]
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
                *self._request_filters(filters),
            )
        )
        if cursor is not None:
            statement = statement.where(
                self._cursor_filter(
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

    async def _packages(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        statuses = [
            status
            for status, column in PACKAGE_COLUMNS.items()
            if not filters.columns or column in filters.columns
        ]
        if not statuses:
            return []
        statement = (
            select(WorkPackage, User.display_name)
            .join(User, User.id == WorkPackage.owner_user_id)
            .where(
                WorkPackage.team_id == team_id,
                WorkPackage.status.in_(statuses),
                *self._package_filters(filters),
            )
        )
        if cursor is not None:
            statement = statement.where(
                self._cursor_filter(
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

    @staticmethod
    def _includes(filters: BoardFilters, item_type: BoardItemType) -> bool:
        return not filters.item_types or item_type in filters.item_types

    @staticmethod
    def _request_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        search = filters.search.strip().lower()
        if search:
            conditions.append(
                or_(
                    func.lower(ServiceRequest.reference).contains(
                        search, autoescape=True
                    ),
                    func.lower(ServiceRequest.title).contains(search, autoescape=True),
                )
            )
        if filters.priorities:
            values = [value for value in filters.priorities if value != "UNSET"]
            conditions.append(
                or_(
                    ServiceRequest.priority.in_(values) if values else false(),
                    ServiceRequest.priority.is_(None)
                    if "UNSET" in filters.priorities
                    else false(),
                )
            )
        if filters.owner_user_id:
            conditions.append(
                ServiceRequest.assigned_specialist_id == filters.owner_user_id
            )
        if filters.due_before:
            conditions.append(ServiceRequest.required_by <= filters.due_before)
        return conditions

    @staticmethod
    def _package_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        search = filters.search.strip().lower()
        if search:
            conditions.append(
                func.lower(WorkPackage.title).contains(search, autoescape=True)
            )
        if filters.priorities:
            conditions.append(WorkPackage.priority.in_(filters.priorities))
        if filters.owner_user_id:
            conditions.append(WorkPackage.owner_user_id == filters.owner_user_id)
        if filters.due_before:
            conditions.append(WorkPackage.due_on <= filters.due_before)
        return conditions

    @staticmethod
    def _cursor_filter(
        changed_column: InstrumentedAttribute[datetime],
        id_column: InstrumentedAttribute[UUID],
        item_type: BoardItemType,
        cursor: tuple[datetime, str, str],
    ) -> ColumnElement[bool]:
        changed_at, cursor_type, cursor_id = cursor
        selected_type = item_type.value
        tie_breaker: ColumnElement[bool]
        if selected_type < cursor_type:
            tie_breaker = id_column.is_not(None)
        elif selected_type == cursor_type:
            tie_breaker = id_column < UUID(cursor_id)
        else:
            tie_breaker = false()
        return or_(
            changed_column < changed_at,
            and_(changed_column == changed_at, tie_breaker),
        )
