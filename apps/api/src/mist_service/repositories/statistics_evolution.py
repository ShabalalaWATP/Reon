"""Grant-scoped content-free fact reads and controlled export records."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from mist_service.analytics_evolution_models import (
    AnalyticsAggregateExport,
    AnalyticsExportAuditEvent,
    AnalyticsExportStatus,
    OperationalAnalyticsFact,
)
from mist_service.domain import Actor
from mist_service.errors import StatisticsQueryInvalid
from mist_service.organisation_models import OrganisationKind
from mist_service.repositories.statistics import (
    MAX_FACT_ROWS,
    PLATFORM_SCOPE_ID,
    SqlAlchemyStatisticsRepository,
)
from mist_service.repositories.statistics_record_mapping import (
    operational_statistics_fact,
)
from mist_service.schemas.statistics_evolution import StatisticsExportCommand
from mist_service.statistics_records import StatisticsEvolutionDataset


class SqlAlchemyStatisticsEvolutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._base = SqlAlchemyStatisticsRepository(session)

    async def load(
        self,
        actor: Actor,
        *,
        scope_id: str,
        start: datetime,
        end: datetime,
        previous_start: datetime,
        previous_end: datetime,
        at: datetime,
        selected_unit_id: UUID | None = None,
    ) -> StatisticsEvolutionDataset:
        current = await self._base.load_dataset(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            start=start,
            end=end,
            at=at,
        )
        previous = await self._base.load_dataset(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            start=previous_start,
            end=previous_end,
            at=at,
        )
        _, unit = await self._base.authorised_scope(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            at=at,
        )
        unit_column = _operational_unit_column(unit.kind)
        fact_rows = tuple(
            await self.session.scalars(
                select(OperationalAnalyticsFact)
                .where(
                    unit_column == unit.id,
                    OperationalAnalyticsFact.occurred_at >= start,
                    OperationalAnalyticsFact.occurred_at < end,
                )
                .order_by(
                    OperationalAnalyticsFact.occurred_at,
                    OperationalAnalyticsFact.id,
                )
                .limit(MAX_FACT_ROWS + 1)
            )
        )
        if len(fact_rows) > MAX_FACT_ROWS:
            raise StatisticsQueryInvalid("Reduce the statistics date range.")
        return StatisticsEvolutionDataset(
            current,
            previous,
            tuple(map(operational_statistics_fact, fact_rows)),
        )

    async def record_denied_export(
        self,
        *,
        actor: Actor,
        command: StatisticsExportCommand,
        scope_unit_id: UUID,
        row_count: int,
        cohort_suppressed: bool,
        reason: str,
    ) -> AnalyticsAggregateExport:
        digest = sha256(
            "|".join(
                (
                    command.scope_id,
                    str(command.unit_id or "root"),
                    command.from_date.isoformat(),
                    command.to_date.isoformat(),
                    command.time_zone,
                    command.format,
                )
            ).encode()
        ).hexdigest()
        record = AnalyticsAggregateExport(
            actor_user_id=actor.id,
            management_grant_id=_grant_id(command.scope_id),
            scope_unit_id=scope_unit_id,
            date_from=command.from_date,
            date_to=command.to_date,
            time_zone=command.time_zone,
            format=command.format,
            status=AnalyticsExportStatus.DENIED,
            query_digest=digest,
            row_count=row_count,
            cohort_suppressed=cohort_suppressed,
            reason=reason,
            version=1,
        )
        self.session.add(record)
        await self.session.flush()
        self.session.add(
            AnalyticsExportAuditEvent(
                export_id=record.id,
                sequence=1,
                actor_user_id=actor.id,
                from_status=None,
                to_status=AnalyticsExportStatus.DENIED,
                reason=reason,
            )
        )
        await self.session.flush()
        return record


def _operational_unit_column(
    kind: OrganisationKind,
) -> InstrumentedAttribute[UUID | None]:
    return {
        OrganisationKind.ROOT: OperationalAnalyticsFact.root_unit_id,
        OrganisationKind.COMMAND: OperationalAnalyticsFact.command_unit_id,
        OrganisationKind.OPS_GROUP: OperationalAnalyticsFact.ops_unit_id,
        OrganisationKind.TEAM: OperationalAnalyticsFact.team_unit_id,
    }[kind]


def _grant_id(scope_id: str) -> UUID | None:
    return None if scope_id == PLATFORM_SCOPE_ID else UUID(scope_id)
