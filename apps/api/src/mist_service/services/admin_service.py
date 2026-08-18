from __future__ import annotations

from uuid import UUID

from anyio import to_thread

from mist_service.admin_policy import is_security_change, require_memberships
from mist_service.admin_ports import (
    AdminIdentityPolicyPort,
    AdminIdentityRecord,
    AdminMutationPort,
    AdminQueryPort,
    AdminUnitRecord,
    CreateIdentityChange,
    StatusIdentityChange,
    UpdateIdentityChange,
)
from mist_service.admin_workspace_policy import workspace_position_for
from mist_service.auth_service import PasswordHasher
from mist_service.config import Environment, Settings
from mist_service.domain import Actor
from mist_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
    InvalidAdministrationChange,
)
from mist_service.models import UserRole
from mist_service.schemas.admin import (
    AdminOrganisationRename,
    AdminStatusPatch,
    AdminUser,
    AdminUserCreate,
    AdminUserPatch,
)
from mist_service.schemas.organisation import OrganisationUnitView
from mist_service.team_models import WorkspacePosition


class AdminService:
    def __init__(
        self,
        queries: AdminQueryPort,
        identity_policy: AdminIdentityPolicyPort,
        mutations: AdminMutationPort,
        settings: Settings,
        hasher: PasswordHasher,
    ) -> None:
        self._queries = queries
        self._identity_policy = identity_policy
        self._mutations = mutations
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
        return await self._queries.list_user_views(query)

    async def list_user_page(
        self,
        actor: Actor,
        query: str | None,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[AdminUser], str | None]:
        self.authorise(actor)
        return await self._queries.page_user_views(query, limit=limit, cursor=cursor)

    async def get_user(self, actor: Actor, user_id: UUID) -> AdminUser:
        self.authorise(actor)
        return await self._queries.user_view(user_id)

    async def create_user(self, actor: Actor, payload: AdminUserCreate) -> AdminUser:
        self.authorise(actor)
        units = await self._queries.load_units(
            payload.organisation_unit_ids,
            role=payload.role,
        )
        require_memberships(payload.role, units)
        password = self._demo_password()
        password_hash = await to_thread.run_sync(self._hasher.hash, password)
        username = await self._identity_policy.next_username()
        email = payload.email or f"{username}@mist.example.test"
        await self._identity_policy.ensure_unique_email(email)
        position = workspace_position_for(payload)
        return await self._mutations.create_identity(
            CreateIdentityChange(
                actor_id=actor.id,
                username=username,
                email=email,
                display_name=payload.display_name,
                password_hash=password_hash,
                role=payload.role,
                scope=self._effective_scope(payload.role, payload.scope, units),
                customer_context_enabled=self._customer_context_enabled(payload.role),
                unit_ids=frozenset(unit.id for unit in units),
                workspace_position=position,
            )
        )

    async def update_user(
        self, actor: Actor, user_id: UUID, payload: AdminUserPatch
    ) -> AdminUser:
        self.authorise(actor)
        await self._identity_policy.lock_identity_sequence()
        user = await self._identity_policy.locked_user(
            user_id, payload.expected_version
        )
        units = await self._queries.load_units(
            payload.organisation_unit_ids,
            role=payload.role,
        )
        require_memberships(payload.role, units)
        old_ids = await self._identity_policy.membership_ids(user.id)
        next_ids = {unit.id for unit in units}
        old_position = await self._identity_policy.workspace_position(user.id)
        next_position = workspace_position_for(payload)
        next_scope = self._effective_scope(payload.role, payload.scope, units)
        next_email = payload.email or user.email
        await self._identity_policy.ensure_unique_email(
            next_email,
            excluding_user_id=user.id,
        )
        security_change = (
            is_security_change(
                current_role=user.role,
                next_role=payload.role,
                current_scope=user.scope,
                next_scope=next_scope,
                current_unit_ids=set(old_ids),
                next_unit_ids=set(next_ids),
            )
            or old_position is not next_position
        )
        if actor.id == user.id and payload.role is not UserRole.PLATFORM_ADMIN:
            raise InvalidAdministrationChange(
                "You cannot remove your own Platform Administrator role."
            )
        if user.role is UserRole.PLATFORM_ADMIN and payload.role is not user.role:
            await self._identity_policy.require_another_admin(user.id)
        if security_change:
            await self._identity_policy.reject_active_work(user.id)
        changed = self._changed_fields(
            user,
            payload,
            next_email,
            next_scope,
            old_ids,
            old_position,
            next_position,
        )
        return await self._mutations.update_identity(
            UpdateIdentityChange(
                actor_id=actor.id,
                user_id=user.id,
                expected_version=user.version,
                display_name=payload.display_name,
                email=next_email,
                role=payload.role,
                scope=next_scope,
                customer_context_enabled=self._customer_context_enabled(payload.role),
                unit_ids=frozenset(next_ids),
                old_unit_ids=frozenset(old_ids),
                workspace_position=next_position,
                security_change=security_change,
                changed_fields=tuple(changed),
            )
        )

    async def set_user_status(
        self, actor: Actor, user_id: UUID, payload: AdminStatusPatch
    ) -> AdminUser:
        self.authorise(actor)
        await self._identity_policy.lock_identity_sequence()
        user = await self._identity_policy.locked_user(
            user_id, payload.expected_version
        )
        if user.is_active == payload.is_active:
            return await self._queries.user_view(user.id)
        if actor.id == user.id and not payload.is_active:
            raise InvalidAdministrationChange("You cannot deactivate your own account.")
        if user.role is UserRole.PLATFORM_ADMIN and not payload.is_active:
            await self._identity_policy.require_another_admin(user.id)
        if not payload.is_active:
            await self._identity_policy.reject_active_work(user.id)
        team_ids = await self._identity_policy.membership_ids(user.id)
        return await self._mutations.set_identity_status(
            StatusIdentityChange(
                actor_id=actor.id,
                user_id=user.id,
                expected_version=user.version,
                is_active=payload.is_active,
                unit_ids=frozenset(team_ids),
            )
        )

    async def rename_unit(
        self,
        actor: Actor,
        unit_id: UUID,
        payload: AdminOrganisationRename,
    ) -> OrganisationUnitView:
        self.authorise(actor)
        unit = await self._mutations.locked_unit(unit_id, payload.expected_version)
        if unit.name == payload.name:
            return OrganisationUnitView.model_validate(unit)
        if self._settings.configuration_admin_enabled:
            raise InvalidAdministrationChange(
                "Rename configured units through Configuration administration."
            )
        await self._mutations.ensure_unique_sibling_name(
            unit.id, unit.version, payload.name
        )
        old_name = unit.name
        return await self._mutations.rename_unit(
            unit.id,
            unit.version,
            old_name=old_name,
            new_name=payload.name,
            actor_id=actor.id,
        )

    @staticmethod
    def _effective_scope(
        role: UserRole, scope: str, units: list[AdminUnitRecord]
    ) -> str:
        if role.value.startswith("DELIVERY_") or role is UserRole.QUALITY_RELEASE:
            return units[0].name
        return scope

    def _demo_password(self) -> str:
        password = self._settings.demo_user_password
        if password is None or not password.get_secret_value():
            raise AdministrationUnavailable()
        return password.get_secret_value()

    @staticmethod
    def _customer_context_enabled(role: UserRole) -> bool:
        return role not in {UserRole.REQUESTER, UserRole.PLATFORM_ADMIN}

    @staticmethod
    def _changed_fields(
        user: AdminIdentityRecord,
        payload: AdminUserPatch,
        next_email: str,
        next_scope: str,
        old_ids: set[UUID],
        old_position: WorkspacePosition | None,
        next_position: WorkspacePosition | None,
    ) -> list[str]:
        fields: list[str] = []
        if user.display_name != payload.display_name:
            fields.append("displayName")
        if user.email != next_email:
            fields.append("email")
        if user.role is not payload.role:
            fields.append("role")
        if user.scope != next_scope:
            fields.append("scope")
        if old_ids != set(payload.organisation_unit_ids):
            fields.append("memberships")
        if old_position is not next_position:
            fields.append("workspacePosition")
        return fields
