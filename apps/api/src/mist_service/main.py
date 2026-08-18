"""FastAPI application composition for the service-request MVP."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import (
    AbstractAsyncContextManager,
    AsyncExitStack,
    asynccontextmanager,
)
from dataclasses import replace
from datetime import timedelta

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.admin_audit import initialise_admin_audit_anchor
from mist_service.admin_sequence import initialise_admin_identity_sequence
from mist_service.application_composition import compose_http_application
from mist_service.auth_service import DUMMY_HASH_INPUT, PasswordHasher
from mist_service.config import Environment, Settings, get_settings
from mist_service.configuration_seed import (
    restore_active_configuration_projection,
    seed_baseline_configuration,
)
from mist_service.database import SessionFactory
from mist_service.demo_seed import seed_demo_users
from mist_service.organisation_seed import seed_organisation_units
from mist_service.ownership import reconcile_owner_labels
from mist_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from mist_service.product_runtime import ProductRuntime, clamav_product_runtime
from mist_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from mist_service.repositories.platform_security import (
    initialise_platform_classification,
)
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow_runtime import (
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


async def _initialise_persistence(
    session: AsyncSession,
    settings: Settings,
    password_hasher: PasswordHasher,
) -> None:
    """Restore persisted configuration and initialise required baseline data."""
    restored_configuration = await restore_active_configuration_projection(session)
    if not restored_configuration:
        await seed_organisation_units(session)
    if settings.allow_demo_users:
        password = (
            settings.demo_user_password.get_secret_value()
            if settings.demo_user_password
            else None
        )
        await seed_demo_users(
            session,
            password_hasher,
            environment=settings.environment.value,
            enabled=True,
            shared_password=password,
            ensure_organisation=False,
        )
        await initialise_admin_identity_sequence(session)
        await initialise_admin_audit_anchor(session)
    await initialise_platform_classification(session)
    await reconcile_owner_labels(session)
    if restored_configuration:
        if settings.allow_demo_users:
            await restore_active_configuration_projection(session)
    else:
        await seed_baseline_configuration(session)


def _lifespan_context(
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    workflow_engine: WorkflowEngine | None,
    password_hasher: PasswordHasher,
    workflow_runtime_factory: WorkflowRuntimeFactory,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build the application lifespan while retaining injectable dependencies."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            engine = workflow_engine
            if engine is None:
                engine = await stack.enter_async_context(
                    workflow_runtime_factory(settings)
                )
            application.state.workflow_engine = engine

            async with sessions() as session, session.begin():
                await _initialise_persistence(session, settings, password_hasher)
            yield

    return lifespan


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

    application = FastAPI(
        title="Mist Service API",
        version="0.1.0",
        lifespan=_lifespan_context(
            configured,
            sessions,
            workflow_engine,
            hasher,
            workflow_runtime_factory,
        ),
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
    compose_http_application(application, configured)
    return application


app = create_app()
