"""PostgreSQL query-plan evidence for bounded feed indexes."""

from __future__ import annotations

from typing import Any

from runtime_scale_measurements import ScaleContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

SessionFactory = async_sessionmaker[AsyncSession]

PLAN_QUERIES = {
    "requests": """
        SELECT id, updated_at
        FROM service_requests
        WHERE requester_id = CAST(:requester_id AS UUID)
        ORDER BY updated_at DESC, id DESC
        LIMIT 51
    """,
    "drafts": """
        SELECT id, updated_at
        FROM request_drafts
        WHERE requester_id = CAST(:requester_id AS UUID)
        ORDER BY updated_at DESC, id DESC
        LIMIT 51
    """,
    "work": """
        SELECT id, updated_at
        FROM workflow_tasks
        WHERE candidate_role = 'INTAKE_TRIAGE' AND status = 'OPEN'
        ORDER BY updated_at DESC, id DESC
        LIMIT 51
    """,
    "tracking": """
        SELECT request.id, request.updated_at
        FROM service_requests AS request
        WHERE EXISTS (
            SELECT 1 FROM request_route_selections AS route
            WHERE route.request_id = request.id
              AND route.position = 0
              AND route.unit_id = CAST(:triage_unit_id AS UUID)
        )
        ORDER BY request.updated_at DESC, request.id DESC
        LIMIT 51
    """,
    "administration": """
        SELECT id, updated_at
        FROM users
        ORDER BY updated_at DESC, id DESC
        LIMIT 51
    """,
    "board": """
        SELECT id, updated_at
        FROM work_packages
        WHERE team_id = CAST(:ssg_team_id AS UUID)
        ORDER BY updated_at DESC, id DESC
        LIMIT 51
    """,
    "history": """
        SELECT id, created_at
        FROM request_events
        WHERE request_id = CAST(:request_id AS UUID)
        ORDER BY created_at DESC, id DESC
        LIMIT 51
    """,
}

REQUIRED_INDEXES = {
    "requests": "ix_service_requests_requester_updated_id",
    "drafts": "ix_request_drafts_requester_updated_id",
    "work": "ix_workflow_tasks_role_status_updated_id",
    "tracking": "ix_request_routes_unit_position_request",
    "administration": "ix_users_updated_id",
    "board": "ix_work_packages_team_updated_id",
    "history": "ix_request_events_request_created_id",
}


async def query_plan_evidence(
    sessions: SessionFactory,
    context: ScaleContext,
) -> dict[str, Any]:
    triage_unit_id = next(iter(context.triage_actor.organisation_unit_ids), None)
    if triage_unit_id is None:
        raise RuntimeError("the triage actor has no organisation scope")
    parameters = {
        "requester_id": context.requester_id,
        "request_id": context.request_id,
        "ssg_team_id": context.ssg_team_id,
        "triage_unit_id": triage_unit_id,
    }
    async with sessions() as session, session.begin():
        index_rows = (
            await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = current_schema()"
                )
            )
        ).scalars()
        available = set(index_rows)
        results: dict[str, Any] = {}
        for name, query in PLAN_QUERIES.items():
            natural = await _explain(session, query, parameters)
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            index_preferred = await _explain(session, query, parameters)
            await session.execute(text("SET LOCAL enable_seqscan = on"))
            required = REQUIRED_INDEXES[name]
            results[name] = {
                "required_index": required,
                "required_index_available": required in available,
                "natural": _summarise(natural),
                "index_compatibility": _summarise(index_preferred),
                "index_compatibility_uses_required": required
                in _index_names(index_preferred),
            }
        return results


async def _explain(
    session: AsyncSession,
    query: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    value = (
        await session.execute(
            # PLAN_QUERIES is an immutable local mapping and all dynamic values use
            # bound parameters. EXPLAIN cannot be expressed through the ORM.
            text(  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            ),
            parameters,
        )
    ).scalar_one()
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        raise RuntimeError("PostgreSQL returned an unexpected EXPLAIN document")
    return value[0]


def _summarise(document: dict[str, Any]) -> dict[str, Any]:
    plan = document["Plan"]
    return {
        "actual_total_time_ms": plan.get("Actual Total Time"),
        "actual_rows": plan.get("Actual Rows"),
        "execution_time_ms": document.get("Execution Time"),
        "index_names": sorted(_index_names(document)),
        "node_types": sorted(_node_types(plan)),
        "planning_time_ms": document.get("Planning Time"),
        "shared_hit_blocks": int(plan.get("Shared Hit Blocks", 0)),
        "shared_read_blocks": int(plan.get("Shared Read Blocks", 0)),
    }


def _walk(node: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node]
    for child in node.get("Plans", []):
        nodes.extend(_walk(child))
    return nodes


def _index_names(document: dict[str, Any]) -> set[str]:
    return {
        str(node["Index Name"])
        for node in _walk(document["Plan"])
        if "Index Name" in node
    }


def _node_types(plan: dict[str, Any]) -> set[str]:
    return {str(node["Node Type"]) for node in _walk(plan)}
