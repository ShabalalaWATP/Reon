"""Synthetic pre-0044 records for the PostgreSQL migration round-trip."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

REQUESTER_ID = UUID("10000000-0000-0000-0000-000000000001")
STAFF_ID = UUID("10000000-0000-0000-0000-000000000002")
QC_ACTIVE_ID = UUID("10000000-0000-0000-0000-000000000003")
QC_INACTIVE_ID = UUID("10000000-0000-0000-0000-000000000004")
CRIOC_ID = UUID("20000000-0000-0000-0000-000000000001")
QC_TEAM_ID = UUID("d2893c1e-7018-5102-bacc-f4b1217721e3")
MANAGED_REQUEST_ID = UUID("30000000-0000-0000-0000-000000000001")
LEGACY_REQUEST_ID = UUID("30000000-0000-0000-0000-000000000002")
PACKAGE_ID = UUID("40000000-0000-0000-0000-000000000001")
SECOND_PACKAGE_ID = UUID("40000000-0000-0000-0000-000000000002")
CONVERSATION_ID = UUID("50000000-0000-0000-0000-000000000001")
MESSAGE_ID = UUID("50000000-0000-0000-0000-000000000002")
DELIVERY_ID = UUID("50000000-0000-0000-0000-000000000003")
REQUEST_EVENT_ID = UUID("50000000-0000-0000-0000-000000000004")


async def seed_revision_0043(connection: AsyncConnection) -> None:
    """Insert records whose backfills must survive the following revisions."""

    await connection.execute(
        text(
            "INSERT INTO users (id, username, email, display_name, password_hash, "
            "role, scope, is_active) VALUES "
            "(:requester, 'migration.requester', 'requester@example.test', "
            "'Migration Requester', 'synthetic-hash', 'REQUESTER', 'customer', true), "
            "(:staff, 'migration.staff', 'staff@example.test', "
            "'Migration Staff', 'synthetic-hash', 'DELIVERY_SPECIALIST', "
            "'delivery', true), "
            "(:qc_active, 'migration.qc.active', 'qc-active@example.test', "
            "'Migration QC Active', 'synthetic-hash', 'QUALITY_RELEASE', "
            "'quality', true), "
            "(:qc_inactive, 'migration.qc.inactive', 'qc-inactive@example.test', "
            "'Migration QC Inactive', 'synthetic-hash', 'QUALITY_RELEASE', "
            "'quality', false)"
        ),
        {
            "requester": REQUESTER_ID,
            "staff": STAFF_ID,
            "qc_active": QC_ACTIVE_ID,
            "qc_inactive": QC_INACTIVE_ID,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO organisation_units (id, code, name, kind, parent_id, "
            "staffing_status, routing_candidate_group, manager_candidate_group, "
            "analyst_candidate_group) VALUES "
            "(:id, 'CRIOC', 'CRIOC root', 'ROOT', NULL, 'ROUTING_POOL', "
            "'crioc-routing', NULL, NULL)"
        ),
        {"id": CRIOC_ID},
    )
    await _seed_sessions(connection)
    await _seed_requests(connection)
    await _seed_preferences_and_views(connection)
    await connection.execute(
        text(
            "INSERT INTO product_packages (id, request_id, package_version, "
            "creation_key, author_user_id, status) VALUES "
            "(:id, :request_id, 1, :creation_key, :author, 'DRAFT')"
        ),
        {
            "id": PACKAGE_ID,
            "request_id": MANAGED_REQUEST_ID,
            "creation_key": UUID("40000000-0000-0000-0000-000000000011"),
            "author": STAFF_ID,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO security_events (id, event_type, outcome, reason_code, "
            "deduplication_key) VALUES "
            "(:id, 'MIGRATION_ASSURANCE', 'DENIED', 'SYNTHETIC', 'roundtrip-key')"
        ),
        {"id": UUID("60000000-0000-0000-0000-000000000001")},
    )


async def seed_manual_qc_history(connection: AsyncConnection) -> None:
    """Add non-migration-owned QC history which downgrade must retain."""

    await connection.execute(
        text(
            "INSERT INTO team_memberships (id, user_id, team_id, workspace_position, "
            "effective_from, effective_until, start_projected_at, end_projected_at, "
            "start_reason, end_reason) VALUES (:id, :user, :team, 'MEMBER', "
            "CURRENT_TIMESTAMP - INTERVAL '2 days', "
            "CURRENT_TIMESTAMP - INTERVAL '1 day', "
            "CURRENT_TIMESTAMP - INTERVAL '2 days', "
            "CURRENT_TIMESTAMP - INTERVAL '1 day', "
            "'Synthetic retained QC history', 'Synthetic historical end')"
        ),
        {
            "id": UUID("d0000000-0000-0000-0000-000000000001"),
            "user": QC_ACTIVE_ID,
            "team": QC_TEAM_ID,
        },
    )


async def _seed_sessions(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "INSERT INTO sessions (id, user_id, token_hash, csrf_token_hash, "
            "credential_version, expires_at) VALUES "
            "(:requester_session, :requester, :requester_token, :requester_csrf, "
            "1, CURRENT_TIMESTAMP + INTERVAL '1 day'), "
            "(:staff_session, :staff, :staff_token, :staff_csrf, "
            "1, CURRENT_TIMESTAMP + INTERVAL '1 day')"
        ),
        {
            "requester_session": UUID("70000000-0000-0000-0000-000000000001"),
            "requester": REQUESTER_ID,
            "requester_token": "1" * 64,
            "requester_csrf": "2" * 64,
            "staff_session": UUID("70000000-0000-0000-0000-000000000002"),
            "staff": STAFF_ID,
            "staff_token": "3" * 64,
            "staff_csrf": "4" * 64,
        },
    )


async def _seed_requests(connection: AsyncConnection) -> None:
    statement = text(
        "INSERT INTO service_requests (id, reference, submission_key, requester_id, "
        "title, service_category, description, question_to_answer, desired_outcome, "
        "background_context, subject_area_or_location, coverage_start, coverage_end, "
        "customer_urgency, supported_activity_or_decision, required_by, "
        "required_by_reason, preferred_deliverable_type, success_criteria, "
        "constraints_or_caveats, supporting_information, sensitivity, "
        "handling_instructions, status, current_owner) VALUES "
        "(:id, :reference, :submission_key, :requester, :title, 'Analysis', "
        "'Synthetic migration description', 'Synthetic question', "
        "'Synthetic outcome', 'Synthetic background', 'Synthetic area', "
        ":coverage_start, :coverage_end, 'ROUTINE', 'Synthetic decision', "
        ":required_by, 'Synthetic deadline', 'PDF', 'Synthetic success', "
        "'No constraints', 'No supporting material', 'OFFICIAL', "
        "'Synthetic handling only', 'IN_PROGRESS', 'SSG Team')"
    )
    common = {
        "requester": REQUESTER_ID,
        "coverage_start": date(2026, 8, 1),
        "coverage_end": date(2026, 8, 2),
        "required_by": date(2026, 8, 20),
    }
    await connection.execute(
        statement,
        {
            **common,
            "id": MANAGED_REQUEST_ID,
            "reference": "SR-MIGRATION-MANAGED",
            "submission_key": UUID("30000000-0000-0000-0000-000000000011"),
            "title": "Synthetic managed request",
        },
    )
    await connection.execute(
        statement,
        {
            **common,
            "id": LEGACY_REQUEST_ID,
            "reference": "SR-MIGRATION-LEGACY",
            "submission_key": UUID("30000000-0000-0000-0000-000000000012"),
            "title": "Synthetic legacy request",
        },
    )


async def _seed_preferences_and_views(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "INSERT INTO notification_preferences (id, user_id, event_group, "
            "enabled, reminder_days) VALUES "
            "(:requester_pref, :requester, 'REQUEST_LIFECYCLE', true, '[1]'), "
            "(:staff_pref, :staff, 'REQUEST_LIFECYCLE', false, '[2]')"
        ),
        {
            "requester_pref": UUID("80000000-0000-0000-0000-000000000001"),
            "requester": REQUESTER_ID,
            "staff_pref": UUID("80000000-0000-0000-0000-000000000002"),
            "staff": STAFF_ID,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO saved_action_views (id, owner_user_id, name, filters, "
            "visible_columns) VALUES "
            "(:requester_view, :requester, 'Existing customer view', '{}', '[]'), "
            "(:staff_view, :staff, 'Shared migration view', "
            '\'{"section":"NEEDS_ATTENTION"}\', \'["reference"]\')'
        ),
        {
            "requester_view": UUID("90000000-0000-0000-0000-000000000001"),
            "requester": REQUESTER_ID,
            "staff_view": UUID("90000000-0000-0000-0000-000000000002"),
            "staff": STAFF_ID,
        },
    )
