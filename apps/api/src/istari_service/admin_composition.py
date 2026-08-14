"""Composition boundary for local synthetic account administration."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.account_request_ports import AccountRequestPort
from istari_service.admin_ports import AdminApplicationPort
from istari_service.auth_service import PasswordHasher
from istari_service.config import Settings
from istari_service.repositories.account_requests import (
    SqlAlchemyAccountRequestRepository,
)
from istari_service.repositories.admin_application import (
    SqlAlchemyAdminApplication,
)
from istari_service.services.account_request_service import AccountRequestService
from istari_service.services.admin_service import AdminService


def admin_service(
    session: AsyncSession, settings: Settings, hasher: PasswordHasher
) -> AdminService:
    return AdminService(
        cast(AdminApplicationPort, SqlAlchemyAdminApplication(session)),
        settings,
        hasher,
    )


def account_request_service(
    session: AsyncSession,
    settings: Settings,
    admin: AdminService | None = None,
) -> AccountRequestService:
    return AccountRequestService(
        cast(AccountRequestPort, SqlAlchemyAccountRequestRepository(session)),
        settings,
        admin,
    )
