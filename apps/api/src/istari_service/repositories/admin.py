"""SQLAlchemy adapter for bounded platform administration."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.admin_models import AdminIdentitySequence
from istari_service.errors import (
    InvalidAdministrationChange,
    ObjectNotFound,
    StaleVersion,
)
from istari_service.models import (
    ServiceRequest,
    Session,
    User,
    UserRole,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
    StaffingStatus,
    UserOrganisationMembership,
)
from istari_service.repositories.admin_reads import AdminReadRepositoryMixin
from istari_service.team_models import TeamMembership, WorkspacePosition

ADMIN_USERNAME = re.compile(r"admin([1-9][0-9]*)")
ACTIVE_WORK_STATUSES = {
    WorkflowTaskStatus.CLAIM_PENDING,
    WorkflowTaskStatus.CLAIMED,
    WorkflowTaskStatus.COMPLETION_PENDING,
    WorkflowTaskStatus.ERROR,
}


class SqlAlchemyAdminRepository(AdminReadRepositoryMixin):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def locked_user(self, user_id: UUID, version: int) -> User:
        user = await self.get_user(user_id, lock=True)
        if user.version != version:
            raise StaleVersion()
        return user

    async def load_units(self, unit_ids: list[UUID]) -> list[OrganisationUnit]:
        if not unit_ids:
            return []
        units = list(
            await self.session.scalars(
                select(OrganisationUnit).where(
                    OrganisationUnit.id.in_(unit_ids),
                    OrganisationUnit.is_configured.is_(True),
                )
            )
        )
        by_id = {unit.id: unit for unit in units}
        if len(by_id) != len(unit_ids):
            raise InvalidAdministrationChange("Select configured organisation units.")
        return [by_id[unit_id] for unit_id in unit_ids]

    async def locked_unit(self, unit_id: UUID, version: int) -> OrganisationUnit:
        unit = await self.session.scalar(
            select(OrganisationUnit)
            .where(
                OrganisationUnit.id == unit_id,
                OrganisationUnit.is_configured.is_(True),
            )
            .with_for_update()
        )
        if unit is None:
            raise ObjectNotFound()
        if unit.version != version:
            raise StaleVersion()
        return unit

    async def ensure_unique_sibling_name(
        self, unit: OrganisationUnit, name: str
    ) -> None:
        duplicate = await self.session.scalar(
            select(OrganisationUnit.id).where(
                OrganisationUnit.parent_id == unit.parent_id,
                OrganisationUnit.id != unit.id,
                OrganisationUnit.is_configured.is_(True),
                func.lower(OrganisationUnit.name) == name.lower(),
            )
        )
        if duplicate is not None:
            raise InvalidAdministrationChange(
                "Organisation names must be unique amongst siblings."
            )

    async def ensure_unique_email(
        self, email: str, *, excluding_user_id: UUID | None = None
    ) -> None:
        statement = select(User.id).where(User.email == email)
        if excluding_user_id is not None:
            statement = statement.where(User.id != excluding_user_id)
        if await self.session.scalar(statement) is not None:
            raise InvalidAdministrationChange(
                "That email address is already assigned to another account."
            )

    async def next_username(self) -> str:
        sequence = await self.lock_identity_sequence()
        usernames = await self.session.scalars(select(User.username))
        numbers = [
            int(match.group(1))
            for username in usernames
            if (match := ADMIN_USERNAME.fullmatch(username))
        ]
        value = max(sequence.next_value, max(numbers, default=0) + 1)
        sequence.next_value = value + 1
        return f"admin{value}"

    async def lock_identity_sequence(self) -> AdminIdentitySequence:
        sequence = await self.session.scalar(
            select(AdminIdentitySequence)
            .where(AdminIdentitySequence.id == 1)
            .with_for_update()
        )
        if sequence is None:
            raise RuntimeError("the administrator identity sequence is unavailable")
        return sequence

    async def membership_ids(self, user_id: UUID) -> set[UUID]:
        return set(
            await self.session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == user_id
                )
            )
        )

    async def workspace_position(self, user_id: UUID) -> WorkspacePosition | None:
        position = await self.session.scalar(
            select(TeamMembership.workspace_position)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.effective_until.is_(None),
            )
            .limit(1)
        )
        return position

    async def replace_memberships(
        self, user_id: UUID, units: list[OrganisationUnit]
    ) -> None:
        await self.session.execute(
            delete(UserOrganisationMembership).where(
                UserOrganisationMembership.user_id == user_id
            )
        )
        self.session.add_all(
            UserOrganisationMembership(user_id=user_id, unit_id=unit.id)
            for unit in units
        )
        await self.session.flush()

    async def recalculate_teams(self, unit_ids: set[UUID]) -> None:
        if not unit_ids:
            return
        teams = list(
            await self.session.scalars(
                select(OrganisationUnit)
                .where(
                    OrganisationUnit.id.in_(unit_ids),
                    OrganisationUnit.kind == OrganisationKind.TEAM,
                )
                .with_for_update()
            )
        )
        for team in teams:
            roles = set(
                await self.session.scalars(
                    select(User.role)
                    .join(
                        UserOrganisationMembership,
                        UserOrganisationMembership.user_id == User.id,
                    )
                    .where(
                        UserOrganisationMembership.unit_id == team.id,
                        User.is_active.is_(True),
                        User.role.in_(
                            [
                                UserRole.DELIVERY_TEAM_LEAD,
                                UserRole.DELIVERY_SPECIALIST,
                            ]
                        ),
                    )
                )
            )
            staffed = {
                UserRole.DELIVERY_TEAM_LEAD,
                UserRole.DELIVERY_SPECIALIST,
            }.issubset(roles)
            team.staffing_status = (
                StaffingStatus.STAFFED if staffed else StaffingStatus.UNSTAFFED
            )

    async def reject_active_work(self, user_id: UUID) -> None:
        work_id = await self.session.scalar(
            select(WorkflowTask.id).where(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status.in_(ACTIVE_WORK_STATUSES),
            )
        )
        if work_id is not None:
            raise InvalidAdministrationChange(
                "Complete or reassign this user's active work first."
            )

    async def require_another_admin(self, user_id: UUID) -> None:
        active_admin_ids = list(
            await self.session.scalars(
                select(User.id)
                .where(
                    User.role == UserRole.PLATFORM_ADMIN,
                    User.is_active.is_(True),
                )
                .order_by(User.id)
                .with_for_update()
            )
        )
        if not any(admin_id != user_id for admin_id in active_admin_ids):
            raise InvalidAdministrationChange(
                "At least one active Platform Administrator must remain."
            )

    async def revoke_sessions(self, user_id: UUID) -> None:
        await self.session.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def cascade_unit_rename(
        self,
        unit: OrganisationUnit,
        *,
        old_name: str,
        new_name: str,
    ) -> None:
        member_ids: set[UUID] = set()
        if unit.kind is OrganisationKind.TEAM:
            member_ids = set(
                await self.session.scalars(
                    select(User.id)
                    .join(
                        UserOrganisationMembership,
                        UserOrganisationMembership.user_id == User.id,
                    )
                    .where(
                        UserOrganisationMembership.unit_id == unit.id,
                        User.role.in_(
                            [
                                UserRole.DELIVERY_TEAM_LEAD,
                                UserRole.DELIVERY_SPECIALIST,
                            ]
                        ),
                    )
                )
            )
        if member_ids:
            await self.session.execute(
                update(User)
                .where(User.id.in_(member_ids))
                .values(
                    scope=new_name,
                    version=User.version + 1,
                    credential_version=User.credential_version + 1,
                )
            )
            await self.session.execute(
                update(Session)
                .where(Session.user_id.in_(member_ids), Session.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
        if unit.kind is OrganisationKind.TEAM:
            request_ids = select(RequestRouteSelection.request_id).where(
                RequestRouteSelection.unit_id == unit.id
            )
            await self.session.execute(
                update(ServiceRequest)
                .where(
                    ServiceRequest.id.in_(request_ids),
                    ServiceRequest.assigned_delivery_team == old_name,
                )
                .values(assigned_delivery_team=new_name)
            )
