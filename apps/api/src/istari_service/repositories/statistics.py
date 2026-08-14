"""Grant-scoped access to content-free statistics projections."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from istari_service import statistics_hierarchy
from istari_service.analytics_models import (
    AnalyticsProjectionState,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from istari_service.analytics_projection import PROJECTION_NAME
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StatisticsQueryInvalid
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
    OrganisationClosure,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationKind, OrganisationUnit
from istari_service.repositories import statistics_record_mapping
from istari_service.schemas.statistics import StatisticsScope, StatisticsUnit
from istari_service.statistics_records import StatisticsDataset

MAX_FACT_ROWS = 50_000
STATEMENT_TIMEOUT_MS = 2_000
PLATFORM_SCOPE_ID = "platform"


class SqlAlchemyStatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_scopes(
        self,
        actor: Actor,
        *,
        at: datetime | None = None,
    ) -> list[StatisticsScope]:
        effective_at = at or datetime.now(UTC)
        if actor.role is UserRole.REQUESTER:
            return []
        if actor.role is UserRole.PLATFORM_ADMIN:
            root = await self._root_unit()
            return [await self._platform_scope(root)]
        rows = (
            await self._session.execute(
                self._active_scope_query(actor.id, effective_at).order_by(
                    OrganisationUnit.sort_order,
                    ManagementGrant.id,
                )
            )
        ).all()
        return [await self._grant_scope(grant, unit) for grant, unit in rows]

    async def load_dataset(
        self,
        actor: Actor,
        *,
        scope_id: str,
        selected_unit_id: UUID | None,
        start: datetime,
        end: datetime,
        at: datetime | None = None,
    ) -> StatisticsDataset:
        await self._apply_statement_timeout()
        scope, unit = await self._resolve_scope(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            at=at or datetime.now(UTC),
        )
        unit_column = self._unit_column(unit.kind)
        fact_conditions = (
            unit_column == unit.id,
            RequestAnalyticsFact.received_at >= start,
            RequestAnalyticsFact.received_at < end,
        )
        fact_query = select(RequestAnalyticsFact).where(*fact_conditions)
        fact_rows = tuple(
            await self._session.scalars(
                fact_query.order_by(RequestAnalyticsFact.received_at).limit(
                    MAX_FACT_ROWS + 1
                )
            )
        )
        if len(fact_rows) > MAX_FACT_ROWS:
            raise StatisticsQueryInvalid("Reduce the statistics date range.")
        interval_query = (
            select(RequestStageInterval)
            .join(
                RequestAnalyticsFact,
                RequestAnalyticsFact.request_id == RequestStageInterval.request_id,
            )
            .where(*fact_conditions)
            .order_by(
                RequestStageInterval.started_at,
                RequestStageInterval.sequence,
            )
        )
        interval_rows = tuple(await self._session.scalars(interval_query))
        child_rows: tuple[OrganisationUnit, ...] = ()
        if scope.include_descendants:
            child_rows = tuple(
                await self._session.scalars(
                    select(OrganisationUnit)
                    .where(
                        OrganisationUnit.parent_id == unit.id,
                        OrganisationUnit.is_configured.is_(True),
                    )
                    .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
                )
            )
        freshness = await self._session.get(
            AnalyticsProjectionState,
            PROJECTION_NAME,
        )
        selected = statistics_hierarchy.selected_statistics_unit(scope, unit.id)
        breadcrumb = statistics_hierarchy.statistics_breadcrumb(scope, selected)
        return StatisticsDataset(
            scope,
            selected,
            breadcrumb,
            tuple(map(statistics_record_mapping.statistics_fact, fact_rows)),
            tuple(map(statistics_record_mapping.statistics_interval, interval_rows)),
            tuple(map(statistics_record_mapping.statistics_child, child_rows)),
            statistics_record_mapping.statistics_freshness(freshness),
        )

    async def authorised_scope(
        self,
        actor: Actor,
        *,
        scope_id: str,
        selected_unit_id: UUID | None = None,
        at: datetime | None = None,
    ) -> tuple[StatisticsScope, OrganisationUnit]:
        """Resolve the same active scope used by screen and export queries."""

        await self._apply_statement_timeout()
        return await self._resolve_scope(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            at=at or datetime.now(UTC),
        )

    async def _resolve_scope(
        self,
        actor: Actor,
        *,
        scope_id: str,
        selected_unit_id: UUID | None,
        at: datetime,
    ) -> tuple[StatisticsScope, OrganisationUnit]:
        if actor.role is UserRole.REQUESTER:
            raise ObjectNotFound()
        if scope_id == PLATFORM_SCOPE_ID:
            if actor.role is not UserRole.PLATFORM_ADMIN:
                raise ObjectNotFound()
            root = await self._root_unit()
            scope = await self._platform_scope(root)
            return scope, await self._select_unit(scope, root, selected_unit_id)
        try:
            grant_id = UUID(scope_id)
        except ValueError as error:
            raise ObjectNotFound() from error
        row = (
            await self._session.execute(
                self._active_scope_query(actor.id, at).where(
                    ManagementGrant.id == grant_id
                )
            )
        ).one_or_none()
        if row is None:
            raise ObjectNotFound()
        grant, unit = row
        scope = await self._grant_scope(grant, unit)
        return scope, await self._select_unit(scope, unit, selected_unit_id)

    @staticmethod
    def _active_scope_query(
        actor_id: UUID,
        at: datetime,
    ) -> Select[tuple[ManagementGrant, OrganisationUnit]]:
        return (
            select(ManagementGrant, OrganisationUnit)
            .join(User, User.id == ManagementGrant.subject_user_id)
            .join(
                ManagementGrantAction,
                ManagementGrantAction.grant_id == ManagementGrant.id,
            )
            .join(
                OrganisationUnit,
                OrganisationUnit.id == ManagementGrant.root_unit_id,
            )
            .where(
                ManagementGrant.subject_user_id == actor_id,
                ManagementGrantAction.action == ManagementAction.STATISTICS,
                ManagementGrant.effective_from <= at,
                or_(
                    ManagementGrant.effective_until.is_(None),
                    ManagementGrant.effective_until > at,
                ),
                ManagementGrant.revoked_at.is_(None),
                User.is_active.is_(True),
                OrganisationUnit.is_configured.is_(True),
            )
        )

    @staticmethod
    def _unit_column(
        kind: OrganisationKind,
    ) -> InstrumentedAttribute[UUID | None]:
        return {
            OrganisationKind.ROOT: RequestAnalyticsFact.root_unit_id,
            OrganisationKind.COMMAND: RequestAnalyticsFact.command_unit_id,
            OrganisationKind.OPS_GROUP: RequestAnalyticsFact.ops_unit_id,
            OrganisationKind.TEAM: RequestAnalyticsFact.team_unit_id,
        }[kind]

    async def _root_unit(self) -> OrganisationUnit:
        root = await self._session.scalar(
            select(OrganisationUnit).where(
                OrganisationUnit.kind == OrganisationKind.ROOT,
                OrganisationUnit.is_configured.is_(True),
            )
        )
        if root is None:
            raise ObjectNotFound()
        return root

    async def _apply_statement_timeout(self) -> None:
        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql":
            await self._session.execute(
                select(
                    func.set_config(
                        "statement_timeout",
                        str(STATEMENT_TIMEOUT_MS),
                        True,
                    )
                )
            )

    async def _platform_scope(self, root: OrganisationUnit) -> StatisticsScope:
        return StatisticsScope(
            id=PLATFORM_SCOPE_ID,
            unit_id=root.id,
            name="Whole platform",
            kind="PLATFORM",
            include_descendants=True,
            units=await self._scope_units(root, include_descendants=True),
        )

    async def _grant_scope(
        self,
        grant: ManagementGrant,
        unit: OrganisationUnit,
    ) -> StatisticsScope:
        return StatisticsScope(
            id=str(grant.id),
            unit_id=unit.id,
            name=unit.name,
            kind=unit.kind,
            include_descendants=grant.include_descendants,
            units=await self._scope_units(
                unit,
                include_descendants=grant.include_descendants,
            ),
        )

    async def _scope_units(
        self,
        root: OrganisationUnit,
        *,
        include_descendants: bool,
    ) -> list[StatisticsUnit]:
        query = (
            select(OrganisationUnit, OrganisationClosure.depth)
            .join(
                OrganisationClosure,
                OrganisationClosure.descendant_id == OrganisationUnit.id,
            )
            .where(
                OrganisationClosure.ancestor_id == root.id,
                OrganisationUnit.is_configured.is_(True),
            )
            .order_by(
                OrganisationClosure.depth,
                OrganisationUnit.sort_order,
                OrganisationUnit.id,
            )
        )
        if not include_descendants:
            query = query.where(OrganisationClosure.depth == 0)
        return [
            StatisticsUnit(
                id=unit.id,
                parent_id=unit.parent_id,
                name=unit.name,
                kind=unit.kind,
                depth=depth,
            )
            for unit, depth in (await self._session.execute(query)).all()
        ]

    async def _select_unit(
        self,
        scope: StatisticsScope,
        root: OrganisationUnit,
        selected_unit_id: UUID | None,
    ) -> OrganisationUnit:
        target_id = selected_unit_id or root.id
        if not any(unit.id == target_id for unit in scope.units):
            raise ObjectNotFound()
        selected = await self._session.get(OrganisationUnit, target_id)
        if selected is None or not selected.is_configured:
            raise ObjectNotFound()
        return selected
