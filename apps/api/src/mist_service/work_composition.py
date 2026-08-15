"""Composition boundary for work-item and related-record operations."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.config import Settings
from mist_service.repositories.related_records import (
    SqlAlchemyRelatedRecordRepository,
)
from mist_service.repositories.work import SqlAlchemyWorkRepository
from mist_service.services.related_record_service import RelatedRecordService
from mist_service.services.work_service import WorkService
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow_command_dispatch import WorkflowCommandDispatcher


def build_related_record_service(session: AsyncSession) -> RelatedRecordService:
    return RelatedRecordService(SqlAlchemyRelatedRecordRepository(session))


def build_work_service(
    session: AsyncSession,
    engine: WorkflowEngine,
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> WorkService:
    return WorkService(
        SqlAlchemyWorkRepository(
            session,
            managed_products_enabled=settings.managed_products_enabled,
        ),
        WorkflowCommandDispatcher(
            sessions,
            engine,
            managed_products_enabled=settings.managed_products_enabled,
        ),
    )
