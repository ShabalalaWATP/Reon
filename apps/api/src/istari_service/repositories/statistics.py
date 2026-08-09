"""Grant-scoped access to content-free statistics projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

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
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationKind, OrganisationUnit
from istari_service.schemas.statistics import StatisticsScope

MAX_FACT_ROWS = 50_000
STATEMENT_TIMEOUT_MS = 2_000
PLATFORM_SCOPE_ID = "platform"


@dataclass(frozen=True, slots=True)
class StatisticsDataset:
    scope: StatisticsScope
    facts: tuple[RequestAnalyticsFact, ...]
    intervals: tuple[RequestStageInterval, ...]
    children: tuple[OrganisationUnit, ...]
    freshness: AnalyticsProjectionState | None


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
        if actor.role is UserRole.PLATFORM_ADMIN:
            root = await self._root_unit()
            return [self._platform_scope(root)]
        rows = (
            await self._session.execute(
                self._active_scope_query(actor.id, effective_at).order_by(
                    OrganisationUnit.sort_order,
                    ManagementGrant.id,
                )
            )
        ).all()
        return [self._grant_scope(grant, unit) for grant, unit in rows]

    async def load_dataset(
        self,
        actor: Actor,
        *,
        scope_id: str,
        start: datetime,
        end: datetime,
        at: datetime | None = None,
    ) -> StatisticsDataset:
        await self._apply_statement_timeout()
        scope, unit = await self._resolve_scope(
            actor,
            scope_id=scope_id,
            at=at or datetime.now(UTC),
        )
        unit_column = self._unit_column(unit.kind)
        fact_conditions = (
            unit_column == unit.id,
            RequestAnalyticsFact.received_at >= start,
            RequestAnalyticsFact.received_at < end,
        )
        fact_query = select(RequestAnalyticsFact).where(*fact_conditions)
        facts = tuple(
            await self._session.scalars(
                fact_query.order_by(RequestAnalyticsFact.received_at).limit(
                    MAX_FACT_ROWS + 1
                )
            )
        )
        if len(facts) > MAX_FACT_ROWS:
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
        intervals = tuple(await self._session.scalars(interval_query))
        children: tuple[OrganisationUnit, ...] = ()
        if scope.include_descendants:
            children = tuple(
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
        return StatisticsDataset(scope, facts, intervals, children, freshness)

    async def authorised_scope(
        self,
        actor: Actor,
        *,
        scope_id: str,
        at: datetime | None = None,
    ) -> tuple[StatisticsScope, OrganisationUnit]:
        """Resolve the same active scope used by screen and export queries."""

        await self._apply_statement_timeout()
        return await self._resolve_scope(
            actor,
            scope_id=scope_id,
            at=at or datetime.now(UTC),
        )

    async def _resolve_scope(
        self,
        actor: Actor,
        *,
        scope_id: str,
        at: datetime,
    ) -> tuple[StatisticsScope, OrganisationUnit]:
        if scope_id == PLATFORM_SCOPE_ID:
            if actor.role is not UserRole.PLATFORM_ADMIN:
                raise ObjectNotFound()
            root = await self._root_unit()
            return self._platform_scope(root), root
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
        return self._grant_scope(grant, unit), unit

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

    @staticmethod
    def _platform_scope(root: OrganisationUnit) -> StatisticsScope:
        return StatisticsScope(
            id=PLATFORM_SCOPE_ID,
            unit_id=root.id,
            name="Whole platform",
            kind="PLATFORM",
            include_descendants=True,
        )

    @staticmethod
    def _grant_scope(
        grant: ManagementGrant,
        unit: OrganisationUnit,
    ) -> StatisticsScope:
        return StatisticsScope(
            id=str(grant.id),
            unit_id=unit.id,
            name=unit.name,
            kind=unit.kind,
            include_descendants=grant.include_descendants,
        )
