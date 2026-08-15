"""Application contracts for synthetic account-request review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.domain import Actor
from mist_service.schemas.account_requests import (
    AccountRequestCreate,
    AccountRequestView,
)
from mist_service.schemas.admin import AdminUser, AdminUserCreate


@dataclass(frozen=True, slots=True)
class PendingAccountRequest:
    id: UUID
    display_name: str
    contact_email: str
    version: int


class AccountRequestPort(Protocol):
    async def submit(self, command: AccountRequestCreate) -> None: ...

    async def list(self) -> list[AccountRequestView]: ...

    async def pending(
        self, request_id: UUID, expected_version: int
    ) -> PendingAccountRequest: ...

    async def approve(
        self,
        request: PendingAccountRequest,
        *,
        created_user_id: UUID,
        reviewed_by_user_id: UUID,
        reviewed_at: datetime,
    ) -> AccountRequestView: ...

    async def reject(
        self,
        request: PendingAccountRequest,
        *,
        decision_note: str,
        reviewed_by_user_id: UUID,
        reviewed_at: datetime,
    ) -> AccountRequestView: ...


class AccountProvisioningPort(Protocol):
    def authorise(self, actor: Actor) -> None: ...

    async def create_user(
        self, actor: Actor, payload: AdminUserCreate
    ) -> AdminUser: ...
