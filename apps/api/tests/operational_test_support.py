"""Shared fakes for privileged operational entry-point tests."""

from __future__ import annotations

import argparse
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    def begin(self) -> AbstractAsyncContextManager[FakeSession]:
        return FakeAsyncContext(self)


class FakeAsyncContext(AbstractAsyncContextManager[Any]):
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_error: object) -> None:
        return None


class FakeEngine:
    def __init__(self, dialect: str = "postgresql") -> None:
        self.connection = SimpleNamespace(
            dialect=SimpleNamespace(name=dialect), execute=self.execute
        )
        self.statements: list[str] = []
        self.disposed = False

    def begin(self) -> FakeAsyncContext:
        return FakeAsyncContext(self.connection)

    async def execute(self, statement: object) -> None:
        self.statements.append(str(statement))

    async def dispose(self) -> None:
        self.disposed = True


@dataclass(frozen=True)
class FakeReport:
    valid: bool = True
    status: str = "ok"
    value: str = "safe"


def arguments(job: str, **values: object) -> argparse.Namespace:
    return argparse.Namespace(job=job, **values)
