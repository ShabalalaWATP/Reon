"""Generate target-scale PostgreSQL evidence without recording sensitive data."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from runtime_scale_measurements import (
    contention_evidence,
    load_scale_context,
    statement_count_evidence,
)
from runtime_scale_plans import query_plan_evidence
from sqlalchemy import func, select, text

from mist_service.database import SessionFactory, dispose_database, engine
from mist_service.models import RequestEvent, ServiceRequest, WorkflowTask
from mist_service.request_draft_models import RequestDraft


async def run(target: int) -> dict[str, Any]:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("runtime scale evidence requires PostgreSQL")
    started = perf_counter()
    counts = await _fixture_counts()
    context = await load_scale_context(SessionFactory, depth=max(target - 100, 1))
    statements = await statement_count_evidence(SessionFactory, engine, context)
    plans = await query_plan_evidence(SessionFactory, context)
    contention = await contention_evidence(SessionFactory)
    bounded = all(item["bounded"] for item in statements.values())
    indexed = all(
        item["required_index_available"] and item["index_compatibility_uses_required"]
        for item in plans.values()
    )
    target_present = all(value >= target for value in counts.values())
    return {
        "contention": contention,
        "duration_ms": round((perf_counter() - started) * 1_000, 3),
        "environment": await _environment(),
        "fixture_counts": counts,
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": target_present and bounded and indexed and contention["passed"],
        "query_plans": plans,
        "statement_counts": statements,
        "target_rows": target,
    }


async def _fixture_counts() -> dict[str, int]:
    async with SessionFactory() as session:
        request_id = await session.scalar(
            select(ServiceRequest.id).where(ServiceRequest.reference == "PERF-000001")
        )
        if request_id is None:
            raise RuntimeError("the target-scale request fixture is missing")
        expressions = {
            "drafts": select(func.count())
            .select_from(RequestDraft)
            .where(RequestDraft.title.like("Performance rehearsal draft %")),
            "history_events": select(func.count())
            .select_from(RequestEvent)
            .where(RequestEvent.request_id == request_id),
            "requests": select(func.count())
            .select_from(ServiceRequest)
            .where(ServiceRequest.reference.like("PERF-%")),
            "work_items": select(func.count())
            .select_from(WorkflowTask)
            .where(WorkflowTask.task_key.like("performance-task-%")),
        }
        return {
            name: int(await session.scalar(statement) or 0)
            for name, statement in expressions.items()
        }


async def _environment() -> dict[str, str]:
    async with SessionFactory() as session:
        database_version = await session.scalar(text("SELECT version()"))
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    return {
        "database": str(database_version).split(",", 1)[0],
        "migration_revision": str(revision),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=2_500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.target < 200:
        parser.error("target must be at least 200 rows")

    async def execute() -> dict[str, Any]:
        try:
            return await run(args.target)
        finally:
            await dispose_database()

    result = asyncio.run(execute())
    rendered = json.dumps(result, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
