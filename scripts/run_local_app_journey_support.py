"""Shared bounded HTTP helpers for live application journey scripts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class Actor:
    username: str
    client: httpx.AsyncClient
    csrf_token: str

    async def get(self, path: str) -> Any:
        response = await self.client.get(path)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, body: dict[str, object] | None = None) -> Any:
        response = await self.client.post(
            path, json=body, headers={"X-CSRF-Token": self.csrf_token}
        )
        response.raise_for_status()
        return response.json() if response.content else None


async def login(base_url: str, origin: str, username: str, password: str) -> Actor:
    client = httpx.AsyncClient(
        base_url=base_url, headers={"Origin": origin}, timeout=httpx.Timeout(15)
    )
    response = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    response.raise_for_status()
    return Actor(username, client, response.json()["csrfToken"])


async def claim(actor: Actor, item: dict[str, Any]) -> dict[str, Any]:
    return await actor.post(f"/work-items/{item['id']}/claim")


async def complete(
    actor: Actor, item: dict[str, Any], command: dict[str, object]
) -> None:
    await actor.post(f"/work-items/{item['id']}/complete", command)


async def destination(actor: Actor, item: dict[str, Any], code: str) -> str:
    options = await actor.get(f"/work-items/{item['id']}/routing-options")
    matches = [option for option in options["items"] if option["code"] == code]
    if len(matches) != 1:
        raise RuntimeError(f"expected one configured destination for {code}")
    return str(matches[0]["id"])
