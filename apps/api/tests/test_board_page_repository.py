"""Database Board filtering, cursor and bounded-source branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import BoardColumn, WorkPackage
from istari_service.board_projection import ProjectedBoardItem, encode_cursor
from istari_service.repositories.board_page import SqlAlchemyBoardPageRepository
from istari_service.schemas.board import BoardFilters, BoardItem, BoardItemType


class ScalarSession:
    def __init__(self, *values: int | None) -> None:
        self.values = iter(values)
        self.statements: list[object] = []

    async def scalar(self, statement: object) -> int | None:
        self.statements.append(statement)
        return next(self.values)


class EmptyRows:
    def all(self) -> list[tuple[object, str]]:
        return []


class ExecuteSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> EmptyRows:
        self.statements.append(statement)
        return EmptyRows()


def projected_item(item_type: BoardItemType) -> ProjectedBoardItem:
    return ProjectedBoardItem(
        BoardItem(
            id=uuid4(),
            itemType=item_type,
            reference="SYNTHETIC-1",
            title="Synthetic bounded Board item",
            column=BoardColumn.IN_PROGRESS,
            priority="HIGH",
            dueOn=datetime.now(UTC).date(),
            ownerUserId=None,
            ownerDisplayName=None,
            version=1,
            linkedRequestId=None,
            availableColumns=[],
        ),
        datetime.now(UTC),
    )


async def test_projection_decodes_cursor_and_queries_only_selected_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = SqlAlchemyBoardPageRepository(cast(AsyncSession, object()))
    request_item = projected_item(BoardItemType.SERVICE_REQUEST)
    request_rows = AsyncMock(return_value=[request_item])
    package_rows = AsyncMock(return_value=[])
    monkeypatch.setattr(repository, "_requests", request_rows)
    monkeypatch.setattr(repository, "_packages", package_rows)

    rows = await repository.projected(
        uuid4(),
        BoardFilters(itemTypes=[BoardItemType.SERVICE_REQUEST]),
        encode_cursor(request_item),
        11,
    )

    assert rows == [request_item]
    request_rows.assert_awaited_once()
    package_rows.assert_not_awaited()


async def test_column_counts_cover_request_and_package_only_columns() -> None:
    request_session = ScalarSession(None)
    request_repository = SqlAlchemyBoardPageRepository(
        cast(AsyncSession, request_session)
    )
    assert (
        await request_repository.column_count(
            uuid4(), BoardColumn.MANAGER_REVIEW, exclude_package_id=uuid4()
        )
        == 0
    )
    assert len(request_session.statements) == 1

    package_session = ScalarSession(3)
    package_repository = SqlAlchemyBoardPageRepository(
        cast(AsyncSession, package_session)
    )
    assert (
        await package_repository.column_count(
            uuid4(), BoardColumn.READY, exclude_package_id=uuid4()
        )
        == 3
    )
    assert len(package_session.statements) == 1


async def test_source_queries_handle_empty_statuses_and_cursors() -> None:
    session = ExecuteSession()
    repository = SqlAlchemyBoardPageRepository(cast(AsyncSession, session))
    team_id = uuid4()
    cursor = (datetime.now(UTC), BoardItemType.WORK_PACKAGE.value, str(uuid4()))

    assert (
        await repository._requests(
            team_id, BoardFilters(columns=[BoardColumn.BACKLOG]), None, 10
        )
        == []
    )
    assert (
        await repository._packages(
            team_id, BoardFilters(columns=[BoardColumn.MANAGER_REVIEW]), None, 10
        )
        == []
    )
    assert await repository._requests(team_id, BoardFilters(), cursor, 10) == []
    assert await repository._packages(team_id, BoardFilters(), cursor, 10) == []
    assert len(session.statements) == 2


def test_filter_builders_cover_every_optional_database_predicate() -> None:
    owner_id = uuid4()
    due_before = datetime.now(UTC).date()
    filters = BoardFilters(
        search=" Synthetic%_query ",
        priorities=["HIGH", "UNSET"],
        ownerUserId=owner_id,
        dueBefore=due_before,
    )
    assert len(SqlAlchemyBoardPageRepository._request_filters(filters)) == 4
    assert len(SqlAlchemyBoardPageRepository._package_filters(filters)) == 4
    assert (
        len(
            SqlAlchemyBoardPageRepository._request_filters(
                BoardFilters(priorities=["UNSET"])
            )
        )
        == 1
    )
    assert (
        len(
            SqlAlchemyBoardPageRepository._request_filters(
                BoardFilters(priorities=["HIGH"])
            )
        )
        == 1
    )
    assert SqlAlchemyBoardPageRepository._request_filters(BoardFilters()) == []
    assert SqlAlchemyBoardPageRepository._package_filters(BoardFilters()) == []


def test_cursor_filter_supports_both_item_types_and_equal_ids() -> None:
    changed_at = datetime.now(UTC)
    item_id = uuid4()
    cursors: tuple[tuple[BoardItemType, str], ...] = (
        (BoardItemType.SERVICE_REQUEST, BoardItemType.WORK_PACKAGE.value),
        (BoardItemType.WORK_PACKAGE, BoardItemType.WORK_PACKAGE.value),
        (BoardItemType.WORK_PACKAGE, BoardItemType.SERVICE_REQUEST.value),
    )
    for item_type, cursor_type in cursors:
        expression = SqlAlchemyBoardPageRepository._cursor_filter(
            WorkPackage.updated_at,
            WorkPackage.id,
            item_type,
            (changed_at, cursor_type, str(item_id)),
        )
        assert expression is not None


def test_selected_source_predicate_defaults_to_both_sources() -> None:
    assert SqlAlchemyBoardPageRepository._includes(
        BoardFilters(), BoardItemType.SERVICE_REQUEST
    )
    assert not SqlAlchemyBoardPageRepository._includes(
        BoardFilters(itemTypes=[BoardItemType.WORK_PACKAGE]),
        BoardItemType.SERVICE_REQUEST,
    )
