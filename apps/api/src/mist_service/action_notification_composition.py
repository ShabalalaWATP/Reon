"""Composition root for action, notification and hastener application services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.repositories.actions import SqlAlchemyActionRepository
from mist_service.repositories.notification_projection import (
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notification_reconciliation import (
    SqlAlchemyNotificationReconciler,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.repositories.task_hasteners import (
    SqlAlchemyTaskHastenerEventWriter,
    SqlAlchemyTaskHastenerNotifier,
    SqlAlchemyTaskHastenerRepository,
    SqlAlchemyTaskHastenerWorkspaceReader,
)
from mist_service.services.action_service import ActionService
from mist_service.services.notification_service import NotificationService
from mist_service.services.task_hastener_service import TaskHastenerService


def action_service(session: AsyncSession) -> ActionService:
    return ActionService(SqlAlchemyActionRepository(session))


def notification_service(session: AsyncSession) -> NotificationService:
    return NotificationService(
        SqlAlchemyNotificationRepository(session),
        SqlAlchemyNotificationProjectionRepository(session),
        SqlAlchemyNotificationReconciler(session),
    )


def task_hastener_service(session: AsyncSession) -> TaskHastenerService:
    return TaskHastenerService(
        SqlAlchemyTaskHastenerRepository(session),
        SqlAlchemyTaskHastenerWorkspaceReader(session),
        SqlAlchemyTaskHastenerEventWriter(session),
        SqlAlchemyTaskHastenerNotifier(session),
    )
