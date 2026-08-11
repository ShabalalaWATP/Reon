"""Operator entry point for bounded maintenance jobs."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from uuid import UUID

from istari_service.database import SessionFactory, dispose_database
from istari_service.operational_snapshot import capture_operational_snapshot
from istari_service.restore_verification import verify_restored_database
from istari_service.retention import (
    RetentionPolicy,
    RetentionService,
    SqlAlchemyRetentionRepository,
)
from istari_service.workflow_attestation import (
    WorkflowAttestation,
    attest_workflow_availability,
)
from istari_service.workflow_recovery import recover_failed_workflow


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="istari-maintenance")
    subcommands = command.add_subparsers(dest="job", required=True)
    retention = subcommands.add_parser("retention")
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--confirm")
    retention.add_argument("--batch-size", type=int, default=1_000)
    verification = subcommands.add_parser("verify-restore")
    verification.add_argument(
        "--expected-revision",
        default="0032_coordination_language",
    )
    snapshot = subcommands.add_parser("health-snapshot")
    snapshot.add_argument("--max-command-age-seconds", type=int, default=300)
    snapshot.add_argument("--max-projection-age-seconds", type=int, default=600)
    recovery = subcommands.add_parser("workflow-recovery")
    recovery.add_argument("--request-id", type=UUID, required=True)
    recovery.add_argument("--apply", action="store_true")
    recovery.add_argument("--confirm")
    attestation = subcommands.add_parser("attest-workflow")
    attestation.add_argument("--process-id", required=True)
    attestation.add_argument("--process-version", type=int, required=True)
    attestation.add_argument("--process-definition-key", required=True)
    attestation.add_argument("--deployment-key", required=True)
    attestation.add_argument("--compatibility-key", required=True)
    attestation.add_argument("--checksum", required=True)
    attestation.add_argument("--operator-subject", required=True)
    attestation.add_argument("--apply", action="store_true")
    attestation.add_argument("--confirm")
    return command


async def run_retention(arguments: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        try:
            report = await RetentionService(SqlAlchemyRetentionRepository(session)).run(
                apply=arguments.apply,
                confirmation=arguments.confirm,
                policy=RetentionPolicy(batch_size=arguments.batch_size),
            )
            if arguments.apply:
                await session.commit()
            return asdict(report)
        except BaseException:
            await session.rollback()
            raise


async def async_main(arguments: argparse.Namespace) -> int:
    try:
        if arguments.job == "retention":
            result = await run_retention(arguments)
            exit_code = 0
        elif arguments.job == "verify-restore":
            async with SessionFactory() as session:
                verification_report = await verify_restored_database(
                    session,
                    expected_revision=arguments.expected_revision,
                )
                result = asdict(verification_report) | {
                    "valid": verification_report.valid
                }
                exit_code = 0 if verification_report.valid else 2
        elif arguments.job == "health-snapshot":
            async with SessionFactory() as session:
                snapshot_report = await capture_operational_snapshot(
                    session,
                    max_command_age_seconds=arguments.max_command_age_seconds,
                    max_projection_age_seconds=arguments.max_projection_age_seconds,
                )
                result = asdict(snapshot_report) | {"status": snapshot_report.status}
                exit_code = 0 if snapshot_report.status == "ok" else 2
        elif arguments.job == "workflow-recovery":
            async with SessionFactory() as session, session.begin():
                recovery_report = await recover_failed_workflow(
                    session,
                    arguments.request_id,
                    apply=arguments.apply,
                    confirmation=arguments.confirm,
                )
                result = asdict(recovery_report)
                exit_code = 0
        elif arguments.job == "attest-workflow":
            async with SessionFactory() as session, session.begin():
                valid = await attest_workflow_availability(
                    session,
                    WorkflowAttestation(
                        process_id=arguments.process_id,
                        process_version=arguments.process_version,
                        process_definition_key=arguments.process_definition_key,
                        deployment_key=arguments.deployment_key,
                        compatibility_key=arguments.compatibility_key,
                        checksum=arguments.checksum,
                        operator_subject=arguments.operator_subject,
                    ),
                    apply=arguments.apply,
                    confirmation=arguments.confirm,
                )
                result = {"valid": valid, "applied": arguments.apply}
                exit_code = 0
        else:
            raise ValueError("unsupported maintenance job")
        print(json.dumps(result, default=str, sort_keys=True))
        return exit_code
    finally:
        await dispose_database()


def main() -> int:
    return asyncio.run(async_main(parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
