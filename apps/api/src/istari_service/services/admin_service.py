"""Bounded administrator use cases."""

from __future__ import annotations

from uuid import UUID

from anyio import to_thread

from istari_service.admin_audit import append_admin_event
from istari_service.admin_policy import is_security_change, membership_error
from istari_service.auth_service import PasswordHasher
from istari_service.config import Environment, Settings
from istari_service.domain import Actor
from istari_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
    InvalidAdministrationChange,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.schemas.admin import (
    AdminOrganisationRename,
    AdminStatusPatch,
    AdminUser,
    AdminUserCreate,
    AdminUserPatch,
)
from istari_service.schemas.organisation import OrganisationUnitView
from istari_service.team_membership_admin import align_admin_team_membership


class AdminService:
    def __init__(
        self,
        repository: SqlAlchemyAdminRepository,
        settings: Settings,
        hasher: PasswordHasher,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._hasher = hasher

    def authorise(self, actor: Actor) -> None:
        if (
            self._settings.environment not in {Environment.LOCAL, Environment.TEST}
            or not self._settings.allow_demo_users
        ):
            raise AdministrationUnavailable()
        if actor.role is not UserRole.PLATFORM_ADMIN:
            raise AdministrationAccessDenied()

    async def list_users(self, actor: Actor, query: str | None) -> list[AdminUser]:
        self.authorise(actor)
        return await self._repository.views(await self._repository.list_users(query))

    async def get_user(self, actor: Actor, user_id: UUID) -> AdminUser:
        self.authorise(actor)
        return (
            await self._repository.views([await self._repository.get_user(user_id)])
        )[0]

    async def create_user(self, actor: Actor, payload: AdminUserCreate) -> AdminUser:
        self.authorise(actor)
        units = await self._repository.load_units(payload.organisation_unit_ids)
        self._validate_memberships(payload.role, units)
        password = self._demo_password()
        password_hash = await to_thread.run_sync(self._hasher.hash, password)
        user = User(
            username=await self._repository.next_username(),
            display_name=payload.display_name,
            password_hash=password_hash,
            role=payload.role,
            scope=self._effective_scope(payload.role, payload.scope, units),
            is_active=True,
        )
        self._repository.session.add(user)
        await self._repository.session.flush()
        await align_admin_team_membership(
            self._repository.session,
            user=user,
            next_team_id=units[0].id
            if units
            and payload.role
            in {
                UserRole.DELIVERY_TEAM_LEAD,
                UserRole.DELIVERY_SPECIALIST,
            }
            else None,
            actor_id=actor.id,
        )
        await self._repository.replace_memberships(user.id, units)
        await self._repository.recalculate_teams({unit.id for unit in units})
        await self._audit(
            actor,
            "USER_CREATED",
            "USER",
            user.id,
            ["displayName", "role", "scope", "memberships"],
            "Synthetic account created.",
        )
        await self._repository.session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def update_user(
        self, actor: Actor, user_id: UUID, payload: AdminUserPatch
    ) -> AdminUser:
        self.authorise(actor)
        await self._repository.lock_identity_sequence()
        user = await self._repository.locked_user(user_id, payload.expected_version)
        units = await self._repository.load_units(payload.organisation_unit_ids)
        self._validate_memberships(payload.role, units)
        old_ids = await self._repository.membership_ids(user.id)
        next_ids = {unit.id for unit in units}
        next_scope = self._effective_scope(payload.role, payload.scope, units)
        security_change = is_security_change(
            current_role=user.role,
            next_role=payload.role,
            current_scope=user.scope,
            next_scope=next_scope,
            current_unit_ids=set(old_ids),
            next_unit_ids=set(next_ids),
        )
        if actor.id == user.id and payload.role is not UserRole.PLATFORM_ADMIN:
            raise InvalidAdministrationChange(
                "You cannot remove your own Platform Administrator role."
            )
        if user.role is UserRole.PLATFORM_ADMIN and payload.role is not user.role:
            await self._repository.require_another_admin(user.id)
        if security_change:
            await self._repository.reject_active_work(user.id)
        changed = self._changed_fields(user, payload, next_scope, old_ids)
        if old_ids != next_ids or user.role is not payload.role:
            await align_admin_team_membership(
                self._repository.session,
                user=user,
                next_team_id=units[0].id
                if units
                and payload.role
                in {
                    UserRole.DELIVERY_TEAM_LEAD,
                    UserRole.DELIVERY_SPECIALIST,
                }
                else None,
                actor_id=actor.id,
            )
        user.display_name = payload.display_name
        user.role = payload.role
        user.scope = next_scope
        user.version += 1
        if security_change:
            user.credential_version += 1
            await self._repository.revoke_sessions(user.id)
        await self._repository.replace_memberships(user.id, units)
        await self._repository.recalculate_teams(old_ids | next_ids)
        await self._audit(
            actor,
            "USER_UPDATED",
            "USER",
            user.id,
            changed,
            "Synthetic account metadata updated.",
        )
        await self._repository.session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def set_user_status(
        self, actor: Actor, user_id: UUID, payload: AdminStatusPatch
    ) -> AdminUser:
        self.authorise(actor)
        await self._repository.lock_identity_sequence()
        user = await self._repository.locked_user(user_id, payload.expected_version)
        if user.is_active == payload.is_active:
            return (await self._repository.views([user]))[0]
        if actor.id == user.id and not payload.is_active:
            raise InvalidAdministrationChange("You cannot deactivate your own account.")
        if user.role is UserRole.PLATFORM_ADMIN and not payload.is_active:
            await self._repository.require_another_admin(user.id)
        if not payload.is_active:
            await self._repository.reject_active_work(user.id)
        team_ids = await self._repository.membership_ids(user.id)
        user.is_active = payload.is_active
        user.version += 1
        user.credential_version += 1
        user.failed_login_count = 0
        user.locked_until = None
        await self._repository.revoke_sessions(user.id)
        await self._repository.session.flush()
        await self._repository.recalculate_teams(team_ids)
        await self._audit(
            actor,
            "USER_ACTIVATED" if payload.is_active else "USER_DEACTIVATED",
            "USER",
            user.id,
            ["isActive"],
            "Synthetic account access status updated.",
        )
        await self._repository.session.refresh(user)
        return (await self._repository.views([user]))[0]

    async def rename_unit(
        self,
        actor: Actor,
        unit_id: UUID,
        payload: AdminOrganisationRename,
    ) -> OrganisationUnitView:
        self.authorise(actor)
        unit = await self._repository.locked_unit(unit_id, payload.expected_version)
        if unit.name == payload.name:
            return OrganisationUnitView.model_validate(unit)
        await self._repository.ensure_unique_sibling_name(unit, payload.name)
        old_name = unit.name
        unit.name = payload.name
        unit.version += 1
        await self._repository.cascade_unit_rename(
            unit, old_name=old_name, new_name=payload.name
        )
        await self._audit(
            actor,
            "ORGANISATION_UNIT_RENAMED",
            "ORGANISATION_UNIT",
            unit.id,
            ["name"],
            "Organisation display name updated.",
        )
        await self._repository.session.refresh(unit)
        return OrganisationUnitView.model_validate(unit)

    @staticmethod
    def _validate_memberships(role: UserRole, units: list[OrganisationUnit]) -> None:
        message = membership_error(role, [unit.kind for unit in units])
        if message:
            raise InvalidAdministrationChange(message)

    @staticmethod
    def _effective_scope(
        role: UserRole, scope: str, units: list[OrganisationUnit]
    ) -> str:
        if role in {UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST}:
            return units[0].name
        return scope

    def _demo_password(self) -> str:
        password = self._settings.demo_user_password
        if password is None or not password.get_secret_value():
            raise AdministrationUnavailable()
        return password.get_secret_value()

    @staticmethod
    def _changed_fields(
        user: User,
        payload: AdminUserPatch,
        next_scope: str,
        old_ids: set[UUID],
    ) -> list[str]:
        fields: list[str] = []
        if user.display_name != payload.display_name:
            fields.append("displayName")
        if user.role is not payload.role:
            fields.append("role")
        if user.scope != next_scope:
            fields.append("scope")
        if old_ids != set(payload.organisation_unit_ids):
            fields.append("memberships")
        return fields

    async def _audit(
        self,
        actor: Actor,
        action: str,
        target_type: str,
        target_id: UUID,
        changed_fields: list[str],
        summary: str,
    ) -> None:
        await append_admin_event(
            self._repository.session,
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            changed_fields=changed_fields,
            summary=summary,
        )
