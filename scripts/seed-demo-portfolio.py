"""Seed a realistic, varied demo request portfolio through the live local stack.

Every request is driven through the real API and workflow engine so boards,
queues, tracking and statistics all reflect genuine lifecycle history. Run
scripts/lib/demo_portfolio_backdate.py inside the api container afterwards to
spread the recorded history over recent weeks for believable statistics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from demo_portfolio_content import (  # noqa: E402
    CLARIFICATION_ANSWERS,
    CLARIFICATION_REASONS,
    FEEDBACK_COMMENTS,
    TEAM_AREAS,
    TEMPLATES,
)
from demo_portfolio_journey import (  # noqa: E402
    Actor,
    JourneyActors,
    JourneyPlan,
    existing_requests,
    login,
    run_journey,
    username_by_display_name,
)

# (team code, command code, ops code, lead display name, no separate data needed
# for specialists because the first eligible specialist is assigned.)
TEAMS = (
    ("SSG_TEAM", "JOCK", "ACSA_B_OPS", "Grant Hanley", "Lewis Ferguson"),
    ("CEDAR_TEAM", "JOCK", "ACSA_B_OPS", "Kenny Dalglish", "Denis Law"),
    ("QUARTZ_TEAM", "JOCK", "ACSA_B_OPS", "Graeme Souness", "Alan Hansen"),
    ("LANTERN_TEAM", "JOCK", "AURORA_OPS", "Gordon Strachan", "Ally McCoist"),
    ("MOSAIC_TEAM", "JOCK", "AURORA_OPS", "Darren Fletcher", "James McFadden"),
    ("COMPASS_TEAM", "JOCK", "AURORA_OPS", "Barry Ferguson", "Paul McStay"),
    ("EMBER_TEAM", "JOCK", "VERTEX_OPS", "Gary McAllister", "John Collins"),
    ("ATLAS_TEAM", "JOCK", "VERTEX_OPS", "Kevin Gallacher", "Colin Hendry"),
    ("HARBOUR_TEAM", "JOCK", "VERTEX_OPS", "Alex McLeish", "Willie Miller"),
    ("BEACON_TEAM", "SYGOC", "NIMBUS_OPS", "Joe Jordan", "Archie Gemmill"),
    ("SLATE_TEAM", "SYGOC", "NIMBUS_OPS", "Dave Mackay", "Billy Bremner"),
    ("ORCHARD_TEAM", "SYGOC", "NIMBUS_OPS", "Jim Baxter", "Danny McGrain"),
    ("LUMEN_TEAM", "SYGOC", "PARALLAX_OPS", "Jimmy Johnstone", "Bobby Lennox"),
    ("NORTHSTAR_TEAM", "SYGOC", "PARALLAX_OPS", "John Greig", "Sandy Jardine"),
    ("COPPER_TEAM", "SYGOC", "PARALLAX_OPS", "Maurice Johnston", "Gordon Durie"),
    ("ROWAN_TEAM", "SYGOC", "HORIZON_OPS", "Stuart McCall", "Neil McCann"),
    ("VELA_TEAM", "SYGOC", "HORIZON_OPS", "Don Hutchison", "Christian Dailly"),
    ("KEEL_TEAM", "SYGOC", "HORIZON_OPS", "Gary Naysmith", "Lee McCulloch"),
    ("FLINT_TEAM", "MYGOC", "MERIDIAN_OPS", "Steven Naismith", "Charlie Adam"),
    ("THISTLE_TEAM", "MYGOC", "MERIDIAN_OPS", "Robert Snodgrass", "Steven Fletcher"),
    ("GRANITE_TEAM", "MYGOC", "MERIDIAN_OPS", "James Morrison", "Shaun Maloney"),
    ("KESTREL_TEAM", "MYGOC", "SOLSTICE_OPS", "Barry Bannan", "David Marshall"),
    ("JUNIPER_TEAM", "MYGOC", "SOLSTICE_OPS", "Allan McGregor", "Stephen O'Donnell"),
    ("VALE_TEAM", "MYGOC", "SOLSTICE_OPS", "Lyndon Dykes", "Ryan Porteous"),
    ("TIDAL_TEAM", "MYGOC", "FRONTIER_OPS", "Jack Hendry", "Aaron Hickey"),
    ("GROVE_TEAM", "MYGOC", "FRONTIER_OPS", "Scott McKenna", "Greg Taylor"),
    ("PRISM_TEAM", "MYGOC", "FRONTIER_OPS", "Ryan Jack", "Stuart Armstrong"),
)
ALLOCATION_COVER = {
    "Kieran Tierney": ("ACSA_B_OPS", "AURORA_OPS", "VERTEX_OPS", "NIMBUS_OPS", "PARALLAX_OPS"),
    "Craig Gordon": ("HORIZON_OPS", "MERIDIAN_OPS", "SOLSTICE_OPS", "FRONTIER_OPS"),
}
IN_FLIGHT_TARGETS = (
    "IN_PROGRESS", "LEAD_REVIEW", "DELIVERY_PLANNING", "QUALITY_REVIEW", "BLOCKED",
)
URGENCIES = ("ROUTINE", "ROUTINE", "TIME_SENSITIVE", "ROUTINE", "IMMEDIATE")


def template(index: int) -> dict[str, str]:
    return TEMPLATES[index % len(TEMPLATES)]


def team_plans(index: int, team: tuple[str, str, str, str, str]) -> list[JourneyPlan]:
    code, command, ops, _lead, _member = team
    area = TEAM_AREAS[code]
    base = dict(team_code=code, command_code=command, ops_code=ops, area=area)
    completed_a = JourneyPlan(
        key=f"{code}-a", content=template(3 * index), target="COMPLETED",
        urgency=URGENCIES[index % len(URGENCIES)], due_days=10 + index % 18,
        feedback_rating=5 if index % 4 == 0 else 4 if index % 2 == 0 else None,
        feedback_comment=FEEDBACK_COMMENTS[index % len(FEEDBACK_COMMENTS)],
        clarify=(
            CLARIFICATION_REASONS[index % 2], CLARIFICATION_ANSWERS[index % 2]
        ) if index % 9 == 0 else None,
        received_days_ago=6 + (index * 1.05) % 27,
        span_hours=36 + (index * 13) % 120, **base,
    )
    completed_b = JourneyPlan(
        key=f"{code}-b", content=template(3 * index + 1), target="COMPLETED",
        urgency=URGENCIES[(index + 2) % len(URGENCIES)], due_days=12 + index % 14,
        late=index % 3 == 0, received_days_ago=3 + (index * 1.7) % 30,
        span_hours=24 + (index * 17) % 140, **base,
    )
    in_flight = JourneyPlan(
        key=f"{code}-c", content=template(3 * index + 2),
        target=IN_FLIGHT_TARGETS[index % len(IN_FLIGHT_TARGETS)],
        urgency=URGENCIES[(index + 1) % len(URGENCIES)], due_days=7 + index % 12,
        clarify=(
            CLARIFICATION_REASONS[index % 2], CLARIFICATION_ANSWERS[index % 2]
        ) if IN_FLIGHT_TARGETS[index % len(IN_FLIGHT_TARGETS)] == "BLOCKED" else None,
        received_days_ago=0.5 + index % 8, span_hours=6 + (index % 5) * 10, **base,
    )
    return [completed_a, completed_b, in_flight]


def routing_plans() -> list[JourneyPlan]:
    plans = []
    stops = (
        ("TRIAGE_REVIEW", "JOCK", "ACSA_B_OPS", "SSG_TEAM", 0.2),
        ("TRIAGE_REVIEW", "SYGOC", "NIMBUS_OPS", "BEACON_TEAM", 1.1),
        ("COORDINATION_REVIEW", "JOCK", "ACSA_B_OPS", "CEDAR_TEAM", 0.6),
        ("COORDINATION_REVIEW", "SYGOC", "HORIZON_OPS", "ROWAN_TEAM", 1.4),
        ("COORDINATION_REVIEW", "MYGOC", "MERIDIAN_OPS", "FLINT_TEAM", 0.9),
        ("ALLOCATION_REVIEW", "JOCK", "VERTEX_OPS", "EMBER_TEAM", 0.8),
        ("ALLOCATION_REVIEW", "SYGOC", "PARALLAX_OPS", "LUMEN_TEAM", 1.8),
        ("ALLOCATION_REVIEW", "MYGOC", "FRONTIER_OPS", "TIDAL_TEAM", 1.2),
    )
    for offset, (target, command, ops, area_team, days) in enumerate(stops):
        # Offsets 0 and 3 shift template so no title collides with a team plan.
        plans.append(JourneyPlan(
            key=f"routing-{offset}", team_code=None, command_code=command,
            ops_code=ops, content=template(offset * 5 + (4 if offset in (0, 3) else 2)),
            area=TEAM_AREAS[area_team], urgency=URGENCIES[offset % len(URGENCIES)],
            due_days=9 + offset, target=target, received_days_ago=days,
            span_hours=4 + offset * 2,
        ))
    return plans


async def build_actors(args: argparse.Namespace, password: str) -> tuple[dict[str, Actor], dict[str, str]]:
    admin = await login(args.base_url, args.origin, "admin1", password)
    usernames = await username_by_display_name(admin)
    await admin.client.aclose()
    display_names = {"John McGinn", "Billy Gilmour", "Scott McTominay",
                     "Callum McGregor", "Angus Gunn", *ALLOCATION_COVER}
    display_names.update(lead for _c, _g, _o, lead, _m in TEAMS)
    display_names.update(member for _c, _g, _o, _l, member in TEAMS)
    actors: dict[str, Actor] = {}
    for name in sorted(display_names):
        actors[name] = await login(args.base_url, args.origin, usernames[name], password)
    return actors, usernames


def journey_actors(actors: dict[str, Actor], requester: str, resolve) -> JourneyActors:
    allocation = {
        ops: actors[name] for name, cover in ALLOCATION_COVER.items() for ops in cover
    }
    return JourneyActors(
        requester=actors[requester],
        triage=actors["Scott McTominay"],
        coordination=actors["Callum McGregor"],
        allocation=allocation,
        leads={code: actors[lead] for code, _g, _o, lead, _m in TEAMS},
        specialists={code: actors[member] for code, _g, _o, _l, member in TEAMS},
        specialist_names={code: member for code, _g, _o, _l, member in TEAMS},
        resolve=resolve,
        quality=actors["Angus Gunn"],
    )


async def execute(args: argparse.Namespace) -> int:
    password = args.password or os.environ.get("DEMO_USER_PASSWORD")
    if not password:
        raise RuntimeError("Provide --password or set DEMO_USER_PASSWORD")
    actors, usernames = await build_actors(args, password)
    resolver_lock = asyncio.Lock()

    async def resolve(display_name: str) -> Actor:
        async with resolver_lock:
            if display_name not in actors:
                actors[display_name] = await login(
                    args.base_url, args.origin, usernames[display_name], password
                )
            return actors[display_name]

    bundles = (
        journey_actors(actors, "John McGinn", resolve),
        journey_actors(actors, "Billy Gilmour", resolve),
    )
    seeded: dict[str, dict[str, str]] = {}
    for requester in ("John McGinn", "Billy Gilmour"):
        seeded.update(await existing_requests(actors[requester]))
    plans: list[JourneyPlan] = []
    for index, team in enumerate(TEAMS):
        plans.extend(team_plans(index, team))
    plans.extend(routing_plans())
    resumed = 0
    for plan in plans:
        record = seeded.get(plan.content["title"].format(area=plan.area))
        if record:
            plan.resume = record
            resumed += 1
    if resumed:
        print(f"Resuming {resumed} previously created requests")
    semaphore = asyncio.Semaphore(args.concurrency)
    results: list[dict[str, object]] = []
    failures: list[str] = []

    async def run_one(sequence: int, plan: JourneyPlan) -> None:
        async with semaphore:
            try:
                results.append(await run_journey(bundles[sequence % 2], plan))
                print(f"  seeded {plan.key}: {plan.target}", flush=True)
            except Exception as error:  # noqa: BLE001 - report and continue
                failures.append(f"{plan.key}: {error}")

    await asyncio.gather(*(run_one(index, plan) for index, plan in enumerate(plans)))
    for actor in actors.values():
        await actor.client.aclose()
    output = Path(args.plan_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"items": results}, indent=2), encoding="utf-8")
    print(f"Seeded {len(results)} of {len(plans)} requests; plan at {output}")
    for failure in failures:
        print(f"  FAILED {failure}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173/api/v1")
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--password")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--plan-output", default="output/demo-portfolio-plan.json")
    args = parser.parse_args()
    return asyncio.run(execute(args))


if __name__ == "__main__":
    raise SystemExit(main())
