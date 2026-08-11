"""Persistence adapter for account request submission and review."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.account_request_models import AccountRequest, AccountRequestStatus
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.schemas.account_requests import (
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
