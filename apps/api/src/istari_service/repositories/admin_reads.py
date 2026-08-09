"""Bounded administrator identity reads and response projection."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import ObjectNotFound
from istari_service.models import User
from istari_service.organisation_models import (
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.schemas.admin import AdminMembership, AdminUser


class AdminReadRepositoryMixin:
    session: AsyncSession

    async def list_users(self, query: str | None) -> list[User]:
        users, _cursor = await self.page_users(query, limit=100, cursor=None)
        return users

    async def page_users(
        self,
        query: str | None,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[User], str | None]:
        statement = select(User)
        normalised = (query or "").strip().lower()
        if normalised:
            statement = statement.where(
                or_(
                    func.lower(User.username).contains(normalised, autoescape=True),
                    func.lower(User.display_name).contains(normalised, autoescape=True),
                )
            )
        if cursor is not None:
            changed_at, user_id = decode_cursor(
                cursor, message="The user filters are invalid."
            )
            statement = statement.where(
                or_(
                    User.updated_at < changed_at,
                    and_(User.updated_at == changed_at, User.id < user_id),
                )
            )
        users = list(
            await self.session.scalars(
                statement.order_by(User.updated_at.desc(), User.id.desc()).limit(
                    limit + 1
                )
            )
        )
        page = users[:limit]
        next_cursor = (
            encode_cursor(page[-1].updated_at, page[-1].id)
            if len(users) > limit and page
            else None
        )
        return page, next_cursor

    async def get_user(self, user_id: UUID, *, lock: bool = False) -> User:
        query = select(User).where(User.id == user_id)
        if lock:
            query = query.with_for_update()
        user = await self.session.scalar(query)
        if user is None:
            raise ObjectNotFound()
        return user

    async def views(self, users: list[User]) -> list[AdminUser]:
        if not users:
            return []
        rows = (
            await self.session.execute(
                select(
                    UserOrganisationMembership.user_id,
                    OrganisationUnit.id,
                    OrganisationUnit.name,
                    OrganisationUnit.kind,
                )
                .join(
                    OrganisationUnit,
                    OrganisationUnit.id == UserOrganisationMembership.unit_id,
                )
                .where(UserOrganisationMembership.user_id.in_({u.id for u in users}))
                .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            )
        ).all()
        memberships: dict[UUID, list[AdminMembership]] = {u.id: [] for u in users}
        for user_id, unit_id, name, kind in rows:
            memberships[user_id].append(
                AdminMembership(
                    organisation_unit_id=unit_id,
                    organisation_unit_name=name,
                    organisation_unit_kind=kind,
                )
            )
        return [
            AdminUser(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=user.role,
                scope=user.scope,
                is_active=user.is_active,
                version=user.version,
                created_at=user.created_at,
                updated_at=user.updated_at,
                memberships=memberships[user.id],
            )
            for user in users
        ]
