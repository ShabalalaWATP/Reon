"""Account-request use cases and privilege boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.account_request_ports import (
    AccountProvisioningPort,
    AccountRequestPort,
)
from istari_service.config import Environment, Settings
from istari_service.domain import Actor
from istari_service.errors import AdministrationUnavailable
from istari_service.models import UserRole
from istari_service.schemas.account_requests import (
    AccountRequestCreate,
    AccountRequestReject,
    AccountRequestView,
)
from istari_service.schemas.admin import AdminUserCreate


class AccountRequestService:
    def __init__(
        self,
        repository: AccountRequestPort,
        settings: Settings,
        admin: AccountProvisioningPort | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._admin = admin

    def _require_demo_accounts(self) -> None:
        if (
            self._settings.environment not in {Environment.LOCAL, Environment.TEST}
            or not self._settings.allow_demo_users
        ):
            raise AdministrationUnavailable()

    async def submit(self, command: AccountRequestCreate) -> None:
        self._require_demo_accounts()
        await self._repository.submit(command)

    async def list(self, actor: Actor) -> list[AccountRequestView]:
        self._require_admin(actor)
        return await self._repository.list()

    async def approve(
        self, actor: Actor, request_id: UUID, expected_version: int
    ) -> AccountRequestView:
        self._require_admin(actor)
        row = await self._repository.pending(request_id, expected_version)
        admin = self._admin
        if admin is None:
            raise AdministrationUnavailable()
        user = await admin.create_user(
            actor,
            AdminUserCreate(
                display_name=row.display_name,
                email=row.contact_email,
                role=UserRole.REQUESTER,
                scope="Customer",
                organisation_unit_ids=[],
            ),
        )
        return await self._repository.approve(
            row,
            created_user_id=user.id,
            reviewed_by_user_id=actor.id,
            reviewed_at=datetime.now(UTC),
        )

    async def reject(
        self, actor: Actor, request_id: UUID, command: AccountRequestReject
    ) -> AccountRequestView:
        self._require_admin(actor)
        row = await self._repository.pending(request_id, command.expected_version)
        return await self._repository.reject(
            row,
            decision_note=command.decision_note,
            reviewed_by_user_id=actor.id,
            reviewed_at=datetime.now(UTC),
        )

    def _require_admin(self, actor: Actor) -> None:
        self._require_demo_accounts()
        if self._admin is None:
            raise AdministrationUnavailable()
        self._admin.authorise(actor)
