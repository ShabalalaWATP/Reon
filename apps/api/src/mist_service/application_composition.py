"""HTTP middleware, error and route composition for the API application."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mist_service.audit import AUDIT_KEY_INFO
from mist_service.compliance_models import SecurityOutcome
from mist_service.config import Settings
from mist_service.errors import InvalidAction, ObjectNotFound, ServiceError
from mist_service.request_security import RequestBodyLimitMiddleware
from mist_service.response_security import SecurityHeadersMiddleware
from mist_service.routers import (
    actions,
    admin,
    auth,
    board,
    calendar,
    capabilities,
    configuration,
    drafts,
    health,
    organisation,
    planning,
    platform_security,
    products,
    profiles,
    request_conversations,
    request_coordination,
    requests,
    statistics,
    statistics_evolution,
    task_hasteners,
    team_workspaces,
    work_items,
    workspace_collaboration,
)
from mist_service.security_events import SecurityEventCommand, SecurityEventRecorder
from mist_service.telemetry import OperationalTelemetryMiddleware


async def handle_service_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Return the stable service-error envelope and audit denied mutations."""
    service_error = cast(ServiceError, error)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and isinstance(
        service_error, (ObjectNotFound, InvalidAction)
    ):
        actor = getattr(request.state, "authenticated_actor", None)
        if actor is not None:
            factory = cast(
                async_sessionmaker[AsyncSession],
                request.app.state.session_factory,
            )
            route = request.scope.get("route")
            await SecurityEventRecorder(
                factory,
                pseudonym_key=cast(bytes, factory.kw["info"][AUDIT_KEY_INFO]),
            ).record_once(
                SecurityEventCommand(
                    event_type="AUTHORIZATION_DENIAL",
                    outcome=SecurityOutcome.DENIED,
                    reason_code=service_error.code,
                    actor_user_id=actor.id,
                    source=request.client.host if request.client else None,
                    correlation_id=getattr(request.state, "correlation_id", None),
                    request_method=request.method,
                    route_template=getattr(route, "path", None),
                )
            )
    return JSONResponse(
        status_code=service_error.status_code,
        headers=getattr(service_error, "response_headers", None),
        content={
            "detail": {
                "code": service_error.code,
                "message": service_error.message,
            }
        },
    )


async def handle_validation_error(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Return bounded validation details without echoing submitted values."""
    validation_error = cast(RequestValidationError, error)
    safe_errors = [
        {
            "loc": [
                part if isinstance(part, int) else str(part)[:80]
                for part in item.get("loc", ())
            ],
            "msg": str(item.get("msg", "Invalid value."))[:200],
            "type": str(item.get("type", "validation_error"))[:80],
        }
        for item in validation_error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


def configure_middleware(application: FastAPI, settings: Settings) -> None:
    """Install the API middleware stack in its established order."""
    application.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.max_request_body_bytes,
        product_upload_max_bytes=settings.product_max_file_bytes,
    )
    application.add_middleware(OperationalTelemetryMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=sorted(settings.allowed_hosts),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(settings.trusted_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "X-Correlation-ID",
            "X-Upload-Token",
        ],
        expose_headers=["X-Correlation-ID"],
    )


def configure_exception_handlers(application: FastAPI) -> None:
    """Register the stable public error handlers."""
    application.add_exception_handler(ServiceError, handle_service_error)
    application.add_exception_handler(
        RequestValidationError,
        handle_validation_error,
    )


def include_application_routers(application: FastAPI, settings: Settings) -> None:
    """Publish the core routes and the configured optional capabilities."""
    application.include_router(health.router)
    for router in (
        platform_security.router,
        auth.router,
        capabilities.router,
        admin.router,
        organisation.router,
        profiles.router,
        requests.router,
        request_coordination.router,
        request_conversations.router,
        statistics.router,
        team_workspaces.router,
        task_hasteners.router,
        workspace_collaboration.router,
        board.router,
        calendar.router,
        drafts.router,
        work_items.router,
    ):
        application.include_router(router, prefix="/api/v1")

    if settings.action_workspace_enabled:
        application.include_router(actions.action_router, prefix="/api/v1")
    if settings.notifications_enabled:
        application.include_router(actions.notification_router, prefix="/api/v1")
    if settings.managed_products_enabled:
        application.include_router(products.router, prefix="/api/v1")
        application.include_router(products.release_router, prefix="/api/v1")
    if settings.configuration_admin_enabled:
        application.include_router(configuration.router, prefix="/api/v1")
    if settings.planning_evolution_enabled:
        application.include_router(
            planning.router,
            prefix="/api/v1/team-workspaces",
        )
    if settings.statistics_evolution_enabled:
        application.include_router(
            statistics_evolution.router,
            prefix="/api/v1/statistics",
        )


def compose_http_application(application: FastAPI, settings: Settings) -> None:
    """Apply all HTTP-facing composition to an initialised application."""
    configure_middleware(application, settings)
    configure_exception_handlers(application)
    include_application_routers(application, settings)
