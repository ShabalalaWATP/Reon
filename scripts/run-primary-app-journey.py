"""Exercise the primary staffed route through the full local service stack."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from run_local_app_journey_support import Actor, claim, complete, destination, login


async def wait_for_item(
    actor: Actor, request_id: str, stage: str, attempts: int = 60
) -> dict[str, Any]:
    for _attempt in range(attempts):
        data = await actor.get("/work-items")
        for item in data["items"]:
            if item["requestId"] == request_id and item["stage"] == stage:
                return item
        await asyncio.sleep(0.5)
    raise RuntimeError(f"{actor.username} did not receive the expected {stage} work")


def request_body() -> dict[str, object]:
    required_by = (datetime.now(UTC).date() + timedelta(days=14)).isoformat()
    return {
        "submissionKey": str(uuid4()),
        "title": "Primary SSG route assurance summary",
        "description": "Produce a synthetic summary through the primary SSG route.",
        "questionToAnswer": "What does the synthetic primary-route evidence show?",
        "desiredOutcome": "A reviewed product delivered through SSG Team and QC.",
        "backgroundContext": "All information is synthetic local assurance data.",
        "subjectAreaOrLocation": "Synthetic primary-route assurance",
        "coverageStart": required_by,
        "coverageEnd": required_by,
        "customerUrgency": "ROUTINE",
        "supportedActivityOrDecision": "A local primary-route assurance decision.",
        "requiredBy": required_by,
        "requiredByReason": "The local assurance review follows this date.",
        "preferredDeliverableType": "Written response",
        "successCriteria": "The complete SSG route is recorded and delivered.",
        "constraintsOrCaveats": "No known constraints.",
        "supportingInformation": "No supporting material is available.",
        "sensitivity": "STANDARD",
        "handlingInstructions": "Standard synthetic-data handling applies.",
    }


async def exercise(args: argparse.Namespace) -> dict[str, object]:
    password = os.environ.get("APP_JOURNEY_PASSWORD")
    if not password:
        raise RuntimeError("APP_JOURNEY_PASSWORD must be set")
    usernames = ("admin2", "admin4", "admin5", "admin6", "admin8", "admin13", "admin15")
    actors = {
        username: await login(args.base_url, args.origin, username, password)
        for username in usernames
    }
    customer, crioc, command, ops, manager, analyst, qc = (
        actors[username] for username in usernames
    )
    request = await customer.post("/requests", request_body())
    request_id = str(request["id"])

    item = await claim(crioc, await wait_for_item(crioc, request_id, "TRIAGE_REVIEW"))
    await complete(
        crioc,
        item,
        {
            "action": "progress",
            "priority": "HIGH",
            "destinationUnitId": await destination(crioc, item, "JOCK"),
        },
    )
    item = await claim(
        command, await wait_for_item(command, request_id, "COORDINATION_REVIEW")
    )
    await complete(
        command,
        item,
        {
            "action": "send_to_allocation",
            "destinationUnitId": await destination(command, item, "ACSA_B_OPS"),
            "note": "Route through the primary operations group.",
        },
    )
    item = await claim(ops, await wait_for_item(ops, request_id, "ALLOCATION_REVIEW"))
    await complete(
        ops,
        item,
        {
            "action": "allocate",
            "destinationUnitId": await destination(ops, item, "SSG_TEAM"),
            "requiredCapabilities": ["Synthetic service production"],
        },
    )
    item = await claim(
        manager, await wait_for_item(manager, request_id, "DELIVERY_PLANNING")
    )
    specialists = await manager.get(f"/work-items/{item['id']}/eligible-specialists")
    specialist = next(
        entry for entry in specialists["items"] if entry["displayName"] == "Ben Doak"
    )
    await complete(
        manager,
        item,
        {
            "action": "assign",
            "specialistId": specialist["id"],
            "reason": "Selected as the Lead Analyst for primary-route assurance.",
        },
    )
    item = await wait_for_item(analyst, request_id, "IN_PROGRESS")
    await complete(
        analyst,
        item,
        {
            "action": "submit",
            "deliverableTitle": "Primary-route service summary",
            "deliverableText": (
                "This synthetic product proves the complete JOCK, ACSA-B Ops "
                "and SSG Team route."
            ),
        },
    )
    item = await claim(manager, await wait_for_item(manager, request_id, "LEAD_REVIEW"))
    await complete(manager, item, {"action": "approve"})
    item = await claim(qc, await wait_for_item(qc, request_id, "QUALITY_REVIEW"))
    await complete(qc, item, {"action": "approve"})
    item = await claim(qc, await wait_for_item(qc, request_id, "READY_FOR_RELEASE"))
    await complete(qc, item, {"action": "release", "recipients": ["Pilot Customer"]})

    final = await customer.get(f"/requests/{request_id}")
    product = await customer.client.get(f"/requests/{request_id}/product")
    product.raise_for_status()
    await asyncio.gather(*(actor.client.aclose() for actor in actors.values()))
    passed = (
        final["status"] == "COMPLETED"
        and final["assignedDeliveryTeam"] == "SSG Team"
        and final["assignedSpecialist"]["displayName"] == "Ben Doak"
    )
    return {
        "assigned_specialist": final["assignedSpecialist"]["displayName"],
        "assigned_team": final["assignedDeliveryTeam"],
        "passed": passed,
        "path": "CRIOC -> JOCK -> ACSA-B Ops -> SSG Team -> QC",
        "product_download": "verified",
        "request_reference": final["reference"],
        "status": final["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(exercise(args))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
