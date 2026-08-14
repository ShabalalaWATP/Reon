"""Authentication HTTP routes."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status

from istari_service.admin_composition import account_request_service
from istari_service.auth_service import csrf_token_for_session
from istari_service.dependencies import (
    AppSettings,
    AuthDependency,
    CurrentSession,
    DatabaseSession,
    IdentityContextDependency,
    LoginPseudonymKey,
    MutationSession,
)
from istari_service.login_rate_limiter import login_source_key
from istari_service.platform_security_composition import platform_security_service
from istari_service.schemas.account_requests import (
    AccountRequestAccepted,
    AccountRequestCreate,
)
from istari_service.schemas.auth import (
    CurrentUser,
    ElevationResponse,
    LoginRequest,
    PasswordAssistanceAccepted,
    PasswordAssistanceRequest,
    PasswordConfirmation,
    SessionResponse,
    SwitchContextRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/account-requests",
    response_model=AccountRequestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_account(
    command: AccountRequestCreate,
    session: DatabaseSession,
    settings: AppSettings,
) -> AccountRequestAccepted:
    service = account_request_service(session, settings)
    await service.submit(command)
    return AccountRequestAccepted()


@router.post(
    "/password-assistance",
    response_model=PasswordAssistanceAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_assistance(
    command: PasswordAssistanceRequest,
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
    pseudonym_key: LoginPseudonymKey,
) -> PasswordAssistanceAccepted:
    service = platform_security_service(
        session,
        pseudonym_key=pseudonym_key,
        pseudonym_key_id=settings.security_pseudonym_key_id,
    )
    await service.request_password_assistance(
        command.email,
        source_key=login_source_key(
            request,
            settings.trusted_proxy_networks,
            pseudonym_key=pseudonym_key,
        ),
    )
    return PasswordAssistanceAccepted()


def _session_response(
    session: CurrentSession,
    csrf_token: str,
    idle_seconds: int,
) -> SessionResponse:
    return SessionResponse(
        user=CurrentUser(
            id=session.actor.id,
            username=session.actor.username,
            display_name=session.actor.display_name,
            role=session.actor.role,
            scope=session.actor.scope,
            organisation_unit_ids=sorted(session.actor.organisation_unit_ids, key=str),
        ),
        csrf_token=csrf_token,
        expires_at=session.expires_at,
        idle_expires_at=(session.last_seen_at or session.expires_at)
        + timedelta(seconds=idle_seconds),
        idle_timeout_seconds=idle_seconds,
        elevated_until=session.elevated_until,
        active_context=session.active_context,
        available_contexts=list(session.available_contexts),
        context_version=session.context_version,
    )


def _set_session_cookie(
    response: Response,
    settings: AppSettings,
    session_token: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=cast(
            Literal["lax", "strict", "none"],
            settings.session_cookie_samesite,
        ),
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def _current_session_response(
    request: Request,
    session: CurrentSession,
    settings: AppSettings,
) -> SessionResponse:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        raise RuntimeError("authenticated session cookie is unavailable")
    return _session_response(
        session,
        csrf_token_for_session(session_token),
        settings.session_idle_seconds,
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    command: LoginRequest,
    request: Request,
    response: Response,
    service: AuthDependency,
    settings: AppSettings,
    pseudonym_key: LoginPseudonymKey,
) -> SessionResponse:
    result = await service.login(
        command.username,
        command.password,
        source_key=login_source_key(
            request,
            settings.trusted_proxy_networks,
            pseudonym_key=pseudonym_key,
        ),
    )
    _set_session_cookie(response, settings, result.session_token)
    return _session_response(
        result.session,
        result.csrf_token,
        settings.session_idle_seconds,
    )


@router.get("/me", response_model=SessionResponse)
async def me(
    request: Request,
    session: CurrentSession,
    settings: AppSettings,
) -> SessionResponse:
    return _current_session_response(request, session, settings)


@router.post("/activity", status_code=status.HTTP_204_NO_CONTENT)
async def activity(session: MutationSession, service: AuthDependency) -> Response:
    await service.record_activity(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/switch-context", response_model=SessionResponse)
async def switch_context(
    command: SwitchContextRequest,
    response: Response,
    session: MutationSession,
    service: IdentityContextDependency,
    settings: AppSettings,
) -> SessionResponse:
    result = await service.switch(session, command.context)
    _set_session_cookie(response, settings, result.session_token)
    return _session_response(
        result.session,
        result.csrf_token,
        settings.session_idle_seconds,
    )


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
