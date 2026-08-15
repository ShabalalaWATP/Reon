"""Managed-product access-audit integrity regressions."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.product_access_audit import SqlAlchemyProductAccessAudit
from mist_service.product_models import ProductAccessEvent
from mist_service.product_types import (
    AccessAuditRecord,
    AccessKind,
    AccessOutcome,
)
from product_test_support import product_actors


async def test_denied_access_audit_is_independent_minimised_and_append_only(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, _analyst, _qc = await product_actors(api_harness)
    target = uuid4()
    await SqlAlchemyProductAccessAudit(api_harness.sessions).record(
        AccessAuditRecord(
            request_id=None,
            package_id=None,
            artefact_id=None,
            target_reference=target,
            actor_id=requester.id,
            kind=AccessKind.DOWNLOAD,
            outcome=AccessOutcome.DENIED,
            reason_code="ACCESS_DENIED",
            correlation_id="safe-correlation",
        )
    )
    async with api_harness.sessions() as session:
        event = await session.scalar(select(ProductAccessEvent))
        assert event is not None
        assert event.target_hash != str(target)
        assert len(event.target_hash) == 64
        assert event.reason_code == "ACCESS_DENIED"
        event.reason_code = "TAMPERED"
        with pytest.raises(ValueError, match="append-only"):
            await session.commit()
        await session.rollback()
