"""Account-request use cases and privilege boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.account_request_models import AccountRequestStatus
from istari_service.admin_audit import append_admin_event
from istari_service.config import Environment, Settings
from istari_service.domain import Actor
from istari_service.errors import AdministrationUnavailable
from istari_service.models import UserRole
from istari_service.repositories.account_requests import (
    SqlAlchemyAccountRequestRepository,
)
from istari_service.schemas.account_requests import (
    AccountRequestCreate,
    AccountRequestReject,
    AccountRequestView,
)
from istari_service.schemas.admin import AdminUserCreate
from istari_service.services.admin_service import AdminService


class AccountRequestService:
    def __init__(
        self,
        repository: SqlAlchemyAccountRequestRepository,
        settings: Settings,
        admin: AdminService | None = None,
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
        row = await self._repository.locked(request_id, expected_version)
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
        row.status = AccountRequestStatus.APPROVED
        row.created_user_id = user.id
        row.reviewed_by_user_id = actor.id
        row.reviewed_at = datetime.now(UTC)
        row.version += 1
        await self._audit(actor, row.id, "ACCOUNT_REQUEST_APPROVED")
        await self._repository.session.flush()
        await self._repository.session.refresh(row)
        return AccountRequestView.model_validate(row)

    async def reject(
        self, actor: Actor, request_id: UUID, command: AccountRequestReject
    ) -> AccountRequestView:
        self._require_admin(actor)
        row = await self._repository.locked(request_id, command.expected_version)
        row.status = AccountRequestStatus.REJECTED
        row.decision_note = command.decision_note.strip()
        row.reviewed_by_user_id = actor.id
        row.reviewed_at = datetime.now(UTC)
        row.version += 1
        await self._audit(actor, row.id, "ACCOUNT_REQUEST_REJECTED")
        await self._repository.session.flush()
        await self._repository.session.refresh(row)
        return AccountRequestView.model_validate(row)

    def _require_admin(self, actor: Actor) -> None:
        self._require_demo_accounts()
        if self._admin is None:
            raise AdministrationUnavailable()
        self._admin.authorise(actor)

    async def _audit(self, actor: Actor, target_id: UUID, action: str) -> None:
        await append_admin_event(
            self._repository.session,
            actor_id=actor.id,
            action=action,
            target_type="ACCOUNT_REQUEST",
            target_id=target_id,
            changed_fields=["status"],
            summary="Synthetic Customer account request reviewed.",
        )
