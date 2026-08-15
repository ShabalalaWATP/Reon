"""HTTP actor client and work-queue operations for the demo journeys."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

RETRYABLE = {429, 500, 502, 503}


@dataclass(slots=True)
class Actor:
    username: str
    password: str
    client: httpx.AsyncClient
    csrf_token: str
    lock: asyncio.Lock

    async def relogin(self) -> None:
        async with self.lock:
            for _attempt in range(20):
                response = await self.client.post(
                    "/auth/login",
                    json={"username": self.username, "password": self.password},
                )
                if response.status_code == 429:
                    await asyncio.sleep(12)
                    continue
                response.raise_for_status()
                self.csrf_token = response.json()["csrfToken"]
                return
            raise RuntimeError(f"login for {self.username} stayed rate-limited")

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(5):
            response = await self.client.request(
                method, path, headers={"X-CSRF-Token": self.csrf_token}, **kwargs
            )
            if response.status_code == 401:
                await self.relogin()
                continue
            if response.status_code in RETRYABLE and attempt < 4:
                await asyncio.sleep(3 + attempt * 3)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"{method} {path} kept failing for {self.username}")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return (await self._send("GET", path, params=params)).json()

    async def post(self, path: str, body: dict[str, object] | None = None) -> Any:
        response = await self._send("POST", path, json=body)
        return response.json() if response.content else None


async def login(base_url: str, origin: str, username: str, password: str) -> Actor:
    client = httpx.AsyncClient(
        base_url=base_url, headers={"Origin": origin}, timeout=httpx.Timeout(30)
    )
    actor = Actor(username, password, client, "", asyncio.Lock())
    await actor.relogin()
    return actor


async def wait_for_item(
    actor: Actor, request_id: str, stage: str, attempts: int = 120
) -> dict[str, Any]:
    for _attempt in range(attempts):
        cursor: str | None = None
        while True:
            data = await actor.get(
                "/work-items", params={"cursor": cursor} if cursor else {}
            )
            for item in data["items"]:
                if item["requestId"] == request_id and item["stage"] == stage:
                    return item
            cursor = data.get("nextCursor")
            if not cursor:
                break
        await asyncio.sleep(0.5)
    raise RuntimeError(
        f"{actor.username} did not receive {stage} work for request {request_id}"
    )


async def claim(actor: Actor, item: dict[str, Any]) -> None:
    if item.get("assigneeId"):
        return
    await actor.post(f"/work-items/{item['id']}/claim")


async def complete(actor: Actor, item: dict[str, Any], command: dict[str, object]) -> None:
    try:
        await actor.post(f"/work-items/{item['id']}/complete", command)
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 404:
            raise
        # A retried completion can find the task already finished; carry on.


async def destination(actor: Actor, item: dict[str, Any], code: str) -> str:
    options = await actor.get(f"/work-items/{item['id']}/routing-options")
    matches = [option for option in options["items"] if option["code"] == code]
    if len(matches) != 1:
        raise RuntimeError(f"expected one configured destination for {code}")
    return str(matches[0]["id"])
