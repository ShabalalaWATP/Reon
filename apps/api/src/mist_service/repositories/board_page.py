"""Compatibility facade for bounded team-board projection queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from mist_service.board_models import BoardColumn
from mist_service.board_projection import (
    ProjectedBoardItem,
    decode_cursor,
    paginate,
)
from mist_service.repositories.board_page_counts import SqlAlchemyBoardCountQueries
from mist_service.repositories.board_page_filters import (
    cursor_filter,
    includes,
    package_filters,
    request_filters,
)
from mist_service.repositories.board_page_sources import (
    SqlAlchemyBoardProjectionQueries,
)
from mist_service.schemas.board import BoardFilters, BoardItem, BoardItemType


class SqlAlchemyBoardPageRepository:
    """Retain the board port while delegating projections and counts."""

    def __init__(self, session: AsyncSession) -> None:
        self._projections = SqlAlchemyBoardProjectionQueries(session)
        self._counts = SqlAlchemyBoardCountQueries(session)

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
            cursor_key = (changed_at, BoardItemType(item_type).value, item_id)
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
        return await self._counts.column_count(
            team_id, column, exclude_package_id=exclude_package_id
        )

    async def filtered_column_counts(
        self, team_id: UUID, filters: BoardFilters
    ) -> dict[BoardColumn, int]:
        return await self._counts.filtered_column_counts(team_id, filters)

    async def _requests(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        return await self._projections.requests(team_id, filters, cursor, fetch_limit)

    async def _packages(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: tuple[datetime, str, str] | None,
        fetch_limit: int,
    ) -> list[ProjectedBoardItem]:
        return await self._projections.packages(team_id, filters, cursor, fetch_limit)

    @staticmethod
    def _includes(filters: BoardFilters, item_type: BoardItemType) -> bool:
        return includes(filters, item_type)

    @staticmethod
    def _request_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
        return request_filters(filters)

    @staticmethod
    def _package_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
        return package_filters(filters)

    @staticmethod
    def _cursor_filter(
        changed_column: InstrumentedAttribute[datetime],
        id_column: InstrumentedAttribute[UUID],
        item_type: BoardItemType,
        cursor: tuple[datetime, str, str],
    ) -> ColumnElement[bool]:
        return cursor_filter(changed_column, id_column, item_type, cursor)
