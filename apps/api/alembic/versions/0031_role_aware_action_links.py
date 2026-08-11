"""Repair operational action audiences and role-aware queue links.

Revision ID: 0031_role_aware_action_links
Revises: 0030_team_operational_skills
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_role_aware_action_links"
down_revision: str | None = "0030_team_operational_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH claimed AS (
                SELECT DISTINCT ON (request_id, candidate_role)
                    request_id, candidate_role, assignee_user_id
                FROM workflow_tasks
                WHERE assignee_user_id IS NOT NULL
                    AND completed_at IS NULL
                    AND status IN (
                        'CLAIM_PENDING', 'CLAIMED', 'COMPLETION_PENDING', 'ERROR'
                    )
                ORDER BY request_id, candidate_role, updated_at DESC, id DESC
            )
            UPDATE action_projections AS action
            SET recipient_user_id = claimed.assignee_user_id,
                candidate_role = NULL,
                required_scope = NULL,
                organisation_unit_id = NULL,
                deep_link = CASE claimed.candidate_role
                    WHEN 'INTAKE_TRIAGE'
                        THEN '/triage?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN 'SERVICE_COORDINATION'
                        THEN '/coordination?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN 'OPERATIONS_ALLOCATION'
                        THEN '/allocation?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN 'DELIVERY_TEAM_LEAD'
                        THEN '/delivery/team?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN 'DELIVERY_SPECIALIST'
                        THEN '/delivery/my-work?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN 'QUALITY_RELEASE'
                        THEN '/quality-release?requestId=' || CAST(action.request_id AS TEXT)
                    ELSE '/requests/' || CAST(action.request_id AS TEXT)
                END,
                projected_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                version = action.version + 1
            FROM claimed
            WHERE action.request_id = claimed.request_id
                AND action.candidate_role = claimed.candidate_role
                AND action.is_active = TRUE
            """
        )
    )

    op.execute(
        sa.text(
            """
            WITH desired AS (
                SELECT action.id, CASE
                    WHEN request.status IN ('ROUTING_PENDING', 'TRIAGE_REVIEW')
                        THEN '/triage?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status IN ('COORDINATION_REVIEW', 'ON_HOLD')
                        THEN '/coordination?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status = 'ALLOCATION_REVIEW'
                        THEN '/allocation?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status IN ('DELIVERY_PLANNING', 'LEAD_REVIEW')
                        THEN '/delivery/team?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status IN ('IN_PROGRESS', 'REWORK_REQUIRED')
                        THEN '/delivery/my-work?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status = 'CUSTOMER_INFORMATION_REQUIRED'
                        AND action.stable_key LIKE '%:waiting:%'
                        THEN '/delivery/my-work?requestId=' || CAST(action.request_id AS TEXT)
                    WHEN request.status IN ('QUALITY_REVIEW', 'READY_FOR_RELEASE')
                        THEN '/quality-release?requestId=' || CAST(action.request_id AS TEXT)
                    ELSE '/requests/' || CAST(action.request_id AS TEXT)
                END AS deep_link
                FROM action_projections AS action
                JOIN service_requests AS request ON request.id = action.request_id
                WHERE action.is_active = TRUE
            )
            UPDATE action_projections AS action
            SET deep_link = desired.deep_link,
                projected_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                version = action.version + 1
            FROM desired
            WHERE action.id = desired.id
                AND action.deep_link IS DISTINCT FROM desired.deep_link
            """
        )
    )


def downgrade() -> None:
    # Audience repair is deliberately retained because broadening access on rollback
    # would be unsafe. Only the legacy link shape is restored.
    op.execute(
        sa.text(
            """
            UPDATE action_projections
            SET deep_link = '/requests/' || CAST(request_id AS TEXT),
                projected_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                version = version + 1
            WHERE request_id IS NOT NULL
                AND is_active = TRUE
            """
        )
    )
