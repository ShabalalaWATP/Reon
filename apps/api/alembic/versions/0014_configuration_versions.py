"""Effective-dated organisation and bounded workflow configuration.

Revision ID: 0014_configuration_versions
Revises: 0013_product_artifacts
Create Date: 2026-08-07 23:00:00
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0014_configuration_versions"
down_revision: str | None = "0013_product_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMESPACE = UUID("69f571ac-2f72-4a86-86b0-7784f3f064b1")
_SCHEMA_DIGEST = "4906bc0cebbca7dea5793c1835b219034106347e9db8322f1bc48eb820ee9c0a"
_BPMN_CHECKSUM = "4fb7167bc69744a22efb1c19ff2f84d086a35e4ce10cd416d221dba0a09023c5"
_CORE_FIELDS = [
    "title",
    "service_category",
    "description",
    "desired_outcome",
    "background_context",
    "required_by",
    "required_by_reason",
    "preferred_deliverable_type",
    "success_criteria",
    "requesting_business_area",
    "intended_recipients",
    "sensitivity",
    "handling_instructions",
]
_OUTCOMES = {
    "intake_review": ["request_information", "progress", "close"],
    "requester_response": ["provide_information", "withdraw"],
    "coordination_review": ["send_to_allocation", "return_to_triage", "hold", "close"],
    "on_hold": ["resume", "close"],
    "allocation_review": ["allocate", "return_to_coordination"],
    "delivery_planning": ["assign", "return_for_reallocation"],
    "delivery_work": ["submit"],
    "lead_review": ["approve", "changes_required"],
    "quality_review": ["approve", "changes_required"],
    "release": ["release"],
}


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _timestamps(*, updated: bool = False) -> list[sa.Column[Any]]:
    columns: list[sa.Column[Any]] = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]
    if updated:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    _create_versions()
    _create_registry()
    _create_workflow_definitions()
    _create_organisation_snapshots()
    _create_workflow_templates()
    _create_lifecycle_evidence()
    _create_request_pins()
    _extend_workflow_instances()
    _initialise_registry_and_backfill()


def _create_versions() -> None:
    op.create_table(
        "configuration_versions",
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            _enum(
                "DRAFT",
                "VALIDATED",
                "AWAITING_APPROVAL",
                "ACTIVE",
                "SUPERSEDED",
                "REJECTED",
                name="configuration_status",
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("based_on_version_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(updated=True),
        sa.CheckConstraint(
            "sequence > 0",
            name=op.f("ck_configuration_versions_configuration_sequence_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_configuration_versions_configuration_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_configuration_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["based_on_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_versions_based_on_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_versions")),
    )
    op.create_index(
        op.f("ix_configuration_versions_sequence"),
        "configuration_versions",
        ["sequence"],
        unique=True,
    )
    op.create_index(
        op.f("ix_configuration_versions_status"),
        "configuration_versions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_configuration_versions_created_by_user_id"),
        "configuration_versions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_configuration_versions_one_active",
        "configuration_versions",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def _create_registry() -> None:
    op.create_table(
        "configuration_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("next_sequence", sa.Integer(), server_default="1", nullable=False),
        sa.Column("active_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "next_sequence > 0",
            name=op.f("ck_configuration_registry_configuration_next_sequence"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_configuration_registry_configuration_registry_version"),
        ),
        sa.ForeignKeyConstraint(
            ["active_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_registry_active_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_registry")),
    )


def _create_workflow_definitions() -> None:
    op.create_table(
        "approved_workflow_definitions",
        sa.Column("process_id", sa.String(length=160), nullable=False),
        sa.Column("process_definition_key", sa.String(length=128), nullable=False),
        sa.Column("process_version", sa.Integer(), nullable=False),
        sa.Column("deployment_key", sa.String(length=128), nullable=False),
        sa.Column("compatibility_key", sa.String(length=80), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_available",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_timestamps(updated=True),
        sa.CheckConstraint(
            "process_version > 0",
            name=op.f("ck_approved_workflow_definitions_approved_process_version"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_approved_workflow_definitions_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approved_workflow_definitions")),
        sa.UniqueConstraint(
            "process_id",
            "process_version",
            name=op.f("uq_approved_workflow_definitions_process_id"),
        ),
        sa.UniqueConstraint(
            "process_definition_key",
            name=op.f("uq_approved_workflow_definitions_process_definition_key"),
        ),
        sa.UniqueConstraint(
            "deployment_key",
            name=op.f("uq_approved_workflow_definitions_deployment_key"),
        ),
        sa.UniqueConstraint(
            "checksum",
            name=op.f("uq_approved_workflow_definitions_checksum"),
        ),
    )
    for column in ("compatibility_key", "is_available"):
        op.create_index(
            op.f(f"ix_approved_workflow_definitions_{column}"),
            "approved_workflow_definitions",
            [column],
            unique=False,
        )


def _create_organisation_snapshots() -> None:
    op.create_table(
        "configuration_unit_revisions",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "kind",
            _enum(
                "ROOT",
                "COMMAND",
                "OPS_GROUP",
                "TEAM",
                name="configuration_organisation_kind",
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "routing_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("minimum_managers", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minimum_analysts", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name=op.f(
                "ck_configuration_unit_revisions_configuration_unit_effective_window"
            ),
        ),
        sa.CheckConstraint(
            "minimum_managers >= 0 AND minimum_analysts >= 0",
            name=op.f(
                "ck_configuration_unit_revisions_configuration_unit_staffing_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "kind = 'TEAM' OR (minimum_managers = 0 AND minimum_analysts = 0)",
            name=op.f(
                "ck_configuration_unit_revisions_configuration_unit_staffing_shape"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_unit_revisions_configuration_version_id_configuration_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_unit_revisions")),
        sa.UniqueConstraint(
            "configuration_version_id",
            "unit_id",
            "effective_from",
            name=op.f("uq_configuration_unit_revisions_configuration_version_id"),
        ),
    )
    op.create_index(
        op.f("ix_configuration_unit_revisions_configuration_version_id"),
        "configuration_unit_revisions",
        ["configuration_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_configuration_unit_revisions_unit_id"),
        "configuration_unit_revisions",
        ["unit_id"],
        unique=False,
    )
    op.create_index(
        "ix_configuration_unit_revision_window",
        "configuration_unit_revisions",
        ["configuration_version_id", "unit_id", "effective_from", "effective_until"],
        unique=False,
    )
    _create_hierarchy_edges()
    _create_candidate_groups()


def _create_hierarchy_edges() -> None:
    op.create_table(
        "configuration_hierarchy_edges",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("parent_unit_id", sa.Uuid(), nullable=False),
        sa.Column("child_unit_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "parent_unit_id <> child_unit_id",
            name=op.f(
                "ck_configuration_hierarchy_edges_configuration_edge_distinct_units"
            ),
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name=op.f(
                "ck_configuration_hierarchy_edges_configuration_edge_effective_window"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_hierarchy_edges_configuration_version_id_configuration_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_hierarchy_edges")),
        sa.UniqueConstraint(
            "configuration_version_id",
            "child_unit_id",
            "effective_from",
            name=op.f("uq_configuration_hierarchy_edges_configuration_version_id"),
        ),
    )
    for column in ("configuration_version_id", "parent_unit_id", "child_unit_id"):
        op.create_index(
            op.f(f"ix_configuration_hierarchy_edges_{column}"),
            "configuration_hierarchy_edges",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_configuration_edge_window",
        "configuration_hierarchy_edges",
        [
            "configuration_version_id",
            "child_unit_id",
            "effective_from",
            "effective_until",
        ],
        unique=False,
    )


def _create_candidate_groups() -> None:
    op.create_table(
        "configuration_candidate_groups",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            _enum("ROUTING", "MANAGER", "ANALYST", name="candidate_group_purpose"),
            nullable=False,
        ),
        sa.Column("candidate_group", sa.String(length=120), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_candidate_groups_configuration_version_id_configuration_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_candidate_groups")),
        sa.UniqueConstraint(
            "configuration_version_id",
            "unit_id",
            "purpose",
            name=op.f("uq_configuration_candidate_groups_configuration_version_id"),
        ),
    )
    for column in ("configuration_version_id", "unit_id", "candidate_group"):
        op.create_index(
            op.f(f"ix_configuration_candidate_groups_{column}"),
            "configuration_candidate_groups",
            [column],
            unique=False,
        )


def _create_workflow_templates() -> None:
    op.create_table(
        "configuration_workflow_templates",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_id", sa.String(length=80), nullable=False),
        sa.Column("schema_digest", sa.String(length=64), nullable=False),
        sa.Column("form_version", sa.String(length=80), nullable=False),
        sa.Column("notification_policy_version", sa.String(length=80), nullable=False),
        sa.Column("organisation_root_id", sa.Uuid(), nullable=False),
        sa.Column("route_depth", sa.Integer(), nullable=False),
        sa.Column("core_fields", sa.JSON(), nullable=False),
        sa.Column("service_categories", sa.JSON(), nullable=False),
        sa.Column("product_types", sa.JSON(), nullable=False),
        sa.Column("task_labels", sa.JSON(), nullable=False),
        sa.Column("allowed_outcomes", sa.JSON(), nullable=False),
        sa.Column("reminder_days", sa.JSON(), nullable=False),
        sa.Column("artefact_types", sa.JSON(), nullable=False),
        sa.Column("approved_link_domains", sa.JSON(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_workflow_templates_configuration_version_id_configuration_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["approved_workflow_definitions.id"],
            name=op.f(
                "fk_configuration_workflow_templates_workflow_definition_id_approved_workflow_definitions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_workflow_templates")),
    )
    op.create_index(
        op.f("ix_configuration_workflow_templates_configuration_version_id"),
        "configuration_workflow_templates",
        ["configuration_version_id"],
        unique=True,
    )
    _create_validation_findings()


def _create_validation_findings() -> None:
    op.create_table(
        "configuration_validation_findings",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "severity",
            _enum("ERROR", "WARNING", name="configuration_finding_severity"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("path", sa.String(length=160), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_validation_findings_configuration_version_id_configuration_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_configuration_validation_findings")
        ),
    )
    for column in ("configuration_version_id", "severity"):
        op.create_index(
            op.f(f"ix_configuration_validation_findings_{column}"),
            "configuration_validation_findings",
            [column],
            unique=False,
        )


def _create_lifecycle_evidence() -> None:
    op.create_table(
        "configuration_approvals",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            _enum("APPROVED", "REJECTED", name="configuration_approval_decision"),
            nullable=False,
        ),
        sa.Column("reviewed_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_approvals_configuration_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_configuration_approvals_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_approvals")),
        sa.UniqueConstraint(
            "configuration_version_id",
            name=op.f("uq_configuration_approvals_configuration_version_id"),
        ),
    )
    op.create_index(
        op.f("ix_configuration_approvals_actor_user_id"),
        "configuration_approvals",
        ["actor_user_id"],
        unique=False,
    )
    op.create_table(
        "configuration_activations",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("activated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("superseded_version_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_activations_configuration_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["configuration_approvals.id"],
            name=op.f(
                "fk_configuration_activations_approval_id_configuration_approvals"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_configuration_activations_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_configuration_activations_superseded_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_activations")),
        sa.UniqueConstraint(
            "configuration_version_id",
            name=op.f("uq_configuration_activations_configuration_version_id"),
        ),
        sa.UniqueConstraint(
            "approval_id", name=op.f("uq_configuration_activations_approval_id")
        ),
    )
    op.create_index(
        op.f("ix_configuration_activations_activated_by_user_id"),
        "configuration_activations",
        ["activated_by_user_id"],
        unique=False,
    )


def _create_request_pins() -> None:
    op.create_table(
        "request_configuration_pins",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_template_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_root_id", sa.Uuid(), nullable=False),
        sa.Column("form_version", sa.String(length=80), nullable=False),
        sa.Column("notification_policy_version", sa.String(length=80), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["service_requests.id"],
            name=op.f("fk_request_configuration_pins_request_id_service_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["configuration_versions.id"],
            name=op.f(
                "fk_request_configuration_pins_configuration_version_id_configuration_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_template_id"],
            ["configuration_workflow_templates.id"],
            name=op.f(
                "fk_request_configuration_pins_workflow_template_id_configuration_workflow_templates"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_configuration_pins")),
    )
    op.create_index(
        op.f("ix_request_configuration_pins_request_id"),
        "request_configuration_pins",
        ["request_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_request_configuration_pins_configuration_version_id"),
        "request_configuration_pins",
        ["configuration_version_id"],
        unique=False,
    )


def _extend_workflow_instances() -> None:
    with op.batch_alter_table("workflow_instances", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("process_checksum", sa.String(length=64), nullable=True)
        )


def _initialise_registry_and_backfill() -> None:
    bind = op.get_bind()
    registry = sa.table(
        "configuration_registry",
        sa.column("id", sa.Integer()),
        sa.column("next_sequence", sa.Integer()),
        sa.column("active_version_id", sa.Uuid()),
        sa.column("version", sa.Integer()),
    )
    bind.execute(
        registry.insert().values(
            id=1, next_sequence=1, active_version_id=None, version=1
        )
    )
    units = (
        bind.execute(
            sa.text(
                "SELECT id, code, name, kind, parent_id, staffing_status, "
                "routing_candidate_group, manager_candidate_group, analyst_candidate_group, "
                "created_at FROM organisation_units WHERE is_configured = true "
                "ORDER BY sort_order, code"
            )
        )
        .mappings()
        .all()
    )
    creator = bind.execute(
        sa.text(
            "SELECT id FROM users WHERE role = 'PLATFORM_ADMIN' AND is_active = true "
            "ORDER BY username LIMIT 1"
        )
    ).scalar_one_or_none()
    roots = [row for row in units if row["kind"] == "ROOT"]
    if not units or creator is None or len(roots) != 1:
        return
    now = datetime.now(UTC)
    effective_from = min((_aware(row["created_at"]) for row in units), default=now)
    version_id = uuid5(_NAMESPACE, "legacy-configuration-v1")
    workflow_id = uuid5(_NAMESPACE, "legacy-workflow-definition-v1")
    template_id = uuid5(_NAMESPACE, "legacy-workflow-template-v1")
    _insert_legacy_header(
        bind,
        version_id=version_id,
        workflow_id=workflow_id,
        template_id=template_id,
        creator_id=creator,
        root_id=roots[0]["id"],
        effective_from=effective_from,
        now=now,
    )
    _insert_legacy_units(bind, units, version_id, effective_from, now)
    _pin_existing_requests(bind, version_id, template_id, roots[0]["id"], now)
    bind.execute(
        registry.update()
        .where(registry.c.id == 1)
        .values(next_sequence=2, active_version_id=version_id)
    )


def _insert_legacy_header(
    bind: sa.Connection,
    *,
    version_id: UUID,
    workflow_id: UUID,
    template_id: UUID,
    creator_id: UUID,
    root_id: UUID,
    effective_from: datetime,
    now: datetime,
) -> None:
    bind.execute(
        sa.text(
            "INSERT INTO configuration_versions "
            "(id, sequence, label, status, effective_from, created_by_user_id, "
            "version, activated_at, created_at, updated_at) "
            "VALUES (:id, 1, :label, 'ACTIVE', :effective_from, :creator, 1, :now, :now, :now)"
        ),
        {
            "id": str(version_id),
            "label": "Imported baseline configuration",
            "effective_from": effective_from,
            "creator": str(creator_id),
            "now": now,
        },
    )
    bind.execute(
        sa.text(
            "INSERT INTO approved_workflow_definitions "
            "(id, process_id, process_definition_key, process_version, deployment_key, "
            "compatibility_key, checksum, approved_by_user_id, approved_at, is_available, "
            "created_at, updated_at) VALUES (:id, 'service-request-v1', :definition_key, "
            "1, :deployment_key, 'istari-human-route-v1', :checksum, :creator, :now, "
            "false, :now, :now)"
        ),
        {
            "id": str(workflow_id),
            "definition_key": "legacy-unverified-service-request-v1",
            "deployment_key": "legacy-unverified-deployment-v1",
            "checksum": _BPMN_CHECKSUM,
            "creator": str(creator_id),
            "now": now,
        },
    )
    labels = {key: key.replace("_", " ").title() for key in _OUTCOMES}
    bind.execute(
        sa.text(
            "INSERT INTO configuration_workflow_templates "
            "(id, configuration_version_id, schema_id, schema_digest, form_version, "
            "notification_policy_version, organisation_root_id, route_depth, core_fields, "
            "service_categories, product_types, task_labels, allowed_outcomes, reminder_days, "
            "artefact_types, approved_link_domains, workflow_definition_id, created_at) "
            "VALUES (:id, :version_id, 'istari.workflow-template/v1', :digest, 'legacy-v1', "
            "'legacy-v1', :root_id, 3, :core_fields, :categories, :product_types, :labels, "
            ":outcomes, :reminders, :artefacts, :domains, :workflow_id, :now)"
        ).bindparams(
            sa.bindparam("core_fields", type_=sa.JSON()),
            sa.bindparam("categories", type_=sa.JSON()),
            sa.bindparam("product_types", type_=sa.JSON()),
            sa.bindparam("labels", type_=sa.JSON()),
            sa.bindparam("outcomes", type_=sa.JSON()),
            sa.bindparam("reminders", type_=sa.JSON()),
            sa.bindparam("artefacts", type_=sa.JSON()),
            sa.bindparam("domains", type_=sa.JSON()),
        ),
        {
            "id": str(template_id),
            "version_id": str(version_id),
            "digest": _SCHEMA_DIGEST,
            "root_id": str(root_id),
            "core_fields": _CORE_FIELDS,
            "categories": ["General service support"],
            "product_types": ["Analytical response"],
            "labels": labels,
            "outcomes": _OUTCOMES,
            "reminders": [7, 3, 1],
            "artefacts": ["LEGACY_TEXT"],
            "domains": [],
            "workflow_id": str(workflow_id),
            "now": now,
        },
    )


def _insert_legacy_units(
    bind: sa.Connection,
    units: Sequence[sa.RowMapping],
    version_id: UUID,
    effective_from: datetime,
    now: datetime,
) -> None:
    for row in units:
        bind.execute(
            sa.text(
                "INSERT INTO configuration_unit_revisions "
                "(id, configuration_version_id, unit_id, code, name, kind, effective_from, "
                "routing_enabled, minimum_managers, minimum_analysts, created_at) VALUES "
                "(:id, :version_id, :unit_id, :code, :name, :kind, :effective_from, true, "
                ":managers, :analysts, :now)"
            ),
            {
                "id": str(uuid4()),
                "version_id": str(version_id),
                "unit_id": str(row["id"]),
                "code": row["code"],
                "name": row["name"],
                "kind": row["kind"],
                "effective_from": effective_from,
                "managers": 1 if row["kind"] == "TEAM" else 0,
                "analysts": 1 if row["kind"] == "TEAM" else 0,
                "now": now,
            },
        )
        if row["parent_id"] is not None:
            bind.execute(
                sa.text(
                    "INSERT INTO configuration_hierarchy_edges "
                    "(id, configuration_version_id, parent_unit_id, child_unit_id, "
                    "effective_from, created_at) VALUES "
                    "(:id, :version_id, :parent_id, :child_id, :effective_from, :now)"
                ),
                {
                    "id": str(uuid4()),
                    "version_id": str(version_id),
                    "parent_id": str(row["parent_id"]),
                    "child_id": str(row["id"]),
                    "effective_from": effective_from,
                    "now": now,
                },
            )
        _insert_candidate_groups(bind, row, version_id, now)


def _insert_candidate_groups(
    bind: sa.Connection,
    row: sa.RowMapping,
    version_id: UUID,
    now: datetime,
) -> None:
    groups = (
        ("ROUTING", row["routing_candidate_group"]),
        ("MANAGER", row["manager_candidate_group"]),
        ("ANALYST", row["analyst_candidate_group"]),
    )
    for purpose, group in groups:
        if group is None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO configuration_candidate_groups "
                "(id, configuration_version_id, unit_id, purpose, candidate_group, created_at) "
                "VALUES (:id, :version_id, :unit_id, :purpose, :candidate_group, :now)"
            ),
            {
                "id": str(uuid4()),
                "version_id": str(version_id),
                "unit_id": str(row["id"]),
                "purpose": purpose,
                "candidate_group": group,
                "now": now,
            },
        )


def _pin_existing_requests(
    bind: sa.Connection,
    version_id: UUID,
    template_id: UUID,
    root_id: UUID,
    now: datetime,
) -> None:
    policy_snapshot = _legacy_request_policy_snapshot(bind, root_id)
    request_ids = (
        bind.execute(sa.text("SELECT id FROM service_requests")).scalars().all()
    )
    for request_id in request_ids:
        bind.execute(
            sa.text(
                "INSERT INTO request_configuration_pins "
                "(id, request_id, configuration_version_id, workflow_template_id, "
                "organisation_root_id, form_version, notification_policy_version, snapshot, "
                "created_at) VALUES (:id, :request_id, :version_id, :template_id, :root_id, "
                "'legacy-v1', 'legacy-v1', :snapshot, :now)"
            ).bindparams(sa.bindparam("snapshot", type_=sa.JSON())),
            {
                "id": str(uuid4()),
                "request_id": str(request_id),
                "version_id": str(version_id),
                "template_id": str(template_id),
                "root_id": str(root_id),
                "snapshot": {
                    "configurationSequence": 1,
                    "workflowSchemaDigest": _SCHEMA_DIGEST,
                    "processId": "service-request-v1",
                    "processVersion": 1,
                    "processChecksum": _BPMN_CHECKSUM,
                    "backfill": "legacy-recording-only",
                    **policy_snapshot,
                },
                "now": now,
            },
        )
    bind.execute(
        sa.text(
            "UPDATE workflow_instances SET process_version = "
            "COALESCE(process_version, 1), process_checksum = :checksum"
        ),
        {"checksum": _BPMN_CHECKSUM},
    )
    starts = bind.execute(
        sa.text(
            "SELECT id, payload FROM workflow_outbox WHERE event_type = 'START_PROCESS'"
        )
    ).mappings()
    for start in starts:
        payload = start["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload.update(
            {
                "processId": "service-request-v1",
                "processVersion": 1,
                "processChecksum": _BPMN_CHECKSUM,
            }
        )
        bind.execute(
            sa.text(
                "UPDATE workflow_outbox SET payload = :payload WHERE id = :id"
            ).bindparams(sa.bindparam("payload", type_=sa.JSON())),
            {"id": str(start["id"]), "payload": payload},
        )


def _legacy_request_policy_snapshot(
    bind: sa.Connection,
    root_id: UUID,
) -> dict[str, object]:
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, code, name, kind, parent_id, staffing_status, sort_order, "
                "routing_candidate_group, manager_candidate_group, analyst_candidate_group "
                "FROM organisation_units WHERE is_configured = true "
                "ORDER BY sort_order, code"
            )
        ).mappings()
    )
    groups: list[dict[str, object]] = []
    for row in rows:
        mappings = (
            ("ROUTING", row["routing_candidate_group"]),
            ("MANAGER", row["manager_candidate_group"]),
            ("ANALYST", row["analyst_candidate_group"]),
        )
        groups.extend(
            {
                "unitId": str(row["id"]),
                "purpose": purpose,
                "candidateGroup": group,
            }
            for purpose, group in mappings
            if group is not None
        )
    domains: tuple[str, ...] = ()
    domains_digest = hashlib.sha256(
        json.dumps(domains, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "requestPolicySchema": "istari.request-policy/v1",
        "organisation": {
            "rootUnitId": str(root_id),
            "units": [
                {
                    "unitId": str(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "routingEnabled": True,
                    "staffingStatus": row["staffing_status"],
                    "sortOrder": row["sort_order"],
                }
                for row in rows
            ],
            "edges": [
                {
                    "parentUnitId": str(row["parent_id"]),
                    "childUnitId": str(row["id"]),
                }
                for row in rows
                if row["parent_id"] is not None
            ],
            "candidateGroups": groups,
        },
        "catalogue": {
            "serviceCategories": ["General service support"],
            "productTypes": ["Analytical response"],
            "artefactTypes": ["LEGACY_TEXT"],
        },
        "approvedLinkDomains": list(domains),
        "approvedLinkDomainsDigest": domains_digest,
    }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def downgrade() -> None:
    with op.batch_alter_table("workflow_instances", schema=None) as batch_op:
        batch_op.drop_column("process_checksum")
    op.drop_index(
        op.f("ix_request_configuration_pins_configuration_version_id"),
        table_name="request_configuration_pins",
    )
    op.drop_index(
        op.f("ix_request_configuration_pins_request_id"),
        table_name="request_configuration_pins",
    )
    op.drop_table("request_configuration_pins")
    op.drop_index(
        op.f("ix_configuration_activations_activated_by_user_id"),
        table_name="configuration_activations",
    )
    op.drop_table("configuration_activations")
    op.drop_index(
        op.f("ix_configuration_approvals_actor_user_id"),
        table_name="configuration_approvals",
    )
    op.drop_table("configuration_approvals")
    for column in ("severity", "configuration_version_id"):
        op.drop_index(
            op.f(f"ix_configuration_validation_findings_{column}"),
            table_name="configuration_validation_findings",
        )
    op.drop_table("configuration_validation_findings")
    op.drop_index(
        op.f("ix_configuration_workflow_templates_configuration_version_id"),
        table_name="configuration_workflow_templates",
    )
    op.drop_table("configuration_workflow_templates")
    for column in ("candidate_group", "unit_id", "configuration_version_id"):
        op.drop_index(
            op.f(f"ix_configuration_candidate_groups_{column}"),
            table_name="configuration_candidate_groups",
        )
    op.drop_table("configuration_candidate_groups")
    op.drop_index(
        "ix_configuration_edge_window", table_name="configuration_hierarchy_edges"
    )
    for column in ("child_unit_id", "parent_unit_id", "configuration_version_id"):
        op.drop_index(
            op.f(f"ix_configuration_hierarchy_edges_{column}"),
            table_name="configuration_hierarchy_edges",
        )
    op.drop_table("configuration_hierarchy_edges")
    op.drop_index(
        "ix_configuration_unit_revision_window",
        table_name="configuration_unit_revisions",
    )
    op.drop_index(
        op.f("ix_configuration_unit_revisions_unit_id"),
        table_name="configuration_unit_revisions",
    )
    op.drop_index(
        op.f("ix_configuration_unit_revisions_configuration_version_id"),
        table_name="configuration_unit_revisions",
    )
    op.drop_table("configuration_unit_revisions")
    for column in ("is_available", "compatibility_key"):
        op.drop_index(
            op.f(f"ix_approved_workflow_definitions_{column}"),
            table_name="approved_workflow_definitions",
        )
    op.drop_table("approved_workflow_definitions")
    op.drop_table("configuration_registry")
    op.drop_index(
        "uq_configuration_versions_one_active", table_name="configuration_versions"
    )
    op.drop_index(
        op.f("ix_configuration_versions_created_by_user_id"),
        table_name="configuration_versions",
    )
    op.drop_index(
        op.f("ix_configuration_versions_status"),
        table_name="configuration_versions",
    )
    op.drop_index(
        op.f("ix_configuration_versions_sequence"),
        table_name="configuration_versions",
    )
    op.drop_table("configuration_versions")
