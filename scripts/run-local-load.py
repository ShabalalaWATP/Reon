"""Run a bounded, content-free read-load rehearsal against a local ISTARI API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx


@dataclass(frozen=True, slots=True)
class ActorPlan:
    username: str
    paths: tuple[str, ...]


CALENDAR_PATH = (
    "/calendar/personal?from=2026-08-01T00%3A00%3A00Z&to=2026-08-14T00%3A00%3A00Z"
)
USERNAMES = tuple(f"admin{index}" for index in range(2, 53) if index != 16)
ROLE_PATHS = {
    "REQUESTER": ("/auth/me", "/requests", "/request-drafts", "/organisation/units"),
    "INTAKE_TRIAGE": ("/auth/me", "/work-items", "/tracked-requests"),
    "SERVICE_COORDINATION": (
        "/auth/me",
        "/work-items",
        "/tracked-requests",
        "/statistics/scopes",
    ),
    "OPERATIONS_ALLOCATION": (
        "/auth/me",
        "/work-items",
        "/tracked-requests",
        "/statistics/scopes",
    ),
    "DELIVERY_TEAM_LEAD": (
        "/auth/me",
        "/work-items",
        "/statistics/scopes",
        "/team-workspaces",
        CALENDAR_PATH,
    ),
    "DELIVERY_SPECIALIST": (
        "/auth/me",
        "/work-items",
        "/team-workspaces",
        CALENDAR_PATH,
    ),
    "QUALITY_RELEASE": ("/auth/me", "/work-items", "/organisation/units"),
}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int(len(ordered) * fraction) - 1))
    return ordered[position]


async def authenticate(
    base_url: str, origin: str, password: str, username: str
) -> tuple[httpx.AsyncClient, ActorPlan]:
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={"Origin": origin},
        timeout=httpx.Timeout(10),
    )
    response = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    response.raise_for_status()
    role = response.json()["user"]["role"]
    paths = ROLE_PATHS.get(role)
    if paths is None:
        await client.aclose()
        raise RuntimeError(f"no bounded read plan is defined for role {role}")
    scoped_paths = await discover_scoped_paths(client)
    return client, ActorPlan(username, paths + scoped_paths)


async def discover_scoped_paths(client: httpx.AsyncClient) -> tuple[str, ...]:
    """Discover only scopes already granted to the authenticated load identity."""

    paths: list[str] = []
    workspaces = await client.get("/team-workspaces")
    if workspaces.status_code == 200 and workspaces.json()["items"]:
        team_id = quote(workspaces.json()["items"][0]["teamId"], safe="")
        paths.extend(
            (
                f"/team-workspaces/{team_id}/board?limit=50",
                f"/team-workspaces/{team_id}/packages?limit=50",
                f"/team-workspaces/{team_id}/calendar?"
                + urlencode(
                    {
                        "from": "2026-08-01T00:00:00Z",
                        "to": "2026-08-14T00:00:00Z",
                    }
                ),
            )
        )
    statistics_scopes = await client.get("/statistics/scopes")
    if statistics_scopes.status_code == 200 and statistics_scopes.json()["items"]:
        scope_id = statistics_scopes.json()["items"][0]["id"]
        paths.append(
            "/statistics?"
            + urlencode(
                {
                    "scopeId": scope_id,
                    "from": "2026-08-01",
                    "to": "2026-08-14",
                    "timeZone": "Europe/London",
                }
            )
        )
    return tuple(paths)


async def run(args: argparse.Namespace) -> dict[str, object]:
    password = os.environ.get("LOAD_TEST_PASSWORD")
    if not password:
        raise RuntimeError("LOAD_TEST_PASSWORD must be set")
    if args.concurrency > len(USERNAMES):
        raise RuntimeError(f"concurrency cannot exceed {len(USERNAMES)} distinct users")
    authenticated = [
        await authenticate(args.base_url, args.origin, password, username)
        for username in USERNAMES[: args.concurrency]
    ]
    clients = [client for client, _ in authenticated]
    client_plans = [plan for _, plan in authenticated]
    if args.warmup_seconds:
        await run_phase(
            clients,
            client_plans,
            concurrency=args.concurrency,
            duration_seconds=args.warmup_seconds,
        )
    started = time.perf_counter()
    result = await run_phase(
        clients,
        client_plans,
        concurrency=args.concurrency,
        duration_seconds=args.duration_seconds or None,
        request_limit=None if args.duration_seconds else args.requests,
    )
    duration = time.perf_counter() - started
    await asyncio.gather(*(client.aclose() for client in clients))
    latencies, statuses, failed_paths, path_latencies = result
    errors = sum(
        count for status, count in statuses.items() if status < 200 or status >= 400
    )
    report: dict[str, object] = {
        "base_url": args.base_url,
        "concurrency": args.concurrency,
        "duration_seconds": round(duration, 3),
        "error_count": errors,
        "error_rate_percent": round(errors * 100 / len(latencies), 3),
        "failed_paths": dict(sorted(failed_paths.items())),
        "mean_ms": round(statistics.fmean(latencies), 2),
        "p50_ms": round(percentile(latencies, 0.50), 2),
        "p90_ms": round(percentile(latencies, 0.90), 2),
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "p99_ms": round(percentile(latencies, 0.99), 2),
        "path_metrics": {
            path: {
                "mean_ms": round(statistics.fmean(values), 2),
                "p95_ms": round(percentile(values, 0.95), 2),
                "p99_ms": round(percentile(values, 0.99), 2),
                "request_count": len(values),
            }
            for path, values in sorted(path_latencies.items())
        },
        "request_count": len(latencies),
        "requests_per_second": round(len(latencies) / duration, 2),
        "status_counts": {str(key): value for key, value in sorted(statuses.items())},
        "warmup_seconds": args.warmup_seconds,
    }
    report["passed"] = (
        float(report["error_rate_percent"]) < args.error_limit_percent
        and float(report["p95_ms"]) < args.p95_limit_ms
        and float(report["p99_ms"]) < args.p99_limit_ms
    )
    return report


async def run_phase(
    clients: list[httpx.AsyncClient],
    plans: list[ActorPlan],
    *,
    concurrency: int,
    duration_seconds: float | None = None,
    request_limit: int | None = None,
) -> tuple[list[float], dict[int, int], dict[str, int], dict[str, list[float]]]:
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    failed_paths: dict[str, int] = {}
    path_latencies: dict[str, list[float]] = {}
    lock = asyncio.Lock()
    sequence = 0
    deadline = time.perf_counter() + duration_seconds if duration_seconds else None

    async def worker() -> None:
        nonlocal sequence
        while True:
            async with lock:
                if deadline is not None and time.perf_counter() >= deadline:
                    return
                if request_limit is not None and sequence >= request_limit:
                    return
                index = sequence
                sequence += 1
            client_index = index % len(clients)
            plan = plans[client_index]
            path = plan.paths[(index // len(clients)) % len(plan.paths)]
            started = time.perf_counter()
            try:
                response = await clients[client_index].get(path)
                status = response.status_code
            except httpx.HTTPError:
                status = 0
            elapsed_ms = (time.perf_counter() - started) * 1_000
            async with lock:
                latencies.append(elapsed_ms)
                path_latencies.setdefault(path, []).append(elapsed_ms)
                statuses[status] = statuses.get(status, 0) + 1
                if status < 200 or status >= 400:
                    key = f"GET {path} -> {status}"
                    failed_paths[key] = failed_paths.get(key, 0) + 1

    await asyncio.gather(*(worker() for _ in range(concurrency)))
    return latencies, statuses, failed_paths, path_latencies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173/api/v1")
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--warmup-seconds", type=float, default=0)
    parser.add_argument("--duration-seconds", type=float, default=0)
    parser.add_argument("--p95-limit-ms", type=float, default=2_000)
    parser.add_argument("--p99-limit-ms", type=float, default=4_000)
    parser.add_argument("--error-limit-percent", type=float, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.duration_seconds < 0:
        parser.error(
            "requests and concurrency must be positive; duration cannot be negative"
        )
    report = asyncio.run(run(args))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
