"""Composition boundary for local synthetic account administration."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.account_request_ports import AccountRequestPort
from mist_service.admin_ports import AdminApplicationPort
from mist_service.auth_service import PasswordHasher
from mist_service.config import Settings
from mist_service.repositories.account_requests import (
    SqlAlchemyAccountRequestRepository,
)
from mist_service.repositories.admin_application import (
    SqlAlchemyAdminApplication,
)
from mist_service.services.account_request_service import AccountRequestService
from mist_service.services.admin_service import AdminService


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
