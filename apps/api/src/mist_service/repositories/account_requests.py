"""Persistence adapter for account request submission and review."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.account_request_models import AccountRequest, AccountRequestStatus
from mist_service.account_request_ports import PendingAccountRequest
from mist_service.admin_audit import append_admin_event
from mist_service.errors import ObjectNotFound, StaleVersion
from mist_service.schemas.account_requests import (
    AccountRequestCreate,
    AccountRequestView,
)


class SqlAlchemyAccountRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit(self, command: AccountRequestCreate) -> None:
        email = str(command.contact_email).strip().lower()
        existing = await self.session.scalar(
            select(AccountRequest.id).where(AccountRequest.contact_email == email)
        )
        if existing is None:
            self.session.add(
                AccountRequest(
                    display_name=command.display_name,
                    contact_email=email,
                    reason=command.reason,
                )
            )
            await self.session.flush()

    async def list(self) -> list[AccountRequestView]:
        rows = list(
            await self.session.scalars(
                select(AccountRequest).order_by(AccountRequest.created_at.desc())
            )
        )
        return [AccountRequestView.model_validate(row) for row in rows]

    async def locked(self, request_id: UUID, expected_version: int) -> AccountRequest:
        row = await self.session.scalar(
            select(AccountRequest)
            .where(AccountRequest.id == request_id)
            .with_for_update()
        )
        if row is None:
            raise ObjectNotFound()
        if row.version != expected_version:
            raise StaleVersion()
        if row.status is not AccountRequestStatus.PENDING:
            raise StaleVersion()
        return row

    async def pending(
        self, request_id: UUID, expected_version: int
    ) -> PendingAccountRequest:
        row = await self.locked(request_id, expected_version)
        return PendingAccountRequest(
            row.id, row.display_name, row.contact_email, row.version
        )

    async def approve(
        self,
        request: PendingAccountRequest,
        *,
        created_user_id: UUID,
        reviewed_by_user_id: UUID,
        reviewed_at: datetime,
    ) -> AccountRequestView:
        row = await self.locked(request.id, request.version)
        row.status = AccountRequestStatus.APPROVED
        row.created_user_id = created_user_id
        row.reviewed_by_user_id = reviewed_by_user_id
        row.reviewed_at = reviewed_at
        row.version += 1
        return await self._reviewed(
            row, reviewed_by_user_id, "ACCOUNT_REQUEST_APPROVED"
        )

    async def reject(
        self,
        request: PendingAccountRequest,
        *,
        decision_note: str,
        reviewed_by_user_id: UUID,
        reviewed_at: datetime,
    ) -> AccountRequestView:
        row = await self.locked(request.id, request.version)
        row.status = AccountRequestStatus.REJECTED
        row.decision_note = decision_note.strip()
        row.reviewed_by_user_id = reviewed_by_user_id
        row.reviewed_at = reviewed_at
        row.version += 1
        return await self._reviewed(
            row, reviewed_by_user_id, "ACCOUNT_REQUEST_REJECTED"
        )

    async def _reviewed(
        self, row: AccountRequest, actor_id: UUID, action: str
    ) -> AccountRequestView:
        await append_admin_event(
            self.session,
            actor_id=actor_id,
            action=action,
            target_type="ACCOUNT_REQUEST",
            target_id=row.id,
            changed_fields=["status"],
            summary="Synthetic Customer account request reviewed.",
        )
        await self.session.flush()
        await self.session.refresh(row)
        return AccountRequestView.model_validate(row)
