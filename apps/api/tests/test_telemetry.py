"""Content-minimised correlation and structured logging tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

from conftest import ApiHarness

ROOT = Path(__file__).parents[3]


def test_container_disables_raw_uvicorn_access_logging() -> None:
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text("utf-8")
    assert '"--no-access-log"' in dockerfile
    assert "docker/dockerfile:1.7@sha256:" in dockerfile


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
