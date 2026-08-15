"""Independent append-only access audit, including denied attempts."""

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.operational_analytics_projection import (
    project_product_access_fact,
)
from mist_service.product_models import ProductAccessEvent
from mist_service.product_types import AccessAuditRecord


class SqlAlchemyProductAccessAudit:
    """Use a separate transaction so a denied request cannot roll back its audit."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def record(self, record: AccessAuditRecord) -> None:
        target_hash = hashlib.sha256(
            str(record.target_reference).encode("ascii")
        ).hexdigest()
        async with self._sessions() as session, session.begin():
            event = ProductAccessEvent(
                request_id=record.request_id,
                package_id=record.package_id,
                artefact_id=record.artefact_id,
                target_hash=target_hash,
                actor_user_id=record.actor_id,
                kind=record.kind,
                outcome=record.outcome,
                reason_code=record.reason_code,
                correlation_id=record.correlation_id,
            )
            session.add(event)
            await session.flush()
            await project_product_access_fact(session, event)
