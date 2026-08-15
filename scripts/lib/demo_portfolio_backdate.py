"""Spread seeded demo request history over recent weeks, keeping audit chains valid.

Run inside the api container, which holds the database credentials and audit key:
    docker exec -i <api> sh -c 'cat > /tmp/backdate.py' < scripts/lib/demo_portfolio_backdate.py
    docker exec -i <api> sh -c 'cat > /tmp/plan.json' < output/demo-portfolio-plan.json
    docker exec <api> python /tmp/backdate.py /tmp/plan.json

Local demo tooling only. Event content is unchanged; timestamps move and the
hash chain, anchor MAC and analytics projection are recomputed so every record
stays verifiable. Core statements are used deliberately: the ORM append-only
guards exist to stop the application mutating audit rows, while this script
rebuilds them consistently with the configured audit key.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update

from mist_service.analytics_projection import project_request_analytics
from mist_service.audit import canonical_anchor_mac, canonical_event_hash
from mist_service.database import SessionFactory
from mist_service.models import (
    Deliverable,
    Feedback,
    ServiceRequest,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.repositories.event_store import audit_key_for_session
from mist_service.request_event_models import RequestEvent


def event_times(count: int, start: datetime, span: timedelta, seed: str) -> list[datetime]:
    """Monotonic timestamps across the span, front-loaded like real routing."""

    rng = random.Random(seed)
    if count == 1:
        return [start]
    fractions = sorted(
        min(1.0, max(0.0, (index / (count - 1)) ** 1.2 + rng.uniform(-0.04, 0.04)))
        for index in range(count)
    )
    fractions[0], fractions[-1] = 0.0, 1.0
    times: list[datetime] = []
    for fraction in fractions:
        candidate = start + span * fraction
        if times and candidate <= times[-1]:
            candidate = times[-1] + timedelta(seconds=45)
        times.append(candidate)
    return times


async def retime_request(item: dict[str, object]) -> str:
    request_id = UUID(str(item["id"]))
    start = datetime.now(UTC) - timedelta(days=float(item["receivedDaysAgo"]))
    span = timedelta(hours=float(item["spanHours"]))
    async with SessionFactory() as session, session.begin():
        key = audit_key_for_session(session)
        reference = await session.scalar(
            select(ServiceRequest.reference).where(ServiceRequest.id == request_id)
        )
        if reference is None:
            return f"missing {request_id}"
        events = (await session.execute(
            select(
                RequestEvent.id, RequestEvent.type, RequestEvent.message,
                RequestEvent.actor_user_id, RequestEvent.prior_status,
                RequestEvent.next_status, RequestEvent.details,
            )
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
        )).all()
        if not events:
            return f"no events {reference}"
        times = event_times(len(events), start, span, str(request_id))
        previous: str | None = None
        for row, moment in zip(events, times, strict=True):
            event_hash = canonical_event_hash(
                request_id=request_id,
                event_type=row.type,
                message=row.message,
                actor_id=row.actor_user_id,
                created_at=moment,
                previous_hash=previous,
                audit_key=key,
                prior_status=row.prior_status,
                next_status=row.next_status,
                details=row.details,
            )
            await session.execute(
                update(RequestEvent)
                .where(RequestEvent.id == row.id)
                .values(created_at=moment, previous_hash=previous, event_hash=event_hash)
            )
            previous = event_hash
        last = times[-1]
        request_values: dict[str, object] = {
            "created_at": times[0],
            "updated_at": last,
            "audit_head_hash": previous,
            "audit_anchor_mac": canonical_anchor_mac(
                request_id=request_id,
                event_count=len(events),
                head_hash=previous or "",
                audit_key=key,
            ),
        }
        if bool(item.get("late")):
            request_values["required_by"] = (start + span * 0.55).date()
        await session.execute(
            update(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .values(**request_values)
        )
        await session.execute(
            update(WorkflowTask)
            .where(
                WorkflowTask.request_id == request_id,
                WorkflowTask.status.in_(
                    [WorkflowTaskStatus.OPEN, WorkflowTaskStatus.CLAIMED]
                ),
            )
            .values(created_at=last, updated_at=last)
        )
        await session.execute(
            update(Deliverable)
            .where(Deliverable.request_id == request_id)
            .values(created_at=start + span * 0.8)
        )
        await session.execute(
            update(Feedback)
            .where(Feedback.request_id == request_id)
            .values(created_at=last + timedelta(hours=3))
        )
        session.expire_all()
        await project_request_analytics(session, request_id)
        return f"retimed {reference}"


async def main(plan_path: str) -> int:
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    failures = 0
    for item in plan["items"]:
        try:
            print(await retime_request(item), flush=True)
        except Exception as error:  # noqa: BLE001 - keep processing the batch
            failures += 1
            print(f"FAILED {item.get('reference', item['id'])}: {error}", flush=True)
    print(f"Backdated {len(plan['items']) - failures} of {len(plan['items'])} requests")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1])))
