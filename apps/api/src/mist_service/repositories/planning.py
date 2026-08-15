"""Bounded exact-team reads and writes for advisory planning projections."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from secrets import token_urlsafe
from typing import cast
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mist_service.analytics_models import RequestAnalyticsFact
from mist_service.board_models import (
    TeamIteration,
    WorkPackage,
    WorkPackageDependency,
)
from mist_service.models import RequestStatus, User
from mist_service.planning_analytics_models import (
    IterationSummarySnapshot,
    PackageBlocker,
    PackageChecklist,
    PackageChecklistItem,
    PackageTemplate,
    PackageTemplateChecklistItem,
    PlanningCapacityPreview,
    PlanningScenario,
    PlanningScenarioStatus,
)
from mist_service.planning_evolution_types import (
    PackagePlanningRows,
    ScenarioPreviewRecord,
)
from mist_service.schemas.planning import (
    CapacityBreakdown,
    CapacityConflict,
    CapacityScenarioCommand,
    CapacityScenarioSummary,
    ChecklistItem,
    PackageChecklistResult,
    PackageTemplateResult,
    TemplateChecklistItem,
)

PLANNING_ROW_LIMIT = 5_000
TERMINAL_REQUEST_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


class SqlAlchemyPlanningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def templates(self, team_id: UUID) -> list[PackageTemplateResult]:
        templates = list(
            await self.session.scalars(
                select(PackageTemplate)
                .where(
                    PackageTemplate.team_id == team_id,
                    PackageTemplate.is_active.is_(True),
                )
                .order_by(PackageTemplate.name, PackageTemplate.version.desc())
                .limit(PLANNING_ROW_LIMIT)
            )
        )
        item_rows = await self._template_items([item.id for item in templates])
        return [
            PackageTemplateResult(
                id=item.id,
                name=item.name,
                description=item.description,
                version=item.version,
                checklist=item_rows[item.id],
            )
            for item in templates
        ]

    async def scenarios(self, team_id: UUID) -> list[CapacityScenarioSummary]:
        rows = list(
            await self.session.scalars(
                select(PlanningScenario)
                .where(PlanningScenario.team_id == team_id)
                .order_by(PlanningScenario.updated_at.desc(), PlanningScenario.id)
                .limit(500)
            )
        )
        return [
            CapacityScenarioSummary(
                id=item.id,
                name=item.name,
                version=item.version,
                starts_on=item.starts_on,
                ends_on=item.ends_on,
                status=item.status,
                updated_at=item.updated_at,
            )
            for item in rows
        ]

    async def package_rows(self, team_id: UUID) -> PackagePlanningRows:
        package_result = await self.session.execute(
            select(WorkPackage, User.display_name)
            .join(User, User.id == WorkPackage.owner_user_id)
            .where(WorkPackage.team_id == team_id)
            .order_by(WorkPackage.due_on, WorkPackage.id)
            .limit(PLANNING_ROW_LIMIT)
        )
        package_rows: tuple[tuple[WorkPackage, str], ...] = tuple(
            (row[0], row[1]) for row in package_result.all()
        )
        package_ids = [row[0].id for row in package_rows]
        if not package_ids:
            return PackagePlanningRows((), {}, (), (), ())
        iteration_result = await self.session.execute(
            select(TeamIteration.id, TeamIteration.name).where(
                TeamIteration.team_id == team_id
            )
        )
        iteration_names: dict[UUID, str] = {
            row[0]: row[1] for row in iteration_result.all()
        }
        dependency = aliased(WorkPackage)
        dependency_result = await self.session.execute(
            select(WorkPackageDependency.package_id, dependency)
            .outerjoin(
                dependency,
                dependency.id == WorkPackageDependency.depends_on_id,
            )
            .where(WorkPackageDependency.package_id.in_(package_ids))
        )
        dependencies: tuple[tuple[UUID, WorkPackage | None], ...] = tuple(
            (row[0], cast(WorkPackage | None, row[1]))
            for row in dependency_result.all()
        )
        blockers = tuple(
            await self.session.scalars(
                select(PackageBlocker)
                .where(
                    PackageBlocker.team_id == team_id,
                    PackageBlocker.resolved_at.is_(None),
                )
                .order_by(PackageBlocker.opened_at, PackageBlocker.id)
                .limit(PLANNING_ROW_LIMIT)
            )
        )
        checklists = tuple(await self._checklists(package_rows, package_ids))
        return PackagePlanningRows(
            package_rows, iteration_names, dependencies, blockers, checklists
        )

    async def request_work_count(self, team_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count(RequestAnalyticsFact.request_id)).where(
                RequestAnalyticsFact.team_unit_id == team_id,
                RequestAnalyticsFact.current_status.not_in(TERMINAL_REQUEST_STATUSES),
            )
        )
        return int(value or 0)

    async def current_iteration(
        self, team_id: UUID
    ) -> tuple[TeamIteration, IterationSummarySnapshot | None] | None:
        iteration = await self.session.scalar(
            select(TeamIteration)
            .where(TeamIteration.team_id == team_id)
            .order_by(
                case(
                    (TeamIteration.status == "ACTIVE", 0),
                    (TeamIteration.status == "PLANNED", 1),
                    else_=2,
                ),
                TeamIteration.starts_on.desc(),
                TeamIteration.id,
            )
            .limit(1)
        )
        if iteration is None:
            return None
        summary = await self.session.scalar(
            select(IterationSummarySnapshot)
            .where(IterationSummarySnapshot.iteration_id == iteration.id)
            .order_by(
                IterationSummarySnapshot.source_version.desc(),
                IterationSummarySnapshot.id,
            )
            .limit(1)
        )
        return iteration, summary

    async def create_scenario_preview(
        self,
        *,
        actor_id: UUID,
        team_id: UUID,
        command: CapacityScenarioCommand,
        source_version: int,
        source_digest: str,
        baseline: CapacityBreakdown,
        scenario_value: CapacityBreakdown,
        conflicts: list[CapacityConflict],
        expires_at: datetime,
    ) -> ScenarioPreviewRecord:
        last_version = await self.session.scalar(
            select(func.max(PlanningScenario.version)).where(
                PlanningScenario.team_id == team_id,
                PlanningScenario.name == command.name,
            )
        )
        scenario = PlanningScenario(
            team_id=team_id,
            name=command.name,
            starts_on=command.starts_on,
            ends_on=command.ends_on,
            planned_minutes=command.planned_minutes,
            status=PlanningScenarioStatus.PREVIEWED,
            source_version=source_version,
            source_digest=source_digest,
            created_by_user_id=actor_id,
            version=int(last_version or 0) + 1,
        )
        self.session.add(scenario)
        await self.session.flush()
        preview = PlanningCapacityPreview(
            scenario_id=scenario.id,
            team_id=team_id,
            created_by_user_id=actor_id,
            token=token_urlsafe(32),
            source_version=source_version,
            source_digest=source_digest,
            baseline=baseline.model_dump(mode="json"),
            scenario=scenario_value.model_dump(mode="json"),
            conflicts=[item.model_dump(mode="json") for item in conflicts],
            expires_at=expires_at,
        )
        self.session.add(preview)
        await self.session.flush()
        return ScenarioPreviewRecord(
            token=preview.token,
            expires_at=preview.expires_at,
            source_version=preview.source_version,
        )

    async def _template_items(
        self, template_ids: list[UUID]
    ) -> defaultdict[UUID, list[TemplateChecklistItem]]:
        grouped: defaultdict[UUID, list[TemplateChecklistItem]] = defaultdict(list)
        if not template_ids:
            return grouped
        rows = await self.session.scalars(
            select(PackageTemplateChecklistItem)
            .where(PackageTemplateChecklistItem.template_id.in_(template_ids))
            .order_by(
                PackageTemplateChecklistItem.template_id,
                PackageTemplateChecklistItem.position,
            )
        )
        for item in rows:
            grouped[item.template_id].append(
                TemplateChecklistItem(
                    id=item.id, label=item.label, required=item.required
                )
            )
        return grouped

    async def _checklists(
        self,
        package_rows: tuple[tuple[WorkPackage, str], ...],
        package_ids: list[UUID],
    ) -> list[PackageChecklistResult]:
        titles = {item.id: item.title for item, _ in package_rows}
        checklists = list(
            await self.session.scalars(
                select(PackageChecklist)
                .where(PackageChecklist.package_id.in_(package_ids))
                .order_by(PackageChecklist.package_id)
            )
        )
        grouped: defaultdict[UUID, list[ChecklistItem]] = defaultdict(list)
        if checklists:
            rows = await self.session.scalars(
                select(PackageChecklistItem)
                .where(
                    PackageChecklistItem.checklist_id.in_(
                        [item.id for item in checklists]
                    )
                )
                .order_by(
                    PackageChecklistItem.checklist_id,
                    PackageChecklistItem.position,
                )
            )
            for item in rows:
                grouped[item.checklist_id].append(
                    ChecklistItem(
                        id=item.id,
                        label=item.label,
                        required=item.required,
                        completed=item.completed_at is not None,
                    )
                )
        return [
            PackageChecklistResult(
                package_id=item.package_id,
                package_title=titles[item.package_id],
                template_name=item.template_name,
                completed_count=sum(row.completed for row in grouped[item.id]),
                total_count=len(grouped[item.id]),
                items=grouped[item.id],
            )
            for item in checklists
        ]
