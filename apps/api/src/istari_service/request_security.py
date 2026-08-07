"""Direct-API request size enforcement independent of an edge proxy."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    """Reject declared or streamed HTTP bodies beyond a configured byte limit."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self._max_bytes:
            await _send_error(scope, receive, send, status_code=413)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                await self._app(scope, _replay(message), send)
                return
            body.extend(message.get("body", b""))
            if len(body) > self._max_bytes:
                await _send_error(scope, receive, send, status_code=413)
                return
            if not message.get("more_body", False):
                break
        await self._app(
            scope,
            _replay({"type": "http.request", "body": bytes(body)}),
            send,
        )


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name.lower() == b"content-length":
            try:
                parsed = int(value)
            except ValueError:
                return None
            return max(parsed, 0)
    return None


def _replay(message: Message) -> Receive:
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return message
        return {"type": "http.disconnect"}

    return receive


async def _send_error(
    scope: Scope,
    receive: Receive,
    send: Send,
    *,
    status_code: int,
) -> None:
    response = JSONResponse(
        status_code=status_code,
        content={
            "detail": {
                "code": "REQUEST_TOO_LARGE",
                "message": "The request body exceeds the permitted size.",
            }
        },
    )
    await response(scope, receive, send)
