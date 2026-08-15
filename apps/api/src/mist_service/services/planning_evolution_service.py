"""Advisory planning cockpit assembled from authoritative source records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from mist_service.board_models import BoardColumn, IterationStatus, WorkPackageStatus
from mist_service.board_projection import ProjectedBoardItem
from mist_service.domain import Actor
from mist_service.errors import StaleVersion
from mist_service.management_models import ManagementAction
from mist_service.planning_capacity_types import PlanningCapacityProjection
from mist_service.planning_evolution_types import PackagePlanningRows
from mist_service.planning_projection import (
    blocker_warnings,
    capacity_conflicts,
    dependency_warnings,
    lanes,
    source_digest,
    utc,
)
from mist_service.schemas.planning import (
    CapacityBreakdown,
    CapacityScenarioCommand,
    CapacityScenarioList,
    CapacityScenarioPreview,
    IterationProjection,
    PackageTemplateList,
    PlanningCockpit,
    PlanningFreshness,
    PlanningSummary,
)
from mist_service.services.planning_evolution_ports import (
    PlanningAccessPolicy,
    PlanningBoardReader,
    PlanningCapacityReader,
    PlanningFreshnessReader,
    PlanningQueryReader,
    PlanningScenarioWriter,
)

COCKPIT_CAPACITY_DAYS = 14
REQUEST_WORK_ESTIMATE_MINUTES = 450
PREVIEW_TTL = timedelta(minutes=10)
TERMINAL_PACKAGE_STATUSES = {WorkPackageStatus.DONE, WorkPackageStatus.CANCELLED}


@dataclass(frozen=True, slots=True)
class _Snapshot:
    items: tuple[ProjectedBoardItem, ...]
    packages: PackagePlanningRows
    request_work_count: int
    capacity: PlanningCapacityProjection
    source_digest: str
    source_version: int


class PlanningEvolutionService:
    def __init__(
        self,
        *,
        access: PlanningAccessPolicy,
        board: PlanningBoardReader,
        queries: PlanningQueryReader,
        scenarios: PlanningScenarioWriter,
        capacity: PlanningCapacityReader,
        freshness: PlanningFreshnessReader,
    ) -> None:
        self._access = access
        self._board = board
        self._queries = queries
        self._scenarios = scenarios
        self._capacity = capacity
        self._freshness_reader = freshness

    async def cockpit(
        self, actor: Actor, team_id: UUID, *, now: datetime | None = None
    ) -> PlanningCockpit:
        await self._access.authorise_read(actor, team_id, ManagementAction.BOARD)
        await self._access.authorise_read(actor, team_id, ManagementAction.CAPACITY)
        effective_now = now or datetime.now(UTC)
        snapshot = await self._snapshot(team_id, effective_now.date())
        warnings, warning_counts = dependency_warnings(snapshot.packages)
        blockers, blocker_ages = blocker_warnings(snapshot.packages, effective_now)
        lane_rows = lanes(
            snapshot.items,
            snapshot.packages,
            blocker_ages,
            warning_counts,
        )
        iteration = await self._iteration(team_id, snapshot.packages)
        active_items = [
            item
            for item in snapshot.items
            if item.item.column not in {BoardColumn.COMPLETED, BoardColumn.CANCELLED}
        ]
        freshness = await self._freshness(snapshot.source_version, effective_now)
        return PlanningCockpit(
            team_id=team_id,
            generated_at=effective_now,
            freshness=freshness,
            summary=PlanningSummary(
                backlog_count=sum(
                    item.item.column
                    in {
                        BoardColumn.BACKLOG,
                        BoardColumn.AWAITING_ASSIGNMENT,
                        BoardColumn.READY,
                    }
                    for item in active_items
                ),
                active_iteration_count=int(
                    iteration is not None and iteration.status == IterationStatus.ACTIVE
                ),
                due_risk_count=sum(
                    item.item.due_on <= effective_now.date() + timedelta(days=7)
                    for item in active_items
                ),
                wip_count=sum(
                    item.item.column
                    not in {
                        BoardColumn.BACKLOG,
                        BoardColumn.AWAITING_ASSIGNMENT,
                        BoardColumn.READY,
                    }
                    for item in active_items
                ),
                blocked_count=sum(
                    item.item.column is BoardColumn.BLOCKED for item in active_items
                ),
                available_minutes=snapshot.capacity.available_minutes,
                reserved_minutes=snapshot.capacity.reserved_minutes,
            ),
            lanes=lane_rows,
            blockers=blockers,
            dependencies=warnings,
            iteration=iteration,
            checklists=list(snapshot.packages.checklists),
        )

    async def templates(self, actor: Actor, team_id: UUID) -> PackageTemplateList:
        await self._access.authorise_read(actor, team_id, ManagementAction.BOARD)
        return PackageTemplateList(items=await self._queries.templates(team_id))

    async def scenarios(self, actor: Actor, team_id: UUID) -> CapacityScenarioList:
        await self._access.authorise_read(actor, team_id, ManagementAction.CAPACITY)
        return CapacityScenarioList(items=await self._queries.scenarios(team_id))

    async def preview_scenario(
        self,
        actor: Actor,
        team_id: UUID,
        command: CapacityScenarioCommand,
        *,
        now: datetime | None = None,
    ) -> CapacityScenarioPreview:
        await self._access.authorise_preview(actor, team_id, command.grant_id)
        effective_now = now or datetime.now(UTC)
        snapshot = await self._snapshot(team_id, effective_now.date())
        if command.expected_source_version != snapshot.source_version:
            raise StaleVersion("Planning sources changed. Refresh and try again.")
        capacity = await self._capacity.capacity(
            team_id, command.starts_on, command.ends_on
        )
        package_minutes = sum(
            package.remaining_effort_minutes
            for package, _ in snapshot.packages.packages
            if package.status not in TERMINAL_PACKAGE_STATUSES
        )
        request_minutes = snapshot.request_work_count * REQUEST_WORK_ESTIMATE_MINUTES
        baseline = CapacityBreakdown(
            available_minutes=capacity.available_minutes,
            reserved_minutes=capacity.reserved_minutes,
            request_work_minutes=request_minutes,
            package_minutes=package_minutes,
            net_minutes=capacity.available_minutes - request_minutes - package_minutes,
        )
        scenario_value = CapacityBreakdown(
            available_minutes=baseline.available_minutes,
            reserved_minutes=baseline.reserved_minutes,
            request_work_minutes=baseline.request_work_minutes,
            package_minutes=baseline.package_minutes + command.planned_minutes,
            net_minutes=baseline.net_minutes - command.planned_minutes,
        )
        dependencies, _ = dependency_warnings(snapshot.packages)
        conflicts = capacity_conflicts(
            capacity,
            request_minutes + package_minutes + command.planned_minutes,
            dependencies,
            command.starts_on,
        )
        scenario_digest = sha256(
            f"{snapshot.source_digest}|{capacity.source_digest}".encode()
        ).hexdigest()
        preview = await self._scenarios.create_scenario_preview(
            actor_id=actor.id,
            team_id=team_id,
            command=command,
            source_version=snapshot.source_version,
            source_digest=scenario_digest,
            baseline=baseline,
            scenario_value=scenario_value,
            conflicts=conflicts,
            expires_at=effective_now + PREVIEW_TTL,
        )
        return CapacityScenarioPreview(
            token=preview.token,
            expires_at=preview.expires_at,
            source_version=preview.source_version,
            baseline=baseline,
            scenario=scenario_value,
            conflicts=conflicts,
            estimate_label=(
                "Deterministic advisory estimate using current membership, calendar "
                "availability, active request work, packages and reservations."
            ),
        )

    async def _snapshot(self, team_id: UUID, today: date) -> _Snapshot:
        items = tuple(await self._board.projected_items(team_id))
        packages = await self._queries.package_rows(team_id)
        request_count = await self._queries.request_work_count(team_id)
        capacity = await self._capacity.capacity(
            team_id,
            today,
            today + timedelta(days=COCKPIT_CAPACITY_DAYS - 1),
        )
        digest = source_digest(items, packages, request_count, capacity.source_digest)
        return _Snapshot(
            items=items,
            packages=packages,
            request_work_count=request_count,
            capacity=capacity,
            source_digest=digest,
            source_version=int(digest[:7], 16) + 1,
        )

    async def _freshness(self, source_version: int, now: datetime) -> PlanningFreshness:
        state = await self._freshness_reader.freshness()
        if state.rebuilding:
            return PlanningFreshness(
                health="REBUILDING",
                label="Request projection is rebuilding",
                source_version=source_version,
            )
        projected_at = state.last_projected_at
        if projected_at is None or utc(projected_at) < now - timedelta(minutes=15):
            return PlanningFreshness(
                health="STALE",
                label="Request projection may be stale",
                source_version=source_version,
            )
        return PlanningFreshness(
            health="READY",
            label="Current source projection",
            source_version=source_version,
        )

    async def _iteration(
        self, team_id: UUID, rows: PackagePlanningRows
    ) -> IterationProjection | None:
        current = await self._queries.current_iteration(team_id)
        if current is None:
            return None
        iteration, snapshot = current
        packages = [
            package
            for package, _ in rows.packages
            if package.iteration_id == iteration.id
        ]
        committed_packages = len(packages)
        completed = [item for item in packages if item.status is WorkPackageStatus.DONE]
        committed_points = sum(item.estimate_points for item in packages)
        completed_points = sum(item.estimate_points for item in completed)
        factual_summary = snapshot.factual_summary if snapshot else None
        if factual_summary is None and iteration.status is IterationStatus.CLOSED:
            factual_summary = (
                f"{len(completed)} of {committed_packages} packages completed; "
                f"{completed_points} of {committed_points} points completed."
            )
        return IterationProjection(
            id=iteration.id,
            name=iteration.name,
            goal=iteration.goal,
            starts_on=iteration.starts_on,
            ends_on=iteration.ends_on,
            status=iteration.status,
            committed_points=committed_points,
            completed_points=completed_points,
            committed_packages=committed_packages,
            completed_packages=len(completed),
            factual_summary=factual_summary,
        )
