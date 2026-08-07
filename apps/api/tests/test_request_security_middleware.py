"""Low-level branches for bounded body handling outside ordinary HTTP flows."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from istari_service.request_security import RequestBodyLimitMiddleware


async def test_non_http_scope_is_forwarded_unchanged() -> None:
    calls: list[str] = []

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        calls.append("forwarded")

    async def receive() -> dict[str, str]:
        return {"type": "lifespan.startup"}

    async def send(_message: object) -> None:
        return None

    middleware = RequestBodyLimitMiddleware(app, max_bytes=1_024)
    await middleware({"type": "lifespan"}, receive, send)  # type: ignore[arg-type]
    assert calls == ["forwarded"]


async def test_invalid_length_and_disconnect_are_safely_replayed() -> None:
    received: list[str] = []

    async def app(
        _scope: Any,
        receive: Callable[[], Awaitable[Any]],
        _send: Any,
    ) -> None:
        received.append((await receive())["type"])
        received.append((await receive())["type"])

    async def invalid_length_receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"ok", "more_body": False}

    async def send(_message: object) -> None:
        return None

    middleware = RequestBodyLimitMiddleware(app, max_bytes=1_024)
    await middleware(  # type: ignore[arg-type]
        {
            "type": "http",
            "headers": [(b"content-length", b"invalid")],
        },
        invalid_length_receive,
        send,
    )
    assert received == ["http.request", "http.disconnect"]

    async def disconnected() -> dict[str, str]:
        return {"type": "http.disconnect"}

    received.clear()
    await middleware(  # type: ignore[arg-type]
        {"type": "http", "headers": []},
        disconnected,
        send,
    )
    assert received == ["http.disconnect", "http.disconnect"]
