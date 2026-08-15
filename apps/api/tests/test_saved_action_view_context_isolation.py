"""Customer and staff saved-action-view context isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.action_notification_models import ActionSection
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound
from mist_service.models import User, UserRole
from mist_service.repositories.actions import SqlAlchemyActionRepository
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.schemas.actions import (
    ActionColumn,
    ActionFilters,
    SavedActionViewCommand,
    SavedActionViewUpdate,
)


async def test_dual_context_saved_views_are_independently_scoped(
    api_harness: ApiHarness,
) -> None:
    command = SavedActionViewCommand(
        name="My priority work",
        filters=ActionFilters(sections=[ActionSection.NEEDS_MY_ACTION]),
        visible_columns=[ActionColumn.REFERENCE],
    )
    async with api_harness.sessions() as session, session.begin():
        user = await session.scalar(select(User).where(User.username == "admin13"))
        assert user is not None and user.customer_context_enabled
        staff = await actor_from_user_with_memberships(session, user)
        customer = Actor(
            user.id,
            user.username,
            user.display_name,
            UserRole.REQUESTER,
            "Customer",
        )
        repository = SqlAlchemyActionRepository(session)

        staff_view = await repository.create_saved_view(staff, command)
        assert [item.id for item in await repository.saved_views(staff)] == [
            staff_view.id
        ]
        assert await repository.saved_views(customer) == []

        customer_view = await repository.create_saved_view(customer, command)
        assert customer_view.id != staff_view.id
        assert [item.id for item in await repository.saved_views(customer)] == [
            customer_view.id
        ]
        assert [item.id for item in await repository.saved_views(staff)] == [
            staff_view.id
        ]

        update = SavedActionViewUpdate(
            **command.model_dump(), expected_version=staff_view.version
        )
        with pytest.raises(ObjectNotFound):
            await repository.update_saved_view(customer, staff_view.id, update)
        with pytest.raises(ObjectNotFound):
            await repository.delete_saved_view(
                customer, staff_view.id, staff_view.version
            )
        with pytest.raises(ObjectNotFound):
            await repository.delete_saved_view(
                staff, customer_view.id, customer_view.version
            )
