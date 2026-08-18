"""Persistence-independent contracts for bounded platform administration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from mist_service.models import UserRole
from mist_service.organisation_models import OrganisationKind, StaffingStatus
from mist_service.schemas.admin import AdminUser
from mist_service.schemas.organisation import OrganisationUnitView
from mist_service.team_models import WorkspacePosition


@dataclass(frozen=True, slots=True)
class AdminIdentityRecord:
    id: UUID
    display_name: str
    email: str
    role: UserRole
    scope: str
    is_active: bool
    version: int


@dataclass(frozen=True, slots=True)
class AdminUnitRecord:
    id: UUID
    name: str
    code: str
    kind: OrganisationKind
    parent_id: UUID | None
    staffing_status: StaffingStatus
    version: int


@dataclass(frozen=True, slots=True)
class CreateIdentityChange:
    actor_id: UUID
    username: str
    email: str
    display_name: str
    password_hash: str
    role: UserRole
    scope: str
    customer_context_enabled: bool
    unit_ids: frozenset[UUID]
    workspace_position: WorkspacePosition | None


@dataclass(frozen=True, slots=True)
class UpdateIdentityChange:
    actor_id: UUID
    user_id: UUID
    expected_version: int
    display_name: str
    email: str
    role: UserRole
    scope: str
    customer_context_enabled: bool
    unit_ids: frozenset[UUID]
    old_unit_ids: frozenset[UUID]
    workspace_position: WorkspacePosition | None
    security_change: bool
    changed_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StatusIdentityChange:
    actor_id: UUID
    user_id: UUID
    expected_version: int
    is_active: bool
    unit_ids: frozenset[UUID]


class AdminQueryPort(Protocol):
    async def list_user_views(self, query: str | None) -> list[AdminUser]: ...

    async def page_user_views(
        self, query: str | None, *, limit: int, cursor: str | None
    ) -> tuple[list[AdminUser], str | None]: ...

    async def user_view(self, user_id: UUID) -> AdminUser: ...

    async def load_units(
        self, unit_ids: list[UUID], *, role: UserRole
    ) -> list[AdminUnitRecord]: ...


class AdminIdentityPolicyPort(Protocol):
    async def next_username(self) -> str: ...

    async def ensure_unique_email(
        self, email: str, *, excluding_user_id: UUID | None = None
    ) -> None: ...

    async def lock_identity_sequence(self) -> None: ...

    async def locked_user(
        self, user_id: UUID, expected_version: int
    ) -> AdminIdentityRecord: ...

    async def membership_ids(self, user_id: UUID) -> set[UUID]: ...

    async def workspace_position(self, user_id: UUID) -> WorkspacePosition | None: ...

    async def require_another_admin(self, user_id: UUID) -> None: ...

    async def reject_active_work(self, user_id: UUID) -> None: ...


class AdminMutationPort(Protocol):
    async def create_identity(self, change: CreateIdentityChange) -> AdminUser: ...

    async def update_identity(self, change: UpdateIdentityChange) -> AdminUser: ...

    async def set_identity_status(self, change: StatusIdentityChange) -> AdminUser: ...

    async def locked_unit(
        self, unit_id: UUID, expected_version: int
    ) -> AdminUnitRecord: ...

    async def ensure_unique_sibling_name(
        self, unit_id: UUID, expected_version: int, name: str
    ) -> None: ...

    async def rename_unit(
        self,
        unit_id: UUID,
        expected_version: int,
        *,
        old_name: str,
        new_name: str,
        actor_id: UUID,
    ) -> OrganisationUnitView: ...
