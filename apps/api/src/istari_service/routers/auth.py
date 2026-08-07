"""Authentication HTTP routes."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Response, status

from istari_service.dependencies import (
    AppSettings,
    AuthDependency,
    CurrentSession,
    MutationSession,
)
from istari_service.schemas.auth import (
    CurrentUser,
    ElevationResponse,
    LoginRequest,
    PasswordConfirmation,
    SessionResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _session_response(
    session: CurrentSession,
    csrf_token: str,
) -> SessionResponse:
    return SessionResponse(
        user=CurrentUser(
            id=session.actor.id,
            username=session.actor.username,
            display_name=session.actor.display_name,
            role=session.actor.role,
            scope=session.actor.scope,
        ),
        csrf_token=csrf_token,
        expires_at=session.expires_at,
        elevated_until=session.elevated_until,
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    command: LoginRequest,
    response: Response,
    service: AuthDependency,
    settings: AppSettings,
) -> SessionResponse:
    result = await service.login(command.username, command.password)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=cast(
            Literal["lax", "strict", "none"],
            settings.session_cookie_samesite,
        ),
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return _session_response(result.session, result.csrf_token)


@router.get("/me", response_model=SessionResponse)
async def me(
    session: CurrentSession,
    service: AuthDependency,
) -> SessionResponse:
    csrf_token = await service.refresh_csrf(session)
    return _session_response(session, csrf_token)


@router.post("/elevate", response_model=ElevationResponse)
async def elevate(
    command: PasswordConfirmation,
    session: MutationSession,
    service: AuthDependency,
) -> ElevationResponse:
    return ElevationResponse(
        elevated_until=await service.elevate(session, command.password)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: MutationSession,
    service: AuthDependency,
    settings: AppSettings,
) -> Response:
    await service.logout(session)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
