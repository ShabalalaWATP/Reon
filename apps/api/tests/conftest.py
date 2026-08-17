"""Shared isolated API fixtures."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.auth_service import PasswordHasher
from mist_service.config import Environment, Settings
from mist_service.configuration_models import ApprovedWorkflowDefinition
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.main import create_app
from mist_service.models import User
from mist_service.organisation_models import OrganisationUnit
from mist_service.workflow.fake import FakeWorkflowEngine
from mist_service.workflow.lookup import TaskLookupPolicy
from mist_service.workflow_dispatch import WorkflowOutboxDispatcher

DEMO_PASSWORD = "Synthetic-demo-passphrase-42"
ORIGIN = "http://test.local"
COVERAGE_GATE = 95.0


@pytest.fixture(scope="session", autouse=True)
def isolate_tests_from_local_dotenv() -> Iterator[None]:
    """Keep developer runtime features out of deterministic test settings."""
    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    try:
        yield
    finally:
        Settings.model_config["env_file"] = original_env_file


def _percentage(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered / total * 100


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtestloop(session: pytest.Session) -> Any:
    """Enforce line and branch coverage as independent quality gates."""
    yield
    config = session.config
    if config.getoption("no_cov"):
        return
    fail_under = config.getoption("cov_fail_under")
    if fail_under is None or float(fail_under) < COVERAGE_GATE:
        return

    report_path = Path(config.rootpath) / "coverage.json"
    terminal = config.pluginmanager.getplugin("terminalreporter")
    if not report_path.exists():
        terminal.write_line("Independent coverage gate could not read coverage.json.")
        session.testsfailed += 1
        return

    totals = json.loads(report_path.read_text(encoding="utf-8"))["totals"]
    line_coverage = _percentage(totals["covered_lines"], totals["num_statements"])
    branch_coverage = _percentage(totals["covered_branches"], totals["num_branches"])
    terminal.write_sep("=", "independent coverage gates")
    terminal.write_line(f"Line coverage: {line_coverage:.2f}% (required 95.00%)")
    terminal.write_line(f"Branch coverage: {branch_coverage:.2f}% (required 95.00%)")
    if line_coverage < COVERAGE_GATE or branch_coverage < COVERAGE_GATE:
        session.testsfailed += 1


def request_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Prepare a synthetic service summary",
        "description": (
            "Provide a structured summary for a fictional planning exercise."
        ),
        "questionToAnswer": "What does the synthetic evidence show?",
        "desiredOutcome": "A clear summary that supports a synthetic decision.",
        "backgroundContext": "All context is fictional and suitable for this demo.",
        "subjectAreaOrLocation": "Synthetic subject area",
        "coverageStart": (datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
        "coverageEnd": (datetime.now(UTC).date() + timedelta(days=7)).isoformat(),
        "customerUrgency": "ROUTINE",
        "supportedActivityOrDecision": "A fictional planning decision.",
        "requiredBy": (datetime.now(UTC).date() + timedelta(days=14)).isoformat(),
        "requiredByReason": "The fictional review takes place after this date.",
        "preferredDeliverableType": "Written summary",
        "successCriteria": "The summary addresses every stated point clearly.",
        "constraintsOrCaveats": "No known constraints.",
        "supportingInformation": "No supporting material is available.",
        "sensitivity": "STANDARD",
        "handlingInstructions": "Use only within this synthetic demonstration.",
    }
    payload.update(updates)
    return payload


@dataclass(slots=True)
class ApiHarness:
    client: httpx.AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    workflow: FakeWorkflowEngine
    settings: Settings
    csrf_token: str = ""

    async def login(
        self, username: str, password: str = DEMO_PASSWORD
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        self.csrf_token = body["csrfToken"]
        return body

    def mutation_headers(self, *, origin: str = ORIGIN) -> dict[str, str]:
        return {"Origin": origin, "X-CSRF-Token": self.csrf_token}

    async def elevate(self, password: str = DEMO_PASSWORD) -> dict[str, Any]:
        response = await self.client.post(
            "/api/v1/auth/elevate",
            json={"password": password},
            headers=self.mutation_headers(),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        self.csrf_token = body["csrfToken"]
        return body

    async def user_id(self, username: str) -> UUID:
        async with self.sessions() as session:
            user_id = await session.scalar(
                select(User.id).where(User.username == username)
            )
        assert user_id is not None
        return user_id

    async def unit_id(self, code: str) -> UUID:
        async with self.sessions() as session:
            unit_id = await session.scalar(
                select(OrganisationUnit.id).where(OrganisationUnit.code == code)
            )
        assert unit_id is not None
        return unit_id

    async def dispatch_start(self) -> bool:
        dispatcher = WorkflowOutboxDispatcher(
            self.sessions,
            self.workflow,
            process_id=self.settings.camunda_process_id,
            lookup_policy=TaskLookupPolicy(
                max_attempts=3,
                initial_delay_seconds=0,
                backoff_multiplier=1,
                maximum_delay_seconds=0,
            ),
        )
        return await dispatcher.dispatch_once()


@pytest.fixture
async def api_harness() -> ApiHarness:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        trusted_origins=frozenset({ORIGIN}),
        web_origin=ORIGIN,
        allow_demo_users=True,
        demo_user_password=DEMO_PASSWORD,
        session_cookie_secure=False,
        session_ttl_seconds=3600,
        session_idle_seconds=900,
        action_workspace_enabled=True,
        notifications_enabled=True,
        managed_products_enabled=True,
        configuration_admin_enabled=True,
        planning_evolution_enabled=True,
        statistics_evolution_enabled=True,
    )
    database_engine = create_database_engine(settings)
    await create_schema(database_engine)
    sessions = create_session_factory(database_engine)
    workflow = FakeWorkflowEngine()
    app = create_app(
        settings=settings,
        session_factory=sessions,
        workflow_engine=workflow,
        password_hasher=PasswordHasher(
            time_cost=1,
            memory_cost=8_192,
            parallelism=1,
        ),
    )
    async with app.router.lifespan_context(app):
        async with sessions() as session, session.begin():
            approved_workflow = await session.scalar(
                select(ApprovedWorkflowDefinition).where(
                    ApprovedWorkflowDefinition.process_id
                    == settings.camunda_process_id,
                    ApprovedWorkflowDefinition.process_version == 1,
                )
            )
            assert approved_workflow is not None
            # The fake engine is the approved deployment for isolated API tests.
            approved_workflow.is_available = True
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url=ORIGIN,
        ) as client:
            yield ApiHarness(client, sessions, workflow, settings)
    await database_engine.dispose()
