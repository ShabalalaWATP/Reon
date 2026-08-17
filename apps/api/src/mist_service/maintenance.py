"""Operator entry point for bounded maintenance jobs."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from uuid import UUID

from mist_service.config import get_settings
from mist_service.database import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
    dispose_database,
)
from mist_service.legal_holds import LegalHoldService
from mist_service.operational_snapshot import capture_operational_snapshot
from mist_service.restore_verification import verify_restored_database
from mist_service.retention import (
    DisposalIdentity,
    RetentionPolicy,
    RetentionService,
    SqlAlchemyRetentionRepository,
)
from mist_service.workflow_attestation import (
    WorkflowAttestation,
    attest_workflow_availability,
)
from mist_service.workflow_recovery import recover_failed_workflow


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="mist-maintenance")
    subcommands = command.add_subparsers(dest="job", required=True)
    retention = subcommands.add_parser("retention")
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--confirm")
    retention.add_argument("--batch-size", type=int, default=1_000)
    holds = subcommands.add_parser("legal-hold")
    holds.add_argument("action", choices=("apply", "release"))
    holds.add_argument("--target-type", required=True)
    holds.add_argument("--target-id", type=UUID, required=True)
    holds.add_argument("--reason-code")
    verification = subcommands.add_parser("verify-restore")
    verification.add_argument(
        "--expected-revision",
        default="0049_legacy_product_cleanup",
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
    settings = get_settings()
    factory = SessionFactory
    engine = None
    if arguments.apply:
        if not settings.maintenance_database_url:
            raise ValueError("MAINTENANCE_DATABASE_URL is required for disposal")
        configured = settings.model_copy(
            update={"database_url": settings.maintenance_database_url}
        )
        engine = create_database_engine(configured)
        factory = create_session_factory(
            engine,
            audit_hmac_keys=settings.audit_hmac_keys,
            audit_active_key_id=settings.audit_hmac_active_key_id,
        )
    async with factory() as session:
        try:
            operator_subject = settings.maintenance_operator_subject
            disposal_authority = settings.maintenance_disposal_authority
            identity = (
                DisposalIdentity(operator_subject, disposal_authority)
                if operator_subject and disposal_authority
                else None
            )
            repository = (
                SqlAlchemyRetentionRepository(session, identity)
                if identity is not None
                else SqlAlchemyRetentionRepository(session)
            )
            report = await RetentionService(repository).run(
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
        finally:
            if engine is not None:
                await engine.dispose()


async def run_legal_hold(arguments: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    subject = settings.maintenance_operator_subject
    authority = settings.maintenance_legal_hold_authority
    if subject is None or authority is None:
        raise ValueError("configured maintenance identity and authority are required")
    if not settings.maintenance_database_url:
        raise ValueError("MAINTENANCE_DATABASE_URL is required for legal holds")
    configured = settings.model_copy(
        update={"database_url": settings.maintenance_database_url}
    )
    engine = create_database_engine(configured)
    factory = create_session_factory(
        engine,
        audit_hmac_keys=settings.audit_hmac_keys,
        audit_active_key_id=settings.audit_hmac_active_key_id,
    )
    try:
        async with factory() as session, session.begin():
            service = LegalHoldService(session, subject=subject, authority=authority)
            hold = (
                await service.apply(
                    arguments.target_type,
                    arguments.target_id,
                    arguments.reason_code or "",
                )
                if arguments.action == "apply"
                else await service.release(arguments.target_type, arguments.target_id)
            )
            return {"id": str(hold.id), "action": arguments.action}
    finally:
        await engine.dispose()


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
        elif arguments.job == "legal-hold":
            result = await run_legal_hold(arguments)
            exit_code = 0
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
