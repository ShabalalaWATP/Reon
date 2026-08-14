"""Compose statistics use cases with SQLAlchemy adapters at the HTTP boundary."""

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.repositories.statistics import SqlAlchemyStatisticsRepository
from istari_service.repositories.statistics_evolution import (
    SqlAlchemyStatisticsEvolutionRepository,
)
from istari_service.services.statistics_evolution_service import (
    StatisticsEvolutionService,
)
from istari_service.services.statistics_service import StatisticsService


def statistics_service(session: AsyncSession) -> StatisticsService:
    return StatisticsService(SqlAlchemyStatisticsRepository(session))


def statistics_evolution_service(
    session: AsyncSession,
) -> StatisticsEvolutionService:
    repository = SqlAlchemyStatisticsEvolutionRepository(session)
    return StatisticsEvolutionService(repository, repository)
