"""Process entry point for independently deployed maintenance work."""

from __future__ import annotations

import argparse
import asyncio
from typing import cast

from mist_service.config import Settings, get_settings
from mist_service.database import (
    SECURITY_PSEUDONYM_KEY_INFO,
    SessionFactory,
    dispose_database,
)
from mist_service.platform_security_composition import platform_security_service
from mist_service.product_cleanup import ProductUploadCleanup
from mist_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from mist_service.request_embeddings import FastEmbedRequestEmbeddingProvider
from mist_service.request_event_projection import NotificationProjectionReconciler
from mist_service.request_search_indexer import RequestSearchIndexer
from mist_service.team_membership_sync import TeamMembershipProjector
from mist_service.worker_runtime import MaintenanceJob, WorkerIteration, run_worker
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow_cancellation_dispatch import (
    WorkflowCancellationDispatcher,
)
from mist_service.workflow_command_dispatch import WorkflowCommandDispatcher
from mist_service.workflow_dispatch import WorkflowOutboxDispatcher
from mist_service.workflow_maintenance import WorkflowReconciler
from mist_service.workflow_runtime import (
    WorkflowRuntimeFactory,
    managed_camunda_engine,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="mist-worker")
    command.add_argument("--once", action="store_true")
    return command


def build_iteration(
    settings: Settings,
    engine: WorkflowEngine,
) -> WorkerIteration:
    starts = WorkflowOutboxDispatcher(
        SessionFactory,
        engine,
        process_id=settings.camunda_process_id,
    )
    commands = WorkflowCommandDispatcher(
        SessionFactory,
        engine,
        managed_products_enabled=settings.managed_products_enabled,
    )
    cancellations = WorkflowCancellationDispatcher(SessionFactory, engine)
    reconciliation = WorkflowReconciler(SessionFactory, engine)
    membership = TeamMembershipProjector(SessionFactory)
    jobs = [
        MaintenanceJob("workflow-start-dispatch", starts.dispatch_once),
        MaintenanceJob("workflow-command-dispatch", commands.dispatch_once),
        MaintenanceJob("workflow-cancellation-dispatch", cancellations.dispatch_once),
        MaintenanceJob("workflow-reconciliation", reconciliation.reconcile_once),
    ]
    if settings.notifications_enabled:
        notifications = NotificationProjectionReconciler(SessionFactory)
        jobs.append(
            MaintenanceJob("notification-projection", notifications.reconcile_once)
        )
    if settings.request_matching_semantic_enabled:
        request_search = RequestSearchIndexer(
            SessionFactory,
            FastEmbedRequestEmbeddingProvider(
                model_name=settings.request_embedding_model,
                cache_path=settings.request_embedding_cache_path,
                threads=settings.request_embedding_threads,
            ),
            batch_size=settings.request_embedding_batch_size,
        )
        jobs.append(
            MaintenanceJob("request-search-index", request_search.reconcile_once)
        )
    if settings.managed_products_enabled:
        product_cleanup = ProductUploadCleanup(
            SessionFactory,
            PrivateFilesystemObjectStorage(settings.product_storage_path),
        )
        jobs.append(
            MaintenanceJob("product-upload-cleanup", product_cleanup.reconcile_once)
        )
    jobs.append(MaintenanceJob("membership-projection", membership.reconcile_once))

    async def password_assistance() -> bool:
        async with SessionFactory() as session, session.begin():
            return await platform_security_service(
                session,
                pseudonym_key=cast(
                    bytes, SessionFactory.kw["info"][SECURITY_PSEUDONYM_KEY_INFO]
                ),
                pseudonym_key_id=settings.security_pseudonym_key_id,
            ).process_pending_password_assistance()

    jobs.append(MaintenanceJob("password-assistance", password_assistance))
    return WorkerIteration(
        SessionFactory,
        tuple(jobs),
        lease_seconds=settings.worker_lease_seconds,
    )


async def async_main(
    arguments: argparse.Namespace,
    *,
    workflow_runtime_factory: WorkflowRuntimeFactory = managed_camunda_engine,
) -> int:
    settings = get_settings()
    try:
        async with workflow_runtime_factory(settings) as engine:
            iteration = build_iteration(settings, engine)
            if arguments.once:
                await iteration.run_once()
                return 0
            await run_worker(
                iteration,
                asyncio.Event(),
                interval_seconds=settings.worker_interval_seconds,
            )
            return 0
    finally:
        await dispose_database()


def main() -> int:
    try:
        return asyncio.run(async_main(parser().parse_args()))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
