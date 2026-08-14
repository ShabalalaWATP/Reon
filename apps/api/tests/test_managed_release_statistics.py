"""Managed dissemination is counted once at the authoritative QC boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from istari_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from istari_service.domain import Actor
from istari_service.management_seed import management_grant_id
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.operational_analytics_reconciliation import (
    reconcile_operational_analytics,
)
from istari_service.organisation_models import RequestRouteSelection
from istari_service.product_runtime import ProductRuntime
from istari_service.product_security import AllowedHttpsLinkPolicy
from istari_service.repositories.event_store import append_request_event
from istari_service.request_event_models import RequestEvent
from product_test_support import (
    add_claimed_lead_review_task,
    add_claimed_release_task,
    create_product_request,
    product_actors,
)


async def test_complete_managed_releases_are_counted_once_in_statistics(
    api_harness: ApiHarness,
) -> None:
    transport = api_harness.client._transport
    application = transport.app  # type: ignore[attr-defined]
    runtime: ProductRuntime = application.state.product_runtime
    application.state.product_runtime = replace(
        runtime,
        link_policy=AllowedHttpsLinkPolicy(frozenset({"products.example.test"})),
    )
    requester, _other, manager, analyst, qc = await product_actors(api_harness)
    request_ids = [
        await _complete_managed_release(
            api_harness,
            requester=requester,
            manager=manager,
            analyst=analyst,
            qc=qc,
        )
        for _index in range(5)
    ]

    async with api_harness.sessions() as session:
        release_count = await _release_count(session)
        event_counts = dict(
            (
                await session.execute(
                    select(RequestEvent.type, func.count(RequestEvent.id))
                    .where(RequestEvent.request_id.in_(request_ids))
                    .where(
                        RequestEvent.type.in_(
                            {"WORKFLOW_RELEASE", "PRODUCT_DISSEMINATED"}
                        )
                    )
                    .group_by(RequestEvent.type)
                )
            ).all()
        )
    assert release_count == 5
    assert event_counts == {"PRODUCT_DISSEMINATED": 5, "WORKFLOW_RELEASE": 5}

    await _replay_and_assert_release_count(api_harness, 5)

    await api_harness.login("admin8")
    response = await api_harness.client.get(
        "/api/v1/statistics/evolution",
        params=_statistics_params(),
    )
    assert response.status_code == 200, response.text
    released = next(
        item
        for item in response.json()["releases"]
        if item["key"] == "dissemination_released"
    )
    assert released["count"] == 5
    assert released["suppressed"] is False


async def _complete_managed_release(
    harness: ApiHarness,
    *,
    requester: Actor,
    manager: Actor,
    analyst: Actor,
    qc: Actor,
) -> UUID:
    request_id = await create_product_request(harness, requester, analyst)
    await _complete_route(harness, request_id)
    await harness.login("admin11")
    created = await harness.client.post(
        "/api/v1/product-packages",
        headers=harness.mutation_headers(),
        json={
            "requestId": str(request_id),
            "expectedVersion": 3,
            "idempotencyKey": str(uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    package = created.json()
    linked = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/external-links",
        headers=harness.mutation_headers(),
        json=_command(
            1,
            label="Synthetic managed release",
            url="https://products.example.test/synthetic-result",
        ),
    )
    assert linked.status_code == 200, linked.text
    submitted = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/submit",
        headers=harness.mutation_headers(),
        json=_command(2, coveringNote="Synthetic product covering note."),
    )
    assert submitted.status_code == 200, submitted.text

    await _set_request_status(harness, request_id, RequestStatus.LEAD_REVIEW)
    async with harness.sessions() as session, session.begin():
        await add_claimed_lead_review_task(session, request_id, manager.id)
    await harness.login("admin8")
    approved = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/manager-approve",
        headers=harness.mutation_headers(),
        json=_command(
            3,
            packageChecksum=submitted.json()["packageChecksum"],
        ),
    )
    assert approved.status_code == 200, approved.text

    await _set_request_status(harness, request_id, RequestStatus.READY_FOR_RELEASE)
    await _record_workflow_completion(harness, request_id, qc.id)
    async with harness.sessions() as session, session.begin():
        await add_claimed_release_task(session, request_id, qc.id)
    await harness.login("admin15")
    released = await harness.client.post(
        f"/api/v1/releases/{package['id']}/disseminate",
        headers=harness.mutation_headers(),
        json=_command(
            4,
            packageChecksum=approved.json()["packageChecksum"],
            externalLinkAttested=True,
        ),
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "DISSEMINATED"
    assert manager.id != analyst.id != qc.id
    return request_id


async def _set_request_status(
    harness: ApiHarness, request_id: UUID, status: RequestStatus
) -> None:
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = status


async def _complete_route(harness: ApiHarness, request_id: UUID) -> None:
    unit_ids = [
        await harness.unit_id(code) for code in ("JOCK", "ACSA_B_OPS", "SSG_TEAM")
    ]
    async with harness.sessions() as session, session.begin():
        session.add_all(
            RequestRouteSelection(
                request_id=request_id,
                unit_id=unit_id,
                position=position,
            )
            for position, unit_id in enumerate(unit_ids, start=1)
        )


async def _record_workflow_completion(
    harness: ApiHarness, request_id: UUID, actor_id: UUID
) -> None:
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        await append_request_event(
            session,
            request_id=request_id,
            actor_id=actor_id,
            event_type="WORKFLOW_RELEASE",
            message="Synthetic workflow release gate completed.",
            prior_status=request.status,
            next_status=request.status,
        )


async def _replay_and_assert_release_count(harness: ApiHarness, expected: int) -> None:
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        await reconcile_operational_analytics(
            session,
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        assert await _release_count(session) == expected


async def _release_count(session: AsyncSession) -> int:
    value = await session.scalar(
        select(func.count(OperationalAnalyticsFact.id)).where(
            OperationalAnalyticsFact.type == OperationalFactType.DISSEMINATION_RELEASED
        )
    )
    return int(value or 0)


def _command(version: int, **extra: object) -> dict[str, object]:
    return {
        "expectedVersion": version,
        "idempotencyKey": str(uuid4()),
        **extra,
    }


def _statistics_params() -> dict[str, str]:
    today = datetime.now(UTC).date()
    return {
        "scopeId": str(management_grant_id("admin8", "SSG_TEAM")),
        "from": (today - timedelta(days=1)).isoformat(),
        "to": (today + timedelta(days=1)).isoformat(),
        "timeZone": "Europe/London",
    }
