"""HTTP boundary for local synthetic platform administration."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from istari_service.auth_service import PasswordHasher
from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    ElevatedMutationActor,
)
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.schemas.admin import (
    AdminOrganisationRename,
    AdminStatusPatch,
    AdminUser,
    AdminUserCreate,
    AdminUserList,
    AdminUserPatch,
)
from istari_service.schemas.organisation import OrganisationUnitView
from istari_service.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["platform-administration"])


def _service(
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
) -> AdminService:
    return AdminService(
        SqlAlchemyAdminRepository(session),
        settings,
        cast(PasswordHasher, request.app.state.password_hasher),
    )


@router.get("/users", response_model=AdminUserList)
async def list_users(
    request: Request,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
    query: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
) -> AdminUserList:
    items, next_cursor = await _service(request, session, settings).list_user_page(
        actor,
        query,
        limit=limit,
        cursor=cursor,
    )
    return AdminUserList(
        items=items,
        next_cursor=next_cursor,
    )


@router.post(
    "/users",
    response_model=AdminUser,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: AdminUserCreate,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> AdminUser:
    return await _service(request, session, settings).create_user(actor, payload)


@router.get("/users/{user_id}", response_model=AdminUser)
async def get_user(
    user_id: UUID,
    request: Request,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> AdminUser:
    return await _service(request, session, settings).get_user(actor, user_id)


@router.patch("/users/{user_id}", response_model=AdminUser)
async def update_user(
    user_id: UUID,
    payload: AdminUserPatch,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> AdminUser:
    return await _service(request, session, settings).update_user(
        actor, user_id, payload
    )


@router.patch("/users/{user_id}/status", response_model=AdminUser)
async def update_user_status(
    user_id: UUID,
    payload: AdminStatusPatch,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> AdminUser:
    return await _service(request, session, settings).set_user_status(
        actor, user_id, payload
    )


@router.patch(
    "/organisation/units/{unit_id}",
    response_model=OrganisationUnitView,
)
async def rename_organisation_unit(
    unit_id: UUID,
    payload: AdminOrganisationRename,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> OrganisationUnitView:
    return await _service(request, session, settings).rename_unit(
        actor, unit_id, payload
    )
