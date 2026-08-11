"""Drive realistic demo requests through the live local service stack."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

RETRYABLE = {429, 500, 502, 503}
STAGE_ORDER = (
    "TRIAGE_REVIEW", "COORDINATION_REVIEW", "ALLOCATION_REVIEW",
    "DELIVERY_PLANNING", "IN_PROGRESS", "CUSTOMER_INFORMATION_REQUIRED",
    "LEAD_REVIEW", "QUALITY_REVIEW", "READY_FOR_RELEASE", "COMPLETED",
)


def stage_position(status: str) -> int:
    return STAGE_ORDER.index(status) if status in STAGE_ORDER else -1


@dataclass(slots=True)
class Actor:
    username: str
    password: str
    client: httpx.AsyncClient
    csrf_token: str
    lock: asyncio.Lock

    async def relogin(self) -> None:
        async with self.lock:
            for _attempt in range(20):
                response = await self.client.post(
                    "/auth/login",
                    json={"username": self.username, "password": self.password},
                )
                if response.status_code == 429:
                    await asyncio.sleep(12)
                    continue
                response.raise_for_status()
                self.csrf_token = response.json()["csrfToken"]
                return
            raise RuntimeError(f"login for {self.username} stayed rate-limited")

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(5):
            response = await self.client.request(
                method, path, headers={"X-CSRF-Token": self.csrf_token}, **kwargs
            )
            if response.status_code == 401:
                await self.relogin()
                continue
            if response.status_code in RETRYABLE and attempt < 4:
                await asyncio.sleep(3 + attempt * 3)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"{method} {path} kept failing for {self.username}")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return (await self._send("GET", path, params=params)).json()

    async def post(self, path: str, body: dict[str, object] | None = None) -> Any:
        response = await self._send("POST", path, json=body)
        return response.json() if response.content else None


async def login(base_url: str, origin: str, username: str, password: str) -> Actor:
    client = httpx.AsyncClient(
        base_url=base_url, headers={"Origin": origin}, timeout=httpx.Timeout(30)
    )
    actor = Actor(username, password, client, "", asyncio.Lock())
    await actor.relogin()
    return actor


async def username_by_display_name(admin: Actor) -> dict[str, str]:
    mapping: dict[str, str] = {}
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = await admin.get("/admin/users", params=params)
        for item in page["items"]:
            mapping[item["displayName"]] = item["username"]
        cursor = page.get("nextCursor") or page.get("next_cursor")
        if not cursor:
            return mapping


async def existing_requests(actor: Actor) -> dict[str, dict[str, str]]:
    """Map request title to its identifier and status for resume support."""

    found: dict[str, dict[str, str]] = {}
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = await actor.get("/requests", params=params)
        for item in page["items"]:
            found[item["title"]] = {
                "id": str(item["id"]),
                "reference": item.get("reference", ""),
                "status": item.get("status", ""),
            }
        cursor = page.get("nextCursor") or page.get("next_cursor")
        if not cursor:
            return found


async def wait_for_item(
    actor: Actor, request_id: str, stage: str, attempts: int = 120
) -> dict[str, Any]:
    for _attempt in range(attempts):
        data = await actor.get("/work-items")
        for item in data["items"]:
            if item["requestId"] == request_id and item["stage"] == stage:
                return item
        await asyncio.sleep(0.5)
    raise RuntimeError(
        f"{actor.username} did not receive {stage} work for request {request_id}"
    )


async def claim(actor: Actor, item: dict[str, Any]) -> None:
    if item.get("assigneeId"):
        return
    await actor.post(f"/work-items/{item['id']}/claim")


async def complete(actor: Actor, item: dict[str, Any], command: dict[str, object]) -> None:
    try:
        await actor.post(f"/work-items/{item['id']}/complete", command)
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 404:
            raise
        # A retried completion can find the task already finished; carry on.


async def destination(actor: Actor, item: dict[str, Any], code: str) -> str:
    options = await actor.get(f"/work-items/{item['id']}/routing-options")
    matches = [option for option in options["items"] if option["code"] == code]
    if len(matches) != 1:
        raise RuntimeError(f"expected one configured destination for {code}")
    return str(matches[0]["id"])


from demo_portfolio_content import request_body  # noqa: E402


@dataclass(slots=True)
class JourneyPlan:
    key: str
    team_code: str | None
    command_code: str
    ops_code: str
    content: dict[str, str]
    area: str
    urgency: str
    due_days: int
    target: str
    feedback_rating: int | None = None
    feedback_comment: str | None = None
    clarify: tuple[str, str] | None = None
    received_days_ago: float = 7.0
    span_hours: float = 72.0
    late: bool = False
    resume: dict[str, str] | None = field(default=None, compare=False)


@dataclass(slots=True)
class JourneyActors:
    requester: Actor
    triage: Actor
    coordination: Actor
    allocation: dict[str, Actor]
    leads: dict[str, Actor]
    specialists: dict[str, Actor]
    specialist_names: dict[str, str]
    resolve: Any  # async callable mapping a display name to a logged-in Actor
    quality: Actor


async def analyst_for(actors: JourneyActors, team: str, request_id: str, resumed: bool) -> Actor:
    """The planned specialist, or whoever is actually assigned on a resume."""

    if resumed:
        detail = await actors.requester.get(f"/requests/{request_id}")
        assigned = (detail.get("assignedSpecialist") or {}).get("displayName")
        if assigned and assigned != actors.specialist_names.get(team):
            return await actors.resolve(assigned)
    return actors.specialists[team]


async def run_journey(actors: JourneyActors, plan: JourneyPlan) -> dict[str, Any]:
    if plan.resume:
        request_id, reference = plan.resume["id"], plan.resume["reference"]
        position = stage_position(plan.resume["status"])
    else:
        body = request_body(plan.content, plan.area, plan.urgency, plan.due_days)
        request = await actors.requester.post("/requests", body)
        request_id, reference = str(request["id"]), request["reference"]
        position = 0
    result = {
        "id": request_id, "reference": reference,
        "title": plan.content["title"].format(area=plan.area),
        "target": plan.target, "receivedDaysAgo": plan.received_days_ago,
        "spanHours": plan.span_hours, "late": plan.late,
    }
    target_position = stage_position(
        {"COMPLETED": "COMPLETED", "BLOCKED": "CUSTOMER_INFORMATION_REQUIRED"}.get(
            plan.target, plan.target
        )
    )
    if position >= target_position or position < 0:
        return result
    team = plan.team_code or ""

    if position <= stage_position("TRIAGE_REVIEW") and target_position > 0:
        item = await wait_for_item(actors.triage, request_id, "TRIAGE_REVIEW")
        await claim(actors.triage, item)
        await complete(actors.triage, item, {
            "action": "progress", "priority": "MEDIUM",
            "destinationUnitId": await destination(actors.triage, item, plan.command_code),
        })
    if plan.target == "COORDINATION_REVIEW":
        return result

    if position <= stage_position("COORDINATION_REVIEW"):
        item = await wait_for_item(actors.coordination, request_id, "COORDINATION_REVIEW")
        await claim(actors.coordination, item)
        await complete(actors.coordination, item, {
            "action": "send_to_allocation",
            "destinationUnitId": await destination(actors.coordination, item, plan.ops_code),
            "note": "Routed to the operations group covering this operating area.",
        })
    if plan.target == "ALLOCATION_REVIEW":
        return result

    if position <= stage_position("ALLOCATION_REVIEW"):
        ops_actor = actors.allocation[plan.ops_code]
        item = await wait_for_item(ops_actor, request_id, "ALLOCATION_REVIEW")
        await claim(ops_actor, item)
        await complete(ops_actor, item, {
            "action": "allocate",
            "destinationUnitId": await destination(ops_actor, item, team),
            "requiredCapabilities": ["Synthetic service production"],
        })
    if plan.target == "DELIVERY_PLANNING":
        return result

    lead = actors.leads[team]
    if position <= stage_position("DELIVERY_PLANNING"):
        item = await wait_for_item(lead, request_id, "DELIVERY_PLANNING")
        await claim(lead, item)
        specialists = await lead.get(f"/work-items/{item['id']}/eligible-specialists")
        if not specialists["items"]:
            raise RuntimeError(f"no eligible specialists for team {team}")
        planned = actors.specialist_names.get(team)
        chosen = next(
            (entry for entry in specialists["items"] if entry["displayName"] == planned),
            specialists["items"][0],
        )
        await complete(lead, item, {
            "action": "assign", "specialistId": chosen["id"],
            "contributorIds": [],
            "reason": "The Manager selected this accountable delivery team.",
        })
        analyst = actors.specialists[team]
    else:
        analyst = await analyst_for(actors, team, request_id, resumed=True)
    if plan.target == "IN_PROGRESS":
        await wait_for_item(analyst, request_id, "IN_PROGRESS")
        return result

    if plan.clarify and position <= stage_position("IN_PROGRESS"):
        detail = await actors.requester.get(f"/requests/{request_id}")
        threads = detail.get("clarifications") or []
        if not threads:
            item = await wait_for_item(analyst, request_id, "IN_PROGRESS")
            await complete(analyst, item, {
                "action": "request_clarification", "question": plan.clarify[0],
                "reason": "The answer is required to complete the product accurately.",
                "responseDeadline": (
                    datetime.now(UTC).date() + timedelta(days=5)
                ).isoformat(),
            })
            position = stage_position("CUSTOMER_INFORMATION_REQUIRED")
        elif any(thread["status"] == "OPEN" for thread in threads):
            position = stage_position("CUSTOMER_INFORMATION_REQUIRED")
    if plan.target == "BLOCKED":
        return result

    if plan.clarify and position == stage_position("CUSTOMER_INFORMATION_REQUIRED"):
        answer_item = await wait_for_item(
            actors.requester, request_id, "CUSTOMER_INFORMATION_REQUIRED"
        )
        detail = await actors.requester.get(f"/requests/{request_id}")
        thread = next(
            entry for entry in detail["clarifications"] if entry["status"] == "OPEN"
        )
        await complete(actors.requester, answer_item, {
            "action": "provide_clarification", "threadId": thread["id"],
            "expectedVersion": thread["version"],
            "information": plan.clarify[1],
        })
        position = stage_position("IN_PROGRESS")

    if position <= stage_position("IN_PROGRESS"):
        item = await wait_for_item(analyst, request_id, "IN_PROGRESS")
        await complete(analyst, item, {
            "action": "submit",
            "deliverableTitle": plan.content["product_title"].format(area=plan.area),
            "deliverableText": plan.content["product_text"].format(area=plan.area),
        })
    if plan.target == "LEAD_REVIEW":
        return result

    if position <= stage_position("LEAD_REVIEW"):
        item = await wait_for_item(lead, request_id, "LEAD_REVIEW")
        await claim(lead, item)
        await complete(lead, item, {"action": "approve"})
    if plan.target == "QUALITY_REVIEW":
        return result

    if position <= stage_position("QUALITY_REVIEW"):
        item = await wait_for_item(actors.quality, request_id, "QUALITY_REVIEW")
        await claim(actors.quality, item)
        await complete(actors.quality, item, {"action": "approve"})
    item = await wait_for_item(actors.quality, request_id, "READY_FOR_RELEASE")
    await claim(actors.quality, item)
    await complete(actors.quality, item, {
        "action": "release", "recipients": ["Requesting Customer"],
    })

    if plan.feedback_rating is not None:
        try:
            await actors.requester.post(f"/requests/{request_id}/feedback", {
                "rating": plan.feedback_rating,
                "comments": plan.feedback_comment or "Thank you, the product met the need.",
            })
        except httpx.HTTPStatusError:
            pass  # feedback may already exist on a resumed journey
    return result
