"""Immutable, effective-dated organisation and workflow configuration models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.configuration_types import (
    ApprovalDecision,
    CandidateGroupPurpose,
    ConfigurationStatus,
    FindingSeverity,
)
from istari_service.models import (
    UTC_TS,
    UUID_TYPE,
    Base,
    CreatedMixin,
    TimestampMixin,
    _enum,
)
from istari_service.organisation_models import OrganisationKind


class ConfigurationVersion(TimestampMixin, Base):
    __tablename__ = "configuration_versions"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="configuration_sequence_positive"),
        CheckConstraint("version > 0", name="configuration_version_positive"),
        Index(
            "uq_configuration_versions_one_active",
            "status",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    sequence: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[ConfigurationStatus] = mapped_column(
        _enum(ConfigurationStatus, "configuration_status"), index=True
    )
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    based_on_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    validated_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    submitted_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    activated_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    rejected_at: Mapped[datetime | None] = mapped_column(UTC_TS)


class ConfigurationRegistry(Base):
    __tablename__ = "configuration_registry"
    __table_args__ = (
        CheckConstraint("next_sequence > 0", name="configuration_next_sequence"),
        CheckConstraint("version > 0", name="configuration_registry_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    active_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ConfigurationUnitRevision(CreatedMixin, Base):
    __tablename__ = "configuration_unit_revisions"
    __table_args__ = (
        UniqueConstraint("configuration_version_id", "unit_id", "effective_from"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="effective_window",
        ),
        CheckConstraint(
            "minimum_managers >= 0 AND minimum_analysts >= 0",
            name="staffing_nonnegative",
        ),
        CheckConstraint(
            "kind = 'TEAM' OR (minimum_managers = 0 AND minimum_analysts = 0)",
            name="staffing_shape",
        ),
        Index(
            "ix_configuration_unit_revision_window",
            "configuration_version_id",
            "unit_id",
            "effective_from",
            "effective_until",
        ),
    )

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(UUID_TYPE, index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[OrganisationKind] = mapped_column(
        _enum(OrganisationKind, "configuration_organisation_kind")
    )
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    effective_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    routing_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    minimum_managers: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    minimum_analysts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )


class ConfigurationHierarchyEdge(CreatedMixin, Base):
    __tablename__ = "configuration_hierarchy_edges"
    __table_args__ = (
        UniqueConstraint("configuration_version_id", "child_unit_id", "effective_from"),
        CheckConstraint(
            "parent_unit_id <> child_unit_id",
            name="distinct_units",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="effective_window",
        ),
        Index(
            "ix_configuration_edge_window",
            "configuration_version_id",
            "child_unit_id",
            "effective_from",
            "effective_until",
        ),
    )

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="CASCADE"), index=True
    )
    parent_unit_id: Mapped[UUID] = mapped_column(UUID_TYPE, index=True)
    child_unit_id: Mapped[UUID] = mapped_column(UUID_TYPE, index=True)
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    effective_until: Mapped[datetime | None] = mapped_column(UTC_TS)


class ConfigurationCandidateGroup(CreatedMixin, Base):
    __tablename__ = "configuration_candidate_groups"
    __table_args__ = (
        UniqueConstraint("configuration_version_id", "unit_id", "purpose"),
    )

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(UUID_TYPE, index=True)
    purpose: Mapped[CandidateGroupPurpose] = mapped_column(
        _enum(CandidateGroupPurpose, "candidate_group_purpose")
    )
    candidate_group: Mapped[str] = mapped_column(String(120), index=True)


class ApprovedWorkflowDefinition(TimestampMixin, Base):
    __tablename__ = "approved_workflow_definitions"
    __table_args__ = (
        UniqueConstraint("process_id", "process_version"),
        CheckConstraint("process_version > 0", name="approved_process_version"),
    )

    process_id: Mapped[str] = mapped_column(String(160))
    process_definition_key: Mapped[str] = mapped_column(String(128), unique=True)
    process_version: Mapped[int] = mapped_column(Integer)
    deployment_key: Mapped[str] = mapped_column(String(128), unique=True)
    compatibility_key: Mapped[str] = mapped_column(String(80), index=True)
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    approved_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime] = mapped_column(UTC_TS)
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), index=True
    )


class ConfigurationWorkflowTemplate(CreatedMixin, Base):
    __tablename__ = "configuration_workflow_templates"

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    schema_id: Mapped[str] = mapped_column(String(80))
    schema_digest: Mapped[str] = mapped_column(String(64))
    form_version: Mapped[str] = mapped_column(String(80))
    notification_policy_version: Mapped[str] = mapped_column(String(80))
    organisation_root_id: Mapped[UUID] = mapped_column(UUID_TYPE)
    route_depth: Mapped[int] = mapped_column(Integer)
    core_fields: Mapped[list[str]] = mapped_column(JSON)
    service_categories: Mapped[list[str]] = mapped_column(JSON)
    product_types: Mapped[list[str]] = mapped_column(JSON)
    task_labels: Mapped[dict[str, str]] = mapped_column(JSON)
    allowed_outcomes: Mapped[dict[str, list[str]]] = mapped_column(JSON)
    reminder_days: Mapped[list[int]] = mapped_column(JSON)
    artefact_types: Mapped[list[str]] = mapped_column(JSON)
    approved_link_domains: Mapped[list[str]] = mapped_column(JSON)
    workflow_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("approved_workflow_definitions.id", ondelete="RESTRICT")
    )


class ConfigurationValidationFinding(CreatedMixin, Base):
    __tablename__ = "configuration_validation_findings"

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        _enum(FindingSeverity, "configuration_finding_severity"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(String(160))
    unit_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)


class ConfigurationApproval(CreatedMixin, Base):
    __tablename__ = "configuration_approvals"

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"), unique=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        _enum(ApprovalDecision, "configuration_approval_decision")
    )
    reviewed_version: Mapped[int] = mapped_column(Integer)
    snapshot_digest: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)


class ConfigurationActivation(CreatedMixin, Base):
    __tablename__ = "configuration_activations"

    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"), unique=True
    )
    approval_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_approvals.id", ondelete="RESTRICT"), unique=True
    )
    activated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    superseded_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(Text)
    snapshot_digest: Mapped[str] = mapped_column(String(64))
    activated_at: Mapped[datetime] = mapped_column(UTC_TS)


class RequestConfigurationPin(CreatedMixin, Base):
    __tablename__ = "request_configuration_pins"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), unique=True, index=True
    )
    configuration_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"), index=True
    )
    workflow_template_id: Mapped[UUID] = mapped_column(
        ForeignKey("configuration_workflow_templates.id", ondelete="RESTRICT")
    )
    organisation_root_id: Mapped[UUID] = mapped_column(UUID_TYPE)
    form_version: Mapped[str] = mapped_column(String(80))
    notification_policy_version: Mapped[str] = mapped_column(String(80))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)


def _reject_evidence_mutation(_mapper: Any, _connection: Any, _target: Any) -> None:
    raise ValueError("configuration evidence and request pins are append-only")


for evidence_type in (
    ConfigurationApproval,
    ConfigurationActivation,
    RequestConfigurationPin,
):
    event.listen(evidence_type, "before_update", _reject_evidence_mutation)
    event.listen(evidence_type, "before_delete", _reject_evidence_mutation)
