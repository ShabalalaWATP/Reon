"""Renamed owner labels reach requests written under the old wording."""

from __future__ import annotations

from uuid import UUID

from api_helpers import submit_request
from conftest import ApiHarness
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.ownership import OWNER_BY_STATUS, reconcile_owner_labels


async def test_startup_reconciliation_restamps_stale_owner_labels(
    api_harness: ApiHarness,
) -> None:
    """The owner label is a stored, status-derived snapshot so tracking can
    filter on it. A request written before a label rename keeps the old
    wording until it next transitions; reconciliation heals it in place and
    leaves already-correct requests untouched."""

    stale_id = UUID(await submit_request(api_harness))
    fresh_id = UUID(await submit_request(api_harness))
    expected = OWNER_BY_STATUS[RequestStatus.TRIAGE_REVIEW]

    async with api_harness.sessions() as session, session.begin():
        stale = await session.get(ServiceRequest, stale_id)
        assert stale is not None
        stale.current_owner = "Retired Routing Label"

    async with api_harness.sessions() as session, session.begin():
        healed = await reconcile_owner_labels(session)
        assert healed == 1

    async with api_harness.sessions() as session:
        stale = await session.get(ServiceRequest, stale_id)
        fresh = await session.get(ServiceRequest, fresh_id)
        assert stale is not None and fresh is not None
        assert stale.current_owner == expected
        assert fresh.current_owner == expected

    async with api_harness.sessions() as session, session.begin():
        assert await reconcile_owner_labels(session) == 0
