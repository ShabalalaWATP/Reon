"""SQL expression builders shared by bounded board-page queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, false, func, or_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from mist_service.board_models import WorkPackage, WorkPackageStatus
from mist_service.board_projection import PACKAGE_COLUMNS, REQUEST_COLUMNS
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.board import BoardFilters, BoardItemType

TERMINAL_REQUEST_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


def includes(filters: BoardFilters, item_type: BoardItemType) -> bool:
    return not filters.item_types or item_type in filters.item_types


def request_statuses(filters: BoardFilters) -> list[RequestStatus]:
    return [
        status
        for status, column in REQUEST_COLUMNS.items()
        if not filters.columns or column in filters.columns
    ]


def package_statuses(filters: BoardFilters) -> list[WorkPackageStatus]:
    return [
        status
        for status, column in PACKAGE_COLUMNS.items()
        if not filters.columns or column in filters.columns
    ]


def request_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    search = filters.search.strip().lower()
    if search:
        conditions.append(
            or_(
                func.lower(ServiceRequest.reference).contains(search, autoescape=True),
                func.lower(ServiceRequest.title).contains(search, autoescape=True),
            )
        )
    if filters.priorities:
        values = [value for value in filters.priorities if value != "UNSET"]
        conditions.append(
            or_(
                ServiceRequest.priority.in_(values) if values else false(),
                (
                    ServiceRequest.priority.is_(None)
                    if "UNSET" in filters.priorities
                    else false()
                ),
            )
        )
    if filters.owner_user_id:
        conditions.append(
            ServiceRequest.assigned_specialist_id == filters.owner_user_id
        )
    if filters.due_before:
        conditions.append(ServiceRequest.required_by <= filters.due_before)
    return conditions


def package_filters(filters: BoardFilters) -> list[ColumnElement[bool]]:
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


def cursor_filter(
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
