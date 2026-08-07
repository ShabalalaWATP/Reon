"""FastAPI application composition for the service-request MVP."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

from camunda_orchestration_sdk import CamundaAsyncClient
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from istari_service.admin_audit import initialise_admin_audit_anchor
from istari_service.admin_sequence import initialise_admin_identity_sequence
from istari_service.auth_service import DUMMY_HASH_INPUT, PasswordHasher
from istari_service.config import Environment, Settings, get_settings
from istari_service.configuration_seed import seed_baseline_configuration
from istari_service.database import SessionFactory
from istari_service.demo_seed import seed_demo_users
from istari_service.errors import ServiceError
from istari_service.organisation_seed import seed_organisation_units
from istari_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from istari_service.product_runtime import ProductRuntime, clamav_product_runtime
from istari_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from istari_service.request_event_projection import NotificationProjectionReconciler
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
    products,
    requests,
    statistics,
    statistics_evolution,
    team_workspaces,
    work_items,
)
from istari_service.telemetry import OperationalTelemetryMiddleware
from istari_service.workflow.camunda import CamundaWorkflowEngine
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher
from istari_service.workflow_dispatch import WorkflowOutboxDispatcher
from istari_service.workflow_maintenance import (
    WorkflowReconciler,
    run_workflow_maintenance,
)


def _client_configuration(settings: Settings) -> dict[str, str]:
    address = settings.camunda_base_url
    if not address.endswith("/v2"):
        address = f"{address}/v2"
    auth_strategy = settings.camunda_auth_mode.upper()
    if auth_strategy not in {"NONE", "BASIC"}:
        raise ValueError("only NONE or BASIC Camunda authentication is configured")
    configuration = {
        "CAMUNDA_REST_ADDRESS": address,
        "CAMUNDA_AUTH_STRATEGY": auth_strategy,
        "CAMUNDA_SDK_LOG_LEVEL": "warn",
    }
    if auth_strategy == "BASIC":
        configuration["CAMUNDA_BASIC_AUTH_USERNAME"] = settings.camunda_username or ""
        configuration["CAMUNDA_BASIC_AUTH_PASSWORD"] = (
            settings.camunda_password.get_secret_value()
            if settings.camunda_password
            else ""
        )
    return configuration


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
    start_background_worker: bool = True,
    product_runtime: ProductRuntime | None = None,
) -> FastAPI:
    configured = settings or get_settings()
    sessions = session_factory or SessionFactory
    hasher = password_hasher or PasswordHasher()
    managed_products = _configured_product_runtime(configured, product_runtime)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        client: CamundaAsyncClient | None = None
        engine = workflow_engine
        if engine is None:
            client = CamundaAsyncClient(
                configuration=cast(Any, _client_configuration(configured))
            )
            await client.__aenter__()
            engine = CamundaWorkflowEngine(client)
        application.state.workflow_engine = engine

        async with sessions() as session, session.begin():
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
                )
                await initialise_admin_identity_sequence(session)
                await initialise_admin_audit_anchor(session)
            await seed_baseline_configuration(session)

        stop = asyncio.Event()
        maintenance: asyncio.Task[None] | None = None
        if start_background_worker:
            dispatcher = WorkflowOutboxDispatcher(
                sessions,
                engine,
                process_id=configured.camunda_process_id,
            )
            reconciler = WorkflowReconciler(sessions, engine)
            command_dispatcher = WorkflowCommandDispatcher(
                sessions,
                engine,
                managed_products_enabled=configured.managed_products_enabled,
            )
            maintenance = asyncio.create_task(
                run_workflow_maintenance(
                    dispatcher,
                    reconciler,
                    stop,
                    command_dispatcher=command_dispatcher,
                    notification_reconciler=(
                        NotificationProjectionReconciler(sessions)
                        if configured.notifications_enabled
                        else None
                    ),
                ),
                name="workflow-maintenance",
            )
        try:
            yield
        finally:
            stop.set()
            if maintenance is not None:
                await maintenance
            if client is not None:
                await client.__aexit__(None, None, None)

    application = FastAPI(
        title="ISTARI Service API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = configured
    application.state.session_factory = sessions
    application.state.password_hasher = hasher
    application.state.dummy_password_hash = hasher.hash(DUMMY_HASH_INPUT)
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
        _request: Request,
        error: ServiceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
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
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(capabilities.router, prefix="/api/v1")
    application.include_router(admin.router, prefix="/api/v1")
    application.include_router(organisation.router, prefix="/api/v1")
    application.include_router(requests.router, prefix="/api/v1")
    application.include_router(statistics.router, prefix="/api/v1")
    application.include_router(team_workspaces.router, prefix="/api/v1")
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
