"""Content-minimised correlation and structured logging tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from conftest import ApiHarness
from istari_service.telemetry import _failure_location

ROOT = Path(__file__).parents[3]


def test_container_disables_raw_uvicorn_access_logging() -> None:
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text("utf-8")
    assert '"--no-access-log"' in dockerfile
    assert "docker/dockerfile-upstream:master@sha256:" in dockerfile


async def test_valid_correlation_is_returned_and_logs_only_the_route_template(
    api_harness: ApiHarness,
    caplog,
) -> None:
    correlation = str(uuid4())
    with caplog.at_level(logging.INFO, logger="istari_service.access"):
        response = await api_harness.client.get(
            "/health",
            headers={"X-Correlation-ID": correlation},
        )
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation
    event = json.loads(caplog.records[-1].message)
    assert event == {
        "correlationId": correlation,
        "durationMs": event["durationMs"],
        "event": "http_request",
        "method": "GET",
        "route": "/health",
        "status": 200,
    }
    assert event["durationMs"] >= 0


async def test_invalid_correlation_and_unmatched_path_are_not_reflected_in_logs(
    api_harness: ApiHarness,
    caplog,
) -> None:
    unsafe_value = "not-valid-user-supplied"
    sensitive_path = f"/not-a-route/{uuid4()}"
    with caplog.at_level(logging.INFO, logger="istari_service.access"):
        response = await api_harness.client.get(
            sensitive_path,
            headers={"X-Correlation-ID": unsafe_value},
        )
    assert response.status_code == 404
    generated = response.headers["X-Correlation-ID"]
    assert str(UUID(generated)) == generated
    assert unsafe_value not in caplog.records[-1].message
    assert sensitive_path not in caplog.records[-1].message
    assert json.loads(caplog.records[-1].message)["route"] == "unmatched"


async def test_unexpected_failure_is_structured_without_exception_content(
    api_harness: ApiHarness,
    caplog,
) -> None:
    marker = "sensitive-exception-content-must-not-be-logged"
    transport = api_harness.client._transport
    application = transport.app  # type: ignore[attr-defined]

    @application.get("/synthetic-unexpected-failure")
    async def synthetic_failure() -> None:
        raise RuntimeError(marker)

    with (
        caplog.at_level(logging.ERROR, logger="istari_service.access"),
        pytest.raises(RuntimeError, match=marker),
    ):
        await api_harness.client.get("/synthetic-unexpected-failure")

    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "http_request"
    assert event["route"] == "/synthetic-unexpected-failure"
    assert event["status"] == 500
    assert event["exceptionType"] == "builtins.RuntimeError"
    assert event["failureLocation"].startswith("test_telemetry.py:synthetic_failure:")
    assert marker not in caplog.records[-1].message


def test_failure_location_tolerates_an_exception_without_a_traceback() -> None:
    assert _failure_location(RuntimeError("not logged")) == "unknown"
