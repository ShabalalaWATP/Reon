"""Persistence adapter for iteration-close analytics projection."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import TeamIteration
from istari_service.board_ports import IterationRecord
from istari_service.operational_analytics_projection import (
    project_closed_iteration_facts,
)


class SqlAlchemyBoardIterationAnalytics:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def project_closed_iteration(
        self, iteration: IterationRecord, *, occurred_at: datetime
    ) -> None:
        await project_closed_iteration_facts(
            self._session,
            cast(TeamIteration, iteration),
            occurred_at=occurred_at,
        )
