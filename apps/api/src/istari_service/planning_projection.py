"""Pure projections for planning lanes, risks, conflicts and source versions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256
from math import ceil
from uuid import UUID

from istari_service.board_models import BoardColumn, WorkPackageStatus
from istari_service.board_projection import ProjectedBoardItem
from istari_service.planning_capacity_types import PlanningCapacityProjection
from istari_service.planning_evolution_types import PackagePlanningRows
from istari_service.schemas.board import BoardItemType
from istari_service.schemas.planning import (
    BlockerWarning,
    CapacityConflict,
    DependencyWarning,
    PlanningLane,
    PlanningLaneItem,
)


def lanes(
    rows: tuple[ProjectedBoardItem, ...],
    packages: PackagePlanningRows,
    blocker_ages: dict[UUID, int],
    warning_counts: dict[UUID, int],
) -> list[PlanningLane]:
    by_id = {package.id: package for package, _ in packages.packages}
    output: dict[str, list[PlanningLaneItem]] = {"requests": [], "packages": []}
    for row in rows:
        item = row.item
        if item.column in {BoardColumn.COMPLETED, BoardColumn.CANCELLED}:
            continue
        is_package = item.item_type is BoardItemType.WORK_PACKAGE
        package = by_id.get(item.id)
        output["packages" if is_package else "requests"].append(
            PlanningLaneItem(
                id=item.id,
                kind="PACKAGE" if is_package else "REQUEST",
                reference=item.reference,
                title=item.title,
                owner_display_name=item.owner_display_name,
                priority=str(item.priority),
                due_on=item.due_on,
                status=item.column,
                iteration_name=(
                    packages.iteration_names.get(package.iteration_id)
                    if package and package.iteration_id
                    else None
                ),
                blocker_age_days=blocker_ages.get(item.id),
                dependency_warning_count=warning_counts.get(item.id, 0),
            )
        )
    return [
        PlanningLane(key="requests", label="Request work", items=output["requests"]),
        PlanningLane(key="packages", label="Planning work", items=output["packages"]),
    ]


def dependency_warnings(
    rows: PackagePlanningRows,
) -> tuple[list[DependencyWarning], dict[UUID, int]]:
    packages = {item.id: item for item, _ in rows.packages}
    output: list[DependencyWarning] = []
    counts: dict[UUID, int] = {}
    for package_id, dependency in rows.dependencies:
        package = packages.get(package_id)
        if package is None or dependency is None:
            status, warning, reference = "MISSING", "Dependency is unavailable.", "-"
        elif dependency.status is WorkPackageStatus.DONE:
            continue
        elif dependency.status is WorkPackageStatus.BLOCKED:
            status, warning = "BLOCKED", "Dependency is currently blocked."
            reference = f"WP-{str(dependency.id)[:8].upper()}"
        else:
            status = "AT_RISK"
            warning = "Dependency is not complete before dependent work."
            reference = f"WP-{str(dependency.id)[:8].upper()}"
        if package is None:
            continue
        output.append(
            DependencyWarning(
                package_id=package.id,
                reference=f"WP-{str(package.id)[:8].upper()}",
                title=package.title,
                dependency_reference=reference,
                status=status,
                warning=warning,
            )
        )
        counts[package.id] = counts.get(package.id, 0) + 1
    return output, counts


def blocker_warnings(
    rows: PackagePlanningRows, now: datetime
) -> tuple[list[BlockerWarning], dict[UUID, int]]:
    packages = {item.id: item for item, _ in rows.packages}
    output: list[BlockerWarning] = []
    ages: dict[UUID, int] = {}
    for blocker in rows.blockers:
        package = packages.get(blocker.package_id)
        if package is None:
            continue
        age = max(0, (now.date() - utc(blocker.opened_at).date()).days)
        ages[package.id] = max(ages.get(package.id, 0), age)
        output.append(
            BlockerWarning(
                package_id=package.id,
                reference=f"WP-{str(package.id)[:8].upper()}",
                title=package.title,
                age_days=age,
                reason=blocker.reason,
            )
        )
    for package, _ in rows.packages:
        if package.status is not WorkPackageStatus.BLOCKED or package.id in ages:
            continue
        age = max(0, (now.date() - utc(package.updated_at).date()).days)
        ages[package.id] = age
        output.append(
            BlockerWarning(
                package_id=package.id,
                reference=f"WP-{str(package.id)[:8].upper()}",
                title=package.title,
                age_days=age,
                reason=package.blockers,
            )
        )
    return output, ages


def capacity_conflicts(
    capacity: PlanningCapacityProjection,
    demand_minutes: int,
    dependencies: list[DependencyWarning],
    starts_on: date,
) -> list[CapacityConflict]:
    workdays = max(1, sum(day.baseline_minutes > 0 for day in capacity.days))
    daily_demand = ceil(demand_minutes / workdays)
    output: list[CapacityConflict] = []
    for day in capacity.days:
        if day.baseline_minutes and day.available_minutes < daily_demand:
            output.append(
                CapacityConflict(
                    date=day.date,
                    kind="CAPACITY",
                    summary="Estimated aggregate demand exceeds available capacity.",
                )
            )
        if day.baseline_minutes and day.calendar_minutes >= day.baseline_minutes:
            output.append(
                CapacityConflict(
                    date=day.date,
                    kind="CALENDAR",
                    summary="Canonical calendar commitments use this day's capacity.",
                )
            )
        if day.baseline_minutes and day.reserved_minutes >= day.baseline_minutes:
            output.append(
                CapacityConflict(
                    date=day.date,
                    kind="RESERVATION",
                    summary="Existing package reservations use this day's capacity.",
                )
            )
        if len(output) >= 100:
            del output[100:]
            break
    remaining = max(0, 100 - len(output))
    output.extend(
        CapacityConflict(
            date=starts_on,
            kind="DEPENDENCY",
            summary=item.warning,
        )
        for item in dependencies[:remaining]
    )
    return output


def source_digest(
    items: tuple[ProjectedBoardItem, ...],
    packages: PackagePlanningRows,
    request_count: int,
    capacity_digest: str,
) -> str:
    parts = [capacity_digest, f"request-count:{request_count}"]
    parts.extend(
        f"item:{item.item.item_type}:{item.item.id}:{item.item.version}:{item.item.column}"
        for item in sorted(items, key=lambda value: str(value.item.id))
    )
    parts.extend(
        f"package:{item.id}:{item.version}:{item.remaining_effort_minutes}:{item.status}"
        for item, _ in sorted(packages.packages, key=lambda value: str(value[0].id))
    )
    return sha256("|".join(parts).encode()).hexdigest()


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
