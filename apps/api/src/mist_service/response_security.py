"""Defence-in-depth headers for direct API responses."""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _harden_csp(existing: str | None) -> str:
    directives = [
        directive.strip()
        for directive in (existing or "").split(";")
        if directive.strip()
        and directive.lstrip().split(maxsplit=1)[0].lower() != "frame-ancestors"
    ]
    directives.append("frame-ancestors 'none'")
    return "; ".join(directives)


class SecurityHeadersMiddleware:
    """Apply non-cacheable API and browser hardening response headers."""

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

        async def hardened_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Content-Security-Policy"] = _harden_csp(
                    headers.get("Content-Security-Policy")
                )
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=()"
                )
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Embedder-Policy"] = "require-corp"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                headers["Cache-Control"] = "no-store"
            await send(message)

        await self._app(scope, receive, hardened_send)
