"""Real domain activity produces scoped, content-free operational facts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from api_helpers import perform, reach_delivery_work
from conftest import ApiHarness
from istari_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from istari_service.board_models import WorkPackage, WorkPackageStatus
from istari_service.management_seed import management_grant_id
from istari_service.operational_analytics_reconciliation import (
    reconcile_operational_analytics,
)
from istari_service.product_models import ProductAccessEvent
from istari_service.product_types import AccessKind, AccessOutcome


async def test_real_activity_populates_only_the_exact_statistics_scope(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _release_request(harness)
    await _respond_to_notification(harness)
    team_id, grant_id = await _close_iteration_and_commit_capacity(harness)
    await _backfill_access_and_prove_idempotency(harness, request_id)
    root_id = await harness.unit_id("JIOC")

    async with harness.sessions() as session:
        facts = list(
            await session.scalars(
                select(OperationalAnalyticsFact).order_by(
                    OperationalAnalyticsFact.type,
                    OperationalAnalyticsFact.source_key,
                )
            )
        )
        types = {item.type for item in facts}
        assert {
            OperationalFactType.NOTIFICATION_SENT,
            OperationalFactType.NOTIFICATION_RESPONDED,
            OperationalFactType.DISSEMINATION_DOWNLOADED,
            OperationalFactType.ITERATION_COMMITTED,
            OperationalFactType.ITERATION_COMPLETED,
            OperationalFactType.CAPACITY_AVAILABLE,
            OperationalFactType.CAPACITY_RESERVED,
            OperationalFactType.PLANNING_ACTIVE_WORK,
            OperationalFactType.PLANNING_DEMAND,
        }.issubset(types)
        assert all(item.root_unit_id == root_id for item in facts)
        assert {item.team_unit_id for item in facts if item.team_unit_id} == {team_id}
        assert all(request_id not in item.source_key for item in facts)
        assert _fact_columns().isdisjoint(
            {
                "request_id",
                "user_id",
                "title",
                "subject",
                "description",
                "filename",
                "destination_url",
            }
        )

    params = _statistics_params(grant_id)
    await harness.login("admin8")
    visible = await harness.client.get("/api/v1/statistics/evolution", params=params)
    assert visible.status_code == 200, visible.text
    body = visible.json()
    release_keys = {item["key"] for item in body["releases"]}
    assert "dissemination_downloaded" in release_keys
    assert body["notifications"]
    assert body["iterations"] == [
        {
            "key": "iteration_completion",
            "label": "Iteration commitments completed",
            "committedCount": 5,
            "completedCount": 4,
            "completionPercentage": 80.0,
            "suppressed": False,
        }
    ]
    assert body["capacity"]

    await harness.login("admin23")
    sibling = await harness.client.get(
        "/api/v1/statistics/evolution",
        params=_statistics_params(str(management_grant_id("admin23", "QUARTZ_TEAM"))),
    )
    assert sibling.status_code == 200, sibling.text
    assert sibling.json()["releases"] == []
    assert sibling.json()["notifications"] == []
    assert sibling.json()["iterations"] == []
    assert sibling.json()["capacity"] == []


async def test_replay_rejects_unbounded_or_ambiguous_work(
    api_harness: ApiHarness,
) -> None:
    now = datetime.now(UTC)
    async with api_harness.sessions() as session:
        for start, end, limit in (
            (now.replace(tzinfo=None), now + timedelta(hours=1), 10),
            (now, now + timedelta(days=367), 10),
            (now, now + timedelta(hours=1), 0),
            (now, now + timedelta(hours=1), 5_001),
        ):
            try:
                await reconcile_operational_analytics(
                    session,
                    start=start,
                    end=end,
                    source_limit=limit,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("an unsafe replay window was accepted")


async def _release_request(harness: ApiHarness) -> str:
    request_id = await reach_delivery_work(harness)
    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": "Synthetic operational product",
            "deliverableText": "A fictional product used to verify release facts.",
        },
    )
    await perform(harness, "admin8", {"action": "approve"})
    await perform(harness, "admin15", {"action": "approve"})
    await perform(
        harness,
        "admin15",
        {"action": "release", "recipients": ["Fictional service owner"]},
    )
    return request_id


async def _respond_to_notification(harness: ApiHarness) -> None:
    await harness.login("admin2")
    listed = await harness.client.get("/api/v1/me/notifications", params={"limit": 50})
    assert listed.status_code == 200, listed.text
    item = listed.json()["items"][0]
    response = await harness.client.post(
        "/api/v1/me/notifications/state",
        headers=harness.mutation_headers(),
        json={
            "action": "MARK_READ",
            "targets": [{"id": item["id"], "expectedVersion": item["version"]}],
        },
    )
    assert response.status_code == 200, response.text


async def _close_iteration_and_commit_capacity(
    harness: ApiHarness,
) -> tuple[UUID, str]:
    await harness.login("admin8")
    team_id = await harness.unit_id("OSG_TEAM")
    grant_id = str(management_grant_id("admin8", "OSG_TEAM"))
    owner_id = str(await harness.user_id("admin11"))
    contributor_id = str(await harness.user_id("admin12"))
    today = datetime.now(UTC).date()
    iteration = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/iterations",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "name": "Operational facts iteration",
            "goal": "Verify aggregate commitment facts without individual ranking.",
            "startsOn": today.isoformat(),
            "endsOn": (today + timedelta(days=4)).isoformat(),
        },
    )
    assert iteration.status_code == 200, iteration.text
    package_ids: list[UUID] = []
    for index in range(5):
        created = await harness.client.post(
            f"/api/v1/team-workspaces/{team_id}/packages",
            headers=harness.mutation_headers(),
            json=_package_command(
                grant_id,
                owner_id,
                contributor_id,
                iteration.json()["id"],
                index,
            ),
        )
        assert created.status_code == 200, created.text
        package_ids.append(UUID(created.json()["id"]))
    async with harness.sessions() as session, session.begin():
        packages = list(
            await session.scalars(
                select(WorkPackage).where(WorkPackage.id.in_(package_ids[:4]))
            )
        )
        for package in packages:
            package.status = WorkPackageStatus.DONE
    closed = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/iterations/{iteration.json()['id']}/close",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": iteration.json()["version"],
            "completionSummary": "Four of five packages were completed.",
        },
    )
    assert closed.status_code == 200, closed.text
    preview = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/capacity/previews",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "dateFrom": today.isoformat(),
            "dateTo": (today + timedelta(days=4)).isoformat(),
            "timeZone": "Europe/London",
        },
    )
    assert preview.status_code == 200, preview.text
    committed = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/capacity/commits",
        headers=harness.mutation_headers(),
        json={"grantId": grant_id, "token": preview.json()["token"]},
    )
    assert committed.status_code == 200, committed.text
    return team_id, grant_id


def _package_command(
    grant_id: str,
    owner_id: str,
    contributor_id: str,
    iteration_id: str,
    index: int,
) -> dict[str, Any]:
    return {
        "grantId": grant_id,
        "title": f"Synthetic package {index}",
        "description": "Content kept outside operational analytics facts.",
        "ownerUserId": owner_id,
        "contributorIds": [contributor_id],
        "estimatePoints": 3,
        "remainingEffortMinutes": 120,
        "dueOn": (datetime.now(UTC).date() + timedelta(days=4)).isoformat(),
        "priority": "MEDIUM",
        "blockers": "No current blockers.",
        "acceptanceCriteria": "The synthetic package is complete.",
        "linkedRequestId": None,
        "dependencyIds": [],
        "iterationId": iteration_id,
    }


async def _backfill_access_and_prove_idempotency(
    harness: ApiHarness, request_id: str
) -> None:
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        session.add(
            ProductAccessEvent(
                request_id=UUID(request_id),
                package_id=None,
                artefact_id=None,
                target_hash="a" * 64,
                actor_user_id=await harness.user_id("admin2"),
                kind=AccessKind.DOWNLOAD,
                outcome=AccessOutcome.ALLOWED,
                reason_code="CUSTOMER_DOWNLOAD",
                correlation_id="analytics-production-test",
            )
        )
        first = await reconcile_operational_analytics(
            session,
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        count = await session.scalar(select(func.count(OperationalAnalyticsFact.id)))
        second = await reconcile_operational_analytics(
            session,
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        repeated = await session.scalar(select(func.count(OperationalAnalyticsFact.id)))
        assert first.inserted_facts >= 1
        assert second.inserted_facts == 0
        assert repeated == count


def _statistics_params(scope_id: str) -> dict[str, str]:
    today = datetime.now(UTC).date()
    return {
        "scopeId": scope_id,
        "from": (today - timedelta(days=1)).isoformat(),
        "to": (today + timedelta(days=1)).isoformat(),
        "timeZone": "Europe/London",
    }


def _fact_columns() -> set[str]:
    return {column.name for column in OperationalAnalyticsFact.__table__.columns}
