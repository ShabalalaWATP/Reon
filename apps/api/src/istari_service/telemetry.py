"""Content-minimised request correlation and structured access logging."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("istari_service.access")


class OperationalTelemetryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        correlation_id = _correlation_id(scope)
        started = perf_counter()
        status_code = 500

        async def correlated_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self._app(scope, receive, correlated_send)
        finally:
            route = scope.get("route")
            logger.info(
                json.dumps(
                    {
                        "correlationId": correlation_id,
                        "durationMs": round((perf_counter() - started) * 1_000, 3),
                        "event": "http_request",
                        "method": scope.get("method", "UNKNOWN"),
                        "route": getattr(route, "path", "unmatched"),
                        "status": status_code,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


def _correlation_id(scope: Scope) -> str:
    supplied = next(
        (
            value
            for name, value in scope["headers"]
            if name.lower() == b"x-correlation-id"
        ),
        None,
    )
    if supplied is not None:
        try:
            return str(UUID(supplied.decode("ascii")))
        except (UnicodeDecodeError, ValueError):
            pass
    return str(uuid4())
