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

    invalid_messages: list[dict[str, object]] = [
        {"type": "http.request", "body": b"ok", "more_body": False},
        {"type": "http.disconnect"},
    ]

    async def invalid_length_receive() -> dict[str, object]:
        return invalid_messages.pop(0)

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


async def test_product_upload_requires_a_declared_bounded_size() -> None:
    calls: list[str] = []
    sent: list[dict[str, object]] = []

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        calls.append("forwarded")

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"content"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(
        app,
        max_bytes=10,
        product_upload_max_bytes=5,
    )
    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/api/v1/product-packages/package/uploads/intent/content",
        "headers": [],
    }
    await middleware(scope, receive, send)  # type: ignore[arg-type]
    assert calls == []
    assert sent[0]["status"] == 411

    sent.clear()
    scope["headers"] = [(b"content-length", b"6")]
    await middleware(scope, receive, send)  # type: ignore[arg-type]
    assert calls == []
    assert sent[0]["status"] == 413


async def test_product_upload_is_streamed_to_the_storage_boundary() -> None:
    received: list[bytes] = []

    async def app(
        _scope: Any,
        receive: Callable[[], Awaitable[Any]],
        _send: Any,
    ) -> None:
        received.append((await receive())["body"])

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"content", "more_body": False}

    async def send(_message: object) -> None:
        return None

    middleware = RequestBodyLimitMiddleware(
        app,
        max_bytes=1,
        product_upload_max_bytes=10,
    )
    await middleware(  # type: ignore[arg-type]
        {
            "type": "http",
            "method": "PUT",
            "path": "/api/v1/product-packages/package/uploads/intent/content",
            "headers": [(b"content-length", b"7")],
        },
        receive,
        send,
    )
    assert received == [b"content"]
