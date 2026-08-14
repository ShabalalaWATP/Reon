"""FastAPI application composition for the service-request MVP."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from istari_service.admin_audit import initialise_admin_audit_anchor
from istari_service.admin_sequence import initialise_admin_identity_sequence
from istari_service.audit import AUDIT_KEY_INFO
from istari_service.auth_service import DUMMY_HASH_INPUT, PasswordHasher
from istari_service.compliance_models import SecurityOutcome
from istari_service.config import Environment, Settings, get_settings
from istari_service.configuration_seed import (
    restore_active_configuration_projection,
    seed_baseline_configuration,
)
from istari_service.database import SessionFactory
from istari_service.demo_seed import seed_demo_users
from istari_service.errors import InvalidAction, ObjectNotFound, ServiceError
from istari_service.organisation_seed import seed_organisation_units
from istari_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from istari_service.product_runtime import ProductRuntime, clamav_product_runtime
from istari_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from istari_service.repositories.platform_security import (
    initialise_platform_classification,
)
from istari_service.request_security import RequestBodyLimitMiddleware
from istari_service.response_security import SecurityHeadersMiddleware
from istari_service.routers import (
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
from istari_service.security_events import SecurityEventCommand, SecurityEventRecorder
from istari_service.telemetry import OperationalTelemetryMiddleware
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow_runtime import (
    WorkflowRuntimeFactory,
    managed_camunda_engine,
)


def _product_runtime(settings: Settings) -> ProductRuntime:
    if settings.environment is Environment.PROD:
        raise ValueError(
            "production managed products require an injected approved private "
            "storage and scanner runtime"
        )
    storage = PrivateFilesystemObjectStorage(settings.product_storage_path)
    link_policy = AllowedHttpsLinkPolicy(settings.product_allowed_external_domains)
    upload_ttl = timedelta(seconds=settings.product_upload_ttl_seconds)
    if settings.environment is Environment.TEST:
        return ProductRuntime(
            storage=storage,
            scanner=SafeDocumentScanner(),
            link_policy=link_policy,
            upload_ttl=upload_ttl,
            maximum_file_bytes=settings.product_max_file_bytes,
            maximum_package_bytes=settings.product_max_package_bytes,
        )
    return clamav_product_runtime(
        storage,
        link_policy,
        clamav_host=settings.product_clamav_host,
        clamav_port=settings.product_clamav_port,
        clamav_timeout_seconds=settings.product_clamav_timeout_seconds,
        upload_ttl=upload_ttl,
        maximum_file_bytes=settings.product_max_file_bytes,
        maximum_package_bytes=settings.product_max_package_bytes,
    )


def _configured_product_runtime(
    settings: Settings, injected: ProductRuntime | None
) -> ProductRuntime | None:
    if not settings.managed_products_enabled:
        return None
    runtime = injected or _product_runtime(settings)
    uploads_enabled = settings.managed_file_uploads_enabled
    if (
        settings.environment is Environment.PROD
        and uploads_enabled
        and not runtime.approved_semantic_cdr
    ):
        raise ValueError(
            "production managed-file uploads require an approved semantic/CDR "
            "scanner runtime"
        )
    return replace(runtime, managed_file_uploads_enabled=uploads_enabled)


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    workflow_engine: WorkflowEngine | None = None,
    password_hasher: PasswordHasher | None = None,
    product_runtime: ProductRuntime | None = None,
    workflow_runtime_factory: WorkflowRuntimeFactory = managed_camunda_engine,
) -> FastAPI:
    configured = settings or get_settings()
    sessions = session_factory or SessionFactory
    hasher = password_hasher or PasswordHasher()
    managed_products = _configured_product_runtime(configured, product_runtime)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            engine = workflow_engine
            if engine is None:
                engine = await stack.enter_async_context(
                    workflow_runtime_factory(configured)
                )
            application.state.workflow_engine = engine

            async with sessions() as session, session.begin():
                restored_configuration = await restore_active_configuration_projection(
                    session
                )
                if not restored_configuration:
                    await seed_organisation_units(session)
                if configured.allow_demo_users:
                    password = (
                        configured.demo_user_password.get_secret_value()
                        if configured.demo_user_password
                        else None
                    )
                    await seed_demo_users(
                        session,
                        hasher,
                        environment=configured.environment.value,
                        enabled=True,
                        shared_password=password,
                        ensure_organisation=False,
                    )
                    await initialise_admin_identity_sequence(session)
                    await initialise_admin_audit_anchor(session)
                await initialise_platform_classification(session)
                if restored_configuration:
                    if configured.allow_demo_users:
                        await restore_active_configuration_projection(session)
                else:
                    await seed_baseline_configuration(session)

            yield

    application = FastAPI(
        title="ISTARI Service API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=(
            None if configured.environment is Environment.PROD else "/openapi.json"
        ),
        docs_url=(None if configured.environment is Environment.PROD else "/docs"),
        redoc_url=(None if configured.environment is Environment.PROD else "/redoc"),
    )
    application.state.settings = configured
    application.state.session_factory = sessions
    application.state.password_hasher = hasher
    application.state.dummy_password_hash = hasher.hash(DUMMY_HASH_INPUT)
    application.state.login_password_semaphore = asyncio.Semaphore(
        configured.login_hash_concurrency
    )
    if managed_products is not None:
        application.state.product_runtime = managed_products
    application.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=configured.max_request_body_bytes,
        product_upload_max_bytes=configured.product_max_file_bytes,
    )
    application.add_middleware(OperationalTelemetryMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=sorted(configured.allowed_hosts),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(configured.trusted_origins),
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

    @application.exception_handler(ServiceError)
    async def handle_service_error(
        request: Request,
        error: ServiceError,
    ) -> JSONResponse:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and isinstance(
            error, (ObjectNotFound, InvalidAction)
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
                        reason_code=error.code,
                        actor_user_id=actor.id,
                        source=request.client.host if request.client else None,
                        correlation_id=getattr(request.state, "correlation_id", None),
                        request_method=request.method,
                        route_template=getattr(route, "path", None),
                    )
                )
        return JSONResponse(
            status_code=error.status_code,
            headers=getattr(error, "response_headers", None),
            content={
                "detail": {
                    "code": error.code,
                    "message": error.message,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = [
            {
                "loc": [
                    part if isinstance(part, int) else str(part)[:80]
                    for part in item.get("loc", ())
                ],
                "msg": str(item.get("msg", "Invalid value."))[:200],
                "type": str(item.get("type", "validation_error"))[:80],
            }
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    application.include_router(health.router)
    application.include_router(platform_security.router, prefix="/api/v1")
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(capabilities.router, prefix="/api/v1")
    application.include_router(admin.router, prefix="/api/v1")
    application.include_router(organisation.router, prefix="/api/v1")
    application.include_router(profiles.router, prefix="/api/v1")
    application.include_router(requests.router, prefix="/api/v1")
    application.include_router(request_coordination.router, prefix="/api/v1")
    application.include_router(request_conversations.router, prefix="/api/v1")
    application.include_router(statistics.router, prefix="/api/v1")
    application.include_router(team_workspaces.router, prefix="/api/v1")
    application.include_router(task_hasteners.router, prefix="/api/v1")
    application.include_router(workspace_collaboration.router, prefix="/api/v1")
    application.include_router(board.router, prefix="/api/v1")
    application.include_router(calendar.router, prefix="/api/v1")
    application.include_router(drafts.router, prefix="/api/v1")
    application.include_router(work_items.router, prefix="/api/v1")
    if configured.action_workspace_enabled:
        application.include_router(actions.action_router, prefix="/api/v1")
    if configured.notifications_enabled:
        application.include_router(actions.notification_router, prefix="/api/v1")
    if configured.managed_products_enabled:
        application.include_router(products.router, prefix="/api/v1")
        application.include_router(products.release_router, prefix="/api/v1")
    if configured.configuration_admin_enabled:
        application.include_router(configuration.router, prefix="/api/v1")
    if configured.planning_evolution_enabled:
        application.include_router(
            planning.router,
            prefix="/api/v1/team-workspaces",
        )
    if configured.statistics_evolution_enabled:
        application.include_router(
            statistics_evolution.router,
            prefix="/api/v1/statistics",
        )
    return application


app = create_app()
