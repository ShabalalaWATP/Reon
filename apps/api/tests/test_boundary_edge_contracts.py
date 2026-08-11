"""Small boundary cases that must fail closed or preserve protocol behaviour."""

from __future__ import annotations

import pytest

from istari_service.config import Settings
from istari_service.schemas.account_requests import AccountRequestCreate
from istari_service.schemas.related_records import RequestLinkCreate
from istari_service.telemetry import OperationalTelemetryMiddleware
from istari_service.workflow.types import CancelProcessCommand


def test_blank_and_short_boundary_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        AccountRequestCreate.trim_required_text("  ")
    with pytest.raises(ValueError, match="at least 10"):
        RequestLinkCreate.reason_is_meaningful("          ")
    with pytest.raises(ValueError, match="must not be empty"):
        CancelProcessCommand("   ")
    assert Settings().audit_hmac_key_bytes is None


async def test_telemetry_passes_non_http_scopes_through_unchanged() -> None:
    received: list[dict[str, object]] = []

    async def app(scope, _receive, _send) -> None:
        received.append(scope)

    async def receive() -> dict[str, object]:
        return {}

    async def send(_message: dict[str, object]) -> None:
        return None

    scope = {"type": "lifespan"}
    middleware = OperationalTelemetryMiddleware(app)
    await middleware(scope, receive, send)  # type: ignore[arg-type]
    assert received == [scope]
