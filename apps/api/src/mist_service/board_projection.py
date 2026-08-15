"""Pure workflow and package projection rules for the team board."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from mist_service.board_models import BoardColumn, WorkPackage, WorkPackageStatus
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.board import BoardFilters, BoardItem, BoardItemType

REQUEST_COLUMNS = {
    RequestStatus.DELIVERY_PLANNING: BoardColumn.AWAITING_ASSIGNMENT,
    RequestStatus.IN_PROGRESS: BoardColumn.IN_PROGRESS,
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: BoardColumn.BLOCKED,
    RequestStatus.LEAD_REVIEW: BoardColumn.MANAGER_REVIEW,
    RequestStatus.QUALITY_REVIEW: BoardColumn.QUALITY_REVIEW,
    RequestStatus.READY_FOR_RELEASE: BoardColumn.QUALITY_REVIEW,
    RequestStatus.REWORK_REQUIRED: BoardColumn.REWORK,
    RequestStatus.ON_HOLD: BoardColumn.ON_HOLD,
    RequestStatus.COMPLETED: BoardColumn.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED: BoardColumn.CANCELLED,
    RequestStatus.CANCELLED: BoardColumn.CANCELLED,
}
PACKAGE_COLUMNS = {
    WorkPackageStatus.BACKLOG: BoardColumn.BACKLOG,
    WorkPackageStatus.READY: BoardColumn.READY,
    WorkPackageStatus.IN_PROGRESS: BoardColumn.IN_PROGRESS,
    WorkPackageStatus.BLOCKED: BoardColumn.BLOCKED,
    WorkPackageStatus.DONE: BoardColumn.COMPLETED,
    WorkPackageStatus.CANCELLED: BoardColumn.CANCELLED,
}
PACKAGE_TRANSITIONS = {
    WorkPackageStatus.BACKLOG: {WorkPackageStatus.READY, WorkPackageStatus.CANCELLED},
    WorkPackageStatus.READY: {
        WorkPackageStatus.BACKLOG,
        WorkPackageStatus.IN_PROGRESS,
        WorkPackageStatus.BLOCKED,
        WorkPackageStatus.CANCELLED,
    },
    WorkPackageStatus.IN_PROGRESS: {
        WorkPackageStatus.READY,
        WorkPackageStatus.BLOCKED,
        WorkPackageStatus.DONE,
        WorkPackageStatus.CANCELLED,
    },
    WorkPackageStatus.BLOCKED: {
        WorkPackageStatus.READY,
        WorkPackageStatus.IN_PROGRESS,
        WorkPackageStatus.CANCELLED,
    },
    WorkPackageStatus.DONE: {WorkPackageStatus.IN_PROGRESS},
    WorkPackageStatus.CANCELLED: {WorkPackageStatus.BACKLOG},
}


@dataclass(frozen=True, slots=True)
class ProjectedBoardItem:
    item: BoardItem
    changed_at: datetime

    @property
    def key(self) -> tuple[datetime, str, str]:
        return self.changed_at, self.item.item_type.value, str(self.item.id)


def request_projection(
    request: ServiceRequest, owner_name: str | None
) -> ProjectedBoardItem | None:
    column = REQUEST_COLUMNS.get(request.status)
    if column is None:
        return None
    return ProjectedBoardItem(
        item=BoardItem(
            id=request.id,
            item_type=BoardItemType.SERVICE_REQUEST,
            reference=request.reference,
            title=request.title,
            column=column,
            priority=request.priority or "UNSET",
            due_on=request.required_by,
            owner_user_id=request.assigned_specialist_id,
            owner_display_name=owner_name,
            version=request.version,
            linked_request_id=request.id,
            available_columns=[],
            changed_at=_utc(request.updated_at),
        ),
        changed_at=_utc(request.updated_at),
    )


def package_projection(package: WorkPackage, owner_name: str) -> ProjectedBoardItem:
    return ProjectedBoardItem(
        item=BoardItem(
            id=package.id,
            item_type=BoardItemType.WORK_PACKAGE,
            reference=f"WP-{str(package.id)[:8].upper()}",
            title=package.title,
            column=PACKAGE_COLUMNS[package.status],
            priority=package.priority,
            due_on=package.due_on,
            owner_user_id=package.owner_user_id,
            owner_display_name=owner_name,
            version=package.version,
            linked_request_id=package.linked_request_id,
            available_columns=[
                PACKAGE_COLUMNS[item] for item in PACKAGE_TRANSITIONS[package.status]
            ],
            changed_at=_utc(package.updated_at),
        ),
        changed_at=_utc(package.updated_at),
    )


def apply_filters(
    rows: list[ProjectedBoardItem], filters: BoardFilters
) -> list[ProjectedBoardItem]:
    search = filters.search.strip().casefold()
    return [
        row
        for row in rows
        if (not search or search in f"{row.item.reference} {row.item.title}".casefold())
        and (not filters.columns or row.item.column in filters.columns)
        and (not filters.priorities or row.item.priority in filters.priorities)
        and (
            not filters.owner_user_id or row.item.owner_user_id == filters.owner_user_id
        )
        and (not filters.item_types or row.item.item_type in filters.item_types)
        and (not filters.due_before or row.item.due_on <= filters.due_before)
    ]


def paginate(
    rows: list[ProjectedBoardItem], cursor: str | None, limit: int
) -> tuple[list[BoardItem], str | None]:
    ordered = sorted(rows, key=lambda row: row.key, reverse=True)
    if cursor:
        cursor_key = decode_cursor(cursor)
        ordered = [row for row in ordered if row.key < cursor_key]
    page = ordered[: limit + 1]
    has_more = len(page) > limit
    page = page[:limit]
    next_cursor = encode_cursor(page[-1]) if has_more and page else None
    return [row.item for row in page], next_cursor


def encode_cursor(row: ProjectedBoardItem) -> str:
    value = f"{row.changed_at.isoformat()}|{row.item.item_type.value}|{row.item.id}"
    return urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str, str]:
    padded = value + "=" * (-len(value) % 4)
    timestamp, item_type, item_id = urlsafe_b64decode(padded).decode().split("|", 2)
    return datetime.fromisoformat(timestamp), item_type, str(UUID(item_id))


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
