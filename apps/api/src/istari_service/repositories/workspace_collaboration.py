"""Persistence and final read boundary for workspace collaboration."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.models import User
from istari_service.schemas.workspace_collaboration import (
    WorkspaceRecordCreate,
    WorkspaceRecordResolve,
    WorkspaceRecordView,
)
from istari_service.workspace_collaboration_models import (
    WorkspaceRecord,
    WorkspaceRecordEvent,
    WorkspaceRecordEventType,
    WorkspaceRecordStatus,
)


class WorkspaceCollaborationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, unit_id: UUID) -> list[WorkspaceRecordView]:
        rows = (
            await self.session.execute(
                select(WorkspaceRecord, User.display_name)
                .join(User, User.id == WorkspaceRecord.created_by_user_id)
                .where(WorkspaceRecord.unit_id == unit_id)
                .order_by(
                    WorkspaceRecord.status,
                    WorkspaceRecord.updated_at.desc(),
                    WorkspaceRecord.id,
                )
                .limit(250)
            )
        ).all()
        return [self._view(record, name) for record, name in rows]

    async def create(
        self, unit_id: UUID, actor_id: UUID, command: WorkspaceRecordCreate
    ) -> WorkspaceRecord:
        record = WorkspaceRecord(
            unit_id=unit_id,
            kind=command.kind,
            status=WorkspaceRecordStatus.OPEN,
            title=command.title,
            body=command.body,
            url=command.url,
            created_by_user_id=actor_id,
        )
        self.session.add(record)
        await self.session.flush()
        self.session.add(
            WorkspaceRecordEvent(
                record_id=record.id,
                unit_id=unit_id,
                actor_user_id=actor_id,
                type=WorkspaceRecordEventType.CREATED,
                record_version=record.version,
                summary="A workspace collaboration record was created.",
            )
        )
        return record

    async def resolve(
        self,
        unit_id: UUID,
        record_id: UUID,
        actor_id: UUID,
        command: WorkspaceRecordResolve,
    ) -> WorkspaceRecord:
        record = await self.session.scalar(
            select(WorkspaceRecord)
            .where(
                WorkspaceRecord.id == record_id,
                WorkspaceRecord.unit_id == unit_id,
            )
            .with_for_update()
        )
        if record is None:
            raise ObjectNotFound()
        if record.version != command.expected_version:
            raise StaleVersion()
        if record.status is WorkspaceRecordStatus.RESOLVED:
            raise ObjectNotFound()
        record.status = WorkspaceRecordStatus.RESOLVED
        record.resolved_by_user_id = actor_id
        record.resolution = command.resolution.strip()
        record.version += 1
        await self.session.flush()
        self.session.add(
            WorkspaceRecordEvent(
                record_id=record.id,
                unit_id=unit_id,
                actor_user_id=actor_id,
                type=WorkspaceRecordEventType.RESOLVED,
                record_version=record.version,
                summary="A workspace collaboration record was resolved.",
            )
        )
        return record

    @staticmethod
    def _view(record: WorkspaceRecord, creator: str) -> WorkspaceRecordView:
        return WorkspaceRecordView(
            id=record.id,
            kind=record.kind,
            status=record.status,
            title=record.title,
            body=record.body,
            url=record.url,
            created_by_display_name=creator,
            resolution=record.resolution,
            version=record.version,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
