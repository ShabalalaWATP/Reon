"""SQLAlchemy composition adapter for administrator application contracts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.admin_audit import append_admin_event
from istari_service.admin_management_grants import synchronise_admin_manager_grant
from istari_service.admin_ports import (
    AdminIdentityRecord,
    AdminUnitRecord,
    CreateIdentityChange,
    StatusIdentityChange,
    UpdateIdentityChange,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.schemas.admin import AdminUser
from istari_service.schemas.organisation import OrganisationUnitView
from istari_service.team_membership_admin import align_admin_workspace_memberships
from istari_service.team_models import WorkspacePosition


class SqlAlchemyAdminApplication:
    """Expose use-case capabilities without leaking ORM entities or sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SqlAlchemyAdminRepository(session)

    async def list_user_views(self, query: str | None) -> list[AdminUser]:
        return await self._repository.views(await self._repository.list_users(query))

    async def page_user_views(
        self, query: str | None, *, limit: int, cursor: str | None
    ) -> tuple[list[AdminUser], str | None]:
        users, next_cursor = await self._repository.page_users(
            query, limit=limit, cursor=cursor
        )
        return await self._repository.views(users), next_cursor

    async def user_view(self, user_id: UUID) -> AdminUser:
        user = await self._repository.get_user(user_id)
        return (await self._repository.views([user]))[0]

    async def load_units(
        self, unit_ids: list[UUID], *, role: UserRole
    ) -> list[AdminUnitRecord]:
        units = await self._repository.load_units(unit_ids, role=role)
        return [_unit(unit) for unit in units]

    async def next_username(self) -> str:
        return await self._repository.next_username()

    async def ensure_unique_email(
        self, email: str, *, excluding_user_id: UUID | None = None
    ) -> None:
        await self._repository.ensure_unique_email(
            email, excluding_user_id=excluding_user_id
        )

    async def lock_identity_sequence(self) -> None:
        await self._repository.lock_identity_sequence()

    async def locked_user(
        self, user_id: UUID, expected_version: int
    ) -> AdminIdentityRecord:
        user = await self._repository.locked_user(user_id, expected_version)
        return _identity(user)

    async def membership_ids(self, user_id: UUID) -> set[UUID]:
        return await self._repository.membership_ids(user_id)

    async def workspace_position(self, user_id: UUID) -> WorkspacePosition | None:
        return await self._repository.workspace_position(user_id)

    async def require_another_admin(self, user_id: UUID) -> None:
        await self._repository.require_another_admin(user_id)

    async def reject_active_work(self, user_id: UUID) -> None:
        await self._repository.reject_active_work(user_id)

    async def create_identity(self, change: CreateIdentityChange) -> AdminUser:
        units = await self._repository.load_units(
            list(change.unit_ids), role=change.role
        )
        user = User(
            username=change.username,
            email=change.email,
            display_name=change.display_name,
            password_hash=change.password_hash,
            role=change.role,
            scope=change.scope,
            customer_context_enabled=change.customer_context_enabled,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        await align_admin_workspace_memberships(
            self._session,
            user=user,
            next_unit_ids=set(change.unit_ids),
            workspace_position=change.workspace_position,
            actor_id=change.actor_id,
        )
        await self._repository.replace_memberships(user.id, units)
        await self._sync_grant(user, change.actor_id, set(change.unit_ids))
        await self._repository.recalculate_teams(set(change.unit_ids))
        await self._audit(
            change.actor_id,
            "USER_CREATED",
            user.id,
            ["displayName", "email", "role", "scope", "memberships"],
            "Synthetic account created.",
        )
        await self._session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def update_identity(self, change: UpdateIdentityChange) -> AdminUser:
        user = await self._repository.locked_user(
            change.user_id, change.expected_version
        )
        units = await self._repository.load_units(
            list(change.unit_ids), role=change.role
        )
        await align_admin_workspace_memberships(
            self._session,
            user=user,
            next_unit_ids=set(change.unit_ids),
            workspace_position=change.workspace_position,
            actor_id=change.actor_id,
        )
        if user.email != change.email:
            user.assistance_email_hash = None
            user.assistance_email_key_id = None
        user.display_name = change.display_name
        user.email = change.email
        user.role = change.role
        user.scope = change.scope
        user.customer_context_enabled = change.customer_context_enabled
        user.version += 1
        if change.security_change:
            user.credential_version += 1
            await self._repository.revoke_sessions(user.id)
        await self._repository.replace_memberships(user.id, units)
        await self._sync_grant(user, change.actor_id, set(change.unit_ids))
        await self._repository.recalculate_teams(
            set(change.old_unit_ids | change.unit_ids)
        )
        await self._audit(
            change.actor_id,
            "USER_UPDATED",
            user.id,
            list(change.changed_fields),
            "Synthetic account metadata updated.",
        )
        await self._session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def set_identity_status(self, change: StatusIdentityChange) -> AdminUser:
        user = await self._repository.locked_user(
            change.user_id, change.expected_version
        )
        user.is_active = change.is_active
        user.version += 1
        user.credential_version += 1
        user.failed_login_count = 0
        user.locked_until = None
        await self._repository.revoke_sessions(user.id)
        await self._session.flush()
        await self._sync_grant(user, change.actor_id, set(change.unit_ids))
        await self._repository.recalculate_teams(set(change.unit_ids))
        await self._audit(
            change.actor_id,
            "USER_ACTIVATED" if change.is_active else "USER_DEACTIVATED",
            user.id,
            ["isActive"],
            "Synthetic account access status updated.",
        )
        await self._session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def locked_unit(
        self, unit_id: UUID, expected_version: int
    ) -> AdminUnitRecord:
        unit = await self._repository.locked_unit(unit_id, expected_version)
        return _unit(unit)

    async def ensure_unique_sibling_name(
        self, unit_id: UUID, expected_version: int, name: str
    ) -> None:
        unit = await self._repository.locked_unit(unit_id, expected_version)
        await self._repository.ensure_unique_sibling_name(unit, name)

    async def rename_unit(
        self,
        unit_id: UUID,
        expected_version: int,
        *,
        old_name: str,
        new_name: str,
        actor_id: UUID,
    ) -> OrganisationUnitView:
        unit = await self._repository.locked_unit(unit_id, expected_version)
        unit.name = new_name
        unit.version += 1
        await self._repository.cascade_unit_rename(
            unit, old_name=old_name, new_name=new_name
        )
        await self._audit(
            actor_id,
            "ORGANISATION_UNIT_RENAMED",
            unit.id,
            ["name"],
            "Organisation display name updated.",
            target_type="ORGANISATION_UNIT",
        )
        await self._session.refresh(unit)
        return OrganisationUnitView.model_validate(unit)

    async def _sync_grant(
        self, user: User, actor_id: UUID, unit_ids: set[UUID]
    ) -> None:
        await synchronise_admin_manager_grant(
            self._session,
            actor_user_id=actor_id,
            subject_user_id=user.id,
            role=user.role,
            unit_ids=unit_ids,
            workspace_position=await self._repository.workspace_position(user.id),
            is_active=user.is_active,
        )

    async def _audit(
        self,
        actor_id: UUID,
        action: str,
        target_id: UUID,
        changed_fields: list[str],
        summary: str,
        *,
        target_type: str = "USER",
    ) -> None:
        await append_admin_event(
            self._session,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            changed_fields=changed_fields,
            summary=summary,
        )


def _identity(user: User) -> AdminIdentityRecord:
    return AdminIdentityRecord(
        user.id,
        user.display_name,
        user.email,
        user.role,
        user.scope,
        user.is_active,
        user.version,
    )


def _unit(unit: OrganisationUnit) -> AdminUnitRecord:
    return AdminUnitRecord(
        unit.id,
        unit.name,
        unit.code,
        unit.kind,
        unit.parent_id,
        unit.staffing_status,
        unit.version,
    )
