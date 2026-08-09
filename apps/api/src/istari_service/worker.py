"""Process entry point for independently deployed maintenance work."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any, cast

from camunda_orchestration_sdk import CamundaAsyncClient

from istari_service.config import Settings, get_settings
from istari_service.database import SessionFactory, dispose_database
from istari_service.request_event_projection import NotificationProjectionReconciler
from istari_service.team_membership_sync import TeamMembershipProjector
from istari_service.worker_runtime import MaintenanceJob, WorkerIteration, run_worker
from istari_service.workflow.camunda import CamundaWorkflowEngine
from istari_service.workflow_client import camunda_client_configuration
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher
from istari_service.workflow_dispatch import WorkflowOutboxDispatcher
from istari_service.workflow_maintenance import WorkflowReconciler


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="istari-worker")
    command.add_argument("--once", action="store_true")
    return command


def build_iteration(
    settings: Settings,
    engine: CamundaWorkflowEngine,
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
    reconciliation = WorkflowReconciler(SessionFactory, engine)
    membership = TeamMembershipProjector(SessionFactory)
    jobs = [
        MaintenanceJob("workflow-start-dispatch", starts.dispatch_once),
        MaintenanceJob("workflow-command-dispatch", commands.dispatch_once),
        MaintenanceJob("workflow-reconciliation", reconciliation.reconcile_once),
    ]
    if settings.notifications_enabled:
        notifications = NotificationProjectionReconciler(SessionFactory)
        jobs.append(
            MaintenanceJob("notification-projection", notifications.reconcile_once)
        )
    jobs.append(MaintenanceJob("membership-projection", membership.reconcile_once))
    return WorkerIteration(
        SessionFactory,
        tuple(jobs),
        lease_seconds=settings.worker_lease_seconds,
    )


async def async_main(arguments: argparse.Namespace) -> int:
    settings = get_settings()
    client = CamundaAsyncClient(
        configuration=cast(Any, camunda_client_configuration(settings))
    )
    entered = False
    try:
        await client.__aenter__()
        entered = True
        iteration = build_iteration(settings, CamundaWorkflowEngine(client))
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
        if entered:
            await client.__aexit__(None, None, None)
        await dispose_database()


def main() -> int:
    try:
        return asyncio.run(async_main(parser().parse_args()))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
