"""Content-free integrity checks for an isolated restored product database."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.admin_audit import verify_admin_audit_integrity
from istari_service.models import RequestEvent, ServiceRequest, User, WorkflowOutbox
from istari_service.repositories.event_store import verify_request_event_integrity


@dataclass(frozen=True)
class RestoreVerificationReport:
    schema_revision: str | None
    expected_revision: str
    users: int
    requests: int
    request_events: int
    pending_commands: int
    request_audit_valid: bool
    admin_audit_valid: bool

    @property
    def valid(self) -> bool:
        return (
            self.schema_revision == self.expected_revision
            and self.request_audit_valid
            and self.admin_audit_valid
        )


async def verify_restored_database(
    session: AsyncSession,
    *,
    expected_revision: str,
) -> RestoreVerificationReport:
    revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    request_ids = list(await session.scalars(select(ServiceRequest.id)))
    request_audit_valid = all(
        [
            await verify_request_event_integrity(session, request_id)
            for request_id in request_ids
        ]
    )
    return RestoreVerificationReport(
        schema_revision=str(revision) if revision is not None else None,
        expected_revision=expected_revision,
        users=await _count(session, User),
        requests=len(request_ids),
        request_events=await _count(session, RequestEvent),
        pending_commands=int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowOutbox)
                .where(WorkflowOutbox.status.in_(["PENDING", "PROCESSING", "FAILED"]))
            )
            or 0
        ),
        request_audit_valid=request_audit_valid,
        admin_audit_valid=await verify_admin_audit_integrity(session),
    )


async def _count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)
