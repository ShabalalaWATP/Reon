"""Authenticated personal action workspace and notification centre routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from istari_service.action_notification_composition import (
    action_service,
    notification_service,
)
from istari_service.action_notification_models import (
    ActionSection,
    NotificationEventGroup,
)
from istari_service.dependencies import (
    CurrentActor,
    DatabaseSession,
    MutationActor,
    StaffActor,
    StaffMutationActor,
)
from istari_service.schemas.actions import (
    ActionFilters,
    ActionWorkspaceResult,
    NotificationCountResult,
    NotificationFilterState,
    NotificationListResult,
    NotificationPreferenceResult,
    NotificationPreferencesResult,
    NotificationPreferenceUpdate,
    NotificationStateCommand,
    NotificationStateResult,
    SavedActionViewCommand,
    SavedActionViewResult,
    SavedActionViewUpdate,
)

action_router = APIRouter(prefix="/me", tags=["personal-workspace"])
notification_router = APIRouter(prefix="/me", tags=["notifications"])


@action_router.get("/actions", response_model=ActionWorkspaceResult)
async def get_actions(
    actor: StaffActor,
    session: DatabaseSession,
    sections: Annotated[list[ActionSection] | None, Query()] = None,
    action_types: Annotated[
        list[str] | None, Query(alias="actionTypes", max_length=80)
    ] = None,
    due_before: Annotated[date | None, Query(alias="dueBefore")] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ActionWorkspaceResult:
    return await action_service(session).workspace(
        actor,
        ActionFilters(
            sections=sections or [],
            action_types=action_types or [],
            due_before=due_before,
        ),
        limit=limit,
        cursor=cursor,
    )


@action_router.post("/actions/saved-views", response_model=SavedActionViewResult)
async def create_action_view(
    command: SavedActionViewCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> SavedActionViewResult:
    return await action_service(session).create_saved_view(actor, command)


@action_router.patch(
    "/actions/saved-views/{view_id}", response_model=SavedActionViewResult
)
async def update_action_view(
    view_id: UUID,
    command: SavedActionViewUpdate,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> SavedActionViewResult:
    return await action_service(session).update_saved_view(actor, view_id, command)


@action_router.delete(
    "/actions/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_action_view(
    view_id: UUID,
    actor: StaffMutationActor,
    session: DatabaseSession,
    expected_version: Annotated[int, Query(alias="expectedVersion", ge=1)],
) -> Response:
    await action_service(session).delete_saved_view(actor, view_id, expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@notification_router.get("/notifications", response_model=NotificationListResult)
async def get_notifications(
    actor: CurrentActor,
    session: DatabaseSession,
    states: Annotated[list[NotificationFilterState] | None, Query()] = None,
    event_types: Annotated[
        list[str] | None, Query(alias="eventTypes", max_length=80)
    ] = None,
    from_date: Annotated[datetime | None, Query(alias="from")] = None,
    to_date: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationListResult:
    return await notification_service(session).list_notifications(
        actor,
        states=states or [],
        event_types=event_types or [],
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        cursor=cursor,
    )


@notification_router.get("/notifications/count", response_model=NotificationCountResult)
async def get_notification_count(
    actor: CurrentActor, session: DatabaseSession
) -> NotificationCountResult:
    return await notification_service(session).count(actor)


@notification_router.post(
    "/notifications/state", response_model=NotificationStateResult
)
async def update_notification_state(
    command: NotificationStateCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> NotificationStateResult:
    return await notification_service(session).mutate_state(actor, command)


@notification_router.get(
    "/notifications/preferences", response_model=NotificationPreferencesResult
)
async def get_notification_preferences(
    actor: CurrentActor, session: DatabaseSession
) -> NotificationPreferencesResult:
    return await notification_service(session).preferences(actor)


@notification_router.patch(
    "/notifications/preferences/{event_group}",
    response_model=NotificationPreferenceResult,
)
async def update_notification_preference(
    event_group: NotificationEventGroup,
    command: NotificationPreferenceUpdate,
    actor: MutationActor,
    session: DatabaseSession,
) -> NotificationPreferenceResult:
    return await notification_service(session).update_preference(
        actor, event_group, command
    )


# Compatibility aggregate for isolated router composition.
router = APIRouter()
router.include_router(action_router)
router.include_router(notification_router)
