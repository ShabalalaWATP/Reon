"""Pure board projection, cursor and contract boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from mist_service.board_models import (
    BoardColumn,
    WorkPackage,
    WorkPackagePriority,
    WorkPackageStatus,
)
from mist_service.board_policy import require
from mist_service.board_projection import (
    PACKAGE_COLUMNS,
    ProjectedBoardItem,
    apply_filters,
    decode_cursor,
    encode_cursor,
    package_projection,
    paginate,
    request_projection,
)
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.board import (
    BoardConfigurationCommand,
    BoardFilters,
    BoardItem,
    BoardItemType,
    IterationCommand,
    ReservationCommand,
    WorkPackageCommand,
    normalise_filters,
)


def request(status: RequestStatus, *, aware: bool = True) -> ServiceRequest:
    now = datetime.now(UTC)
    return ServiceRequest(
        id=uuid4(),
        requester_id=uuid4(),
        reference=f"SR-{uuid4().hex[:8]}",
        title="Synthetic board request",
        service_category="Research support",
        description="A complete synthetic request for projection testing.",
        question_to_answer="What does the synthetic evidence show?",
        desired_outcome="A useful fictional result.",
        background_context="Synthetic context only.",
        subject_area_or_location="Synthetic subject area",
        coverage_start=now.date(),
        coverage_end=now.date() + timedelta(days=1),
        customer_urgency="ROUTINE",
        supported_activity_or_decision="A fictional planning decision.",
        required_by=now.date() + timedelta(days=4),
        required_by_reason="Needed for a fictional review.",
        preferred_deliverable_type="Written product",
        success_criteria="All fictional points are covered.",
        constraints_or_caveats="No known constraints.",
        supporting_information="No supporting material is available.",
        sensitivity="STANDARD",
        handling_instructions="Synthetic content only.",
        status=status,
        current_owner="SSG Team",
        priority="HIGH",
        updated_at=now if aware else now.replace(tzinfo=None),
        version=2,
    )


def package(status: WorkPackageStatus) -> WorkPackage:
    now = datetime.now(UTC)
    return WorkPackage(
        id=uuid4(),
        team_id=uuid4(),
        linked_request_id=None,
        iteration_id=None,
        title="Synthetic projected package",
        description="Complete fictional work package detail.",
        owner_user_id=uuid4(),
        estimate_points=2,
        remaining_effort_minutes=90,
        due_on=now.date() + timedelta(days=3),
        priority=WorkPackagePriority.MEDIUM,
        status=status,
        blockers="No known blockers.",
        acceptance_criteria="The synthetic output is complete.",
        created_by_user_id=uuid4(),
        updated_at=now,
        version=1,
    )


def item(
    *,
    column: BoardColumn = BoardColumn.READY,
    priority: str = "HIGH",
    owner_id: UUID | None = None,
    item_type: BoardItemType = BoardItemType.WORK_PACKAGE,
    days: int = 1,
    title: str = "Synthetic card",
) -> ProjectedBoardItem:
    identity = uuid4()
    return ProjectedBoardItem(
        BoardItem(
            id=identity,
            itemType=item_type,
            reference=f"WP-{str(identity)[:8]}",
            title=title,
            column=column,
            priority=priority,
            dueOn=datetime.now(UTC).date() + timedelta(days=days),
            ownerUserId=owner_id,
            ownerDisplayName="Synthetic Owner" if owner_id else None,
            version=1,
            linkedRequestId=None,
            availableColumns=[],
            changedAt=datetime.now(UTC),
        ),
        datetime.now(UTC) + timedelta(seconds=days),
    )


def valid_package_command() -> dict[str, object]:
    return {
        "title": "Valid synthetic package",
        "description": "Full detail.",
        "ownerUserId": uuid4(),
        "contributorIds": [uuid4()],
        "estimatePoints": 3,
        "remainingEffortMinutes": 30,
        "dueOn": datetime.now(UTC).date(),
        "priority": "LOW",
        "blockers": "None.",
        "acceptanceCriteria": "Complete.",
        "linkedRequestId": None,
        "dependencyIds": [uuid4()],
        "iterationId": None,
    }


def test_request_and_package_projection_rules_are_complete() -> None:
    projected_statuses = {
        RequestStatus.DELIVERY_PLANNING,
        RequestStatus.IN_PROGRESS,
        RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        RequestStatus.LEAD_REVIEW,
        RequestStatus.QUALITY_REVIEW,
        RequestStatus.READY_FOR_RELEASE,
        RequestStatus.REWORK_REQUIRED,
        RequestStatus.ON_HOLD,
        RequestStatus.COMPLETED,
        RequestStatus.CLOSED_NOT_PROGRESSED,
        RequestStatus.CANCELLED,
    }
    for status in projected_statuses:
        result = request_projection(request(status, aware=False), None)
        assert result is not None
        assert result.item.available_columns == []
        assert result.changed_at.tzinfo is UTC
    assert request_projection(request(RequestStatus.ROUTING_PENDING), None) is None

    for status, column in PACKAGE_COLUMNS.items():
        result = package_projection(package(status), "Synthetic Owner")
        assert result.item.column is column
        assert result.item.available_columns


def test_filters_and_keyset_pagination_compose_without_leaking_rows() -> None:
    owner = uuid4()
    wanted = item(owner_id=owner, title="Urgent customer product")
    rows = [
        wanted,
        item(column=BoardColumn.BLOCKED),
        item(priority="LOW"),
        item(owner_id=uuid4()),
        item(item_type=BoardItemType.SERVICE_REQUEST),
        item(days=30),
    ]
    filters = BoardFilters(
        search="customer",
        columns=[BoardColumn.READY],
        priorities=["HIGH"],
        ownerUserId=owner,
        itemTypes=[BoardItemType.WORK_PACKAGE],
        dueBefore=datetime.now(UTC).date() + timedelta(days=2),
    )
    assert apply_filters(rows, filters) == [wanted]
    assert apply_filters(rows, BoardFilters()) == rows

    first_page, cursor = paginate(rows, None, 2)
    assert len(first_page) == 2
    assert cursor is not None
    second_page, second_cursor = paginate(rows, cursor, 10)
    assert first_page[0].id not in {value.id for value in second_page}
    assert second_cursor is None
    encoded = encode_cursor(wanted)
    decoded = decode_cursor(encoded)
    assert decoded == wanted.key
    with pytest.raises((ValueError, UnicodeError)):
        decode_cursor("not-a-valid-cursor")


def test_board_contracts_reject_ambiguous_or_unbounded_planning() -> None:
    body = valid_package_command()
    WorkPackageCommand.model_validate(body)
    body["contributorIds"] = [body["ownerUserId"], body["ownerUserId"]]
    with pytest.raises(ValidationError, match="Contributors must be unique"):
        WorkPackageCommand.model_validate(body)
    body = valid_package_command()
    dependency = body["dependencyIds"]
    assert isinstance(dependency, list)
    body["dependencyIds"] = [dependency[0]] * 2
    with pytest.raises(ValidationError, match="Dependencies must be unique"):
        WorkPackageCommand.model_validate(body)

    BoardConfigurationCommand(
        grantId=uuid4(), expectedVersion=0, wipLimits={BoardColumn.READY: 2}
    )
    with pytest.raises(ValidationError, match="active delivery columns"):
        BoardConfigurationCommand(
            grantId=uuid4(), expectedVersion=0, wipLimits={BoardColumn.BACKLOG: 2}
        )

    now = datetime.now(UTC)
    ReservationCommand(
        userId=uuid4(),
        startsAt=now,
        endsAt=now + timedelta(hours=1),
        reason="A valid capacity reservation reason.",
    )
    invalid_windows = (
        (now.replace(tzinfo=None), now.replace(tzinfo=None) + timedelta(hours=1)),
        (now, now),
        (now, now + timedelta(days=32)),
    )
    for start, end in invalid_windows:
        with pytest.raises(ValidationError):
            ReservationCommand(
                userId=uuid4(),
                startsAt=start,
                endsAt=end,
                reason="An invalid capacity reservation boundary.",
            )

    IterationCommand(
        grantId=uuid4(),
        name="Valid iteration",
        goal="A valid fictional goal.",
        startsOn=datetime.now(UTC).date(),
        endsOn=datetime.now(UTC).date() + timedelta(days=14),
    )
    for start, end in (
        (datetime.now(UTC).date(), datetime.now(UTC).date() - timedelta(days=1)),
        (datetime.now(UTC).date(), datetime.now(UTC).date() + timedelta(days=91)),
    ):
        with pytest.raises(ValidationError):
            IterationCommand(
                grantId=uuid4(),
                name="Invalid iteration",
                goal="An invalid fictional goal.",
                startsOn=start,
                endsOn=end,
            )

    assert normalise_filters({"search": " test "}).search == " test "
    require(True, RuntimeError("unused"))
    with pytest.raises(RuntimeError, match="required"):
        require(False, RuntimeError("required"))
