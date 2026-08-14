"""Compose calendar use cases with request-scoped persistence adapters."""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.calendar_capacity import CalendarCapacityService
from istari_service.calendar_ports import (
    CalendarCapacityPort,
    CalendarManagementPort,
    CalendarRepositoryPort,
)
from istari_service.repositories.calendar import SqlAlchemyCalendarRepository
from istari_service.repositories.calendar_management import (
    SqlAlchemyCalendarManagement,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.services.calendar_service import CalendarService
from istari_service.services.team_workspace_ports import TeamWorkspaceReadPort


def calendar_service(session: AsyncSession) -> CalendarService:
    """Build one calendar use case over the route transaction's session."""

    calendar = SqlAlchemyCalendarRepository(session)
    return CalendarService(
        cast(CalendarRepositoryPort, calendar),
        cast(TeamWorkspaceReadPort, SqlAlchemyTeamWorkspaceRepository(session)),
        cast(CalendarCapacityPort, CalendarCapacityService(session, calendar)),
        cast(CalendarManagementPort, SqlAlchemyCalendarManagement(session)),
    )
