"""Persistence-independent configuration records and lifecycle values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from mist_service.organisation_models import OrganisationKind


class ConfigurationStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class CandidateGroupPurpose(StrEnum):
    ROUTING = "ROUTING"
    MANAGER = "MANAGER"
    ANALYST = "ANALYST"


class FindingSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PreviewChangeType(StrEnum):
    ADDED = "ADDED"
    MOVED = "MOVED"
    RENAMED = "RENAMED"
    RETIRED = "RETIRED"
    UNSTAFFED = "UNSTAFFED"
    PERMISSION_AFFECTED = "PERMISSION_AFFECTED"
    WORKFLOW_AFFECTED = "WORKFLOW_AFFECTED"
    RESTORED = "RESTORED"


@dataclass(frozen=True, slots=True)
class UnitRevisionSpec:
    unit_id: UUID
    code: str
    name: str
    kind: OrganisationKind
    effective_from: datetime
    effective_until: datetime | None
    routing_enabled: bool
    minimum_managers: int
    minimum_analysts: int


@dataclass(frozen=True, slots=True)
class HierarchyEdgeSpec:
    parent_unit_id: UUID
    child_unit_id: UUID
    effective_from: datetime
    effective_until: datetime | None


@dataclass(frozen=True, slots=True)
class CandidateGroupSpec:
    unit_id: UUID
    purpose: CandidateGroupPurpose
    candidate_group: str


@dataclass(frozen=True, slots=True)
class WorkflowTemplateSpec:
    schema_id: str
    form_version: str
    notification_policy_version: str
    organisation_root_id: UUID
    route_depth: int
    core_fields: tuple[str, ...]
    service_categories: tuple[str, ...]
    product_types: tuple[str, ...]
    task_labels: Mapping[str, str]
    allowed_outcomes: Mapping[str, tuple[str, ...]]
    reminder_days: tuple[int, ...]
    artefact_types: tuple[str, ...]
    approved_link_domains: tuple[str, ...]
    workflow_definition_id: UUID

    def __post_init__(self) -> None:
        for field_name in (
            "core_fields",
            "service_categories",
            "product_types",
            "reminder_days",
            "artefact_types",
            "approved_link_domains",
        ):
            object.__setattr__(
                self, field_name, tuple(sorted(getattr(self, field_name)))
            )
        object.__setattr__(
            self, "task_labels", MappingProxyType(dict(self.task_labels))
        )
        object.__setattr__(
            self,
            "allowed_outcomes",
            MappingProxyType(
                {
                    key: tuple(sorted(values))
                    for key, values in self.allowed_outcomes.items()
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ConfigurationDraftSpec:
    units: tuple[UnitRevisionSpec, ...]
    edges: tuple[HierarchyEdgeSpec, ...]
    candidate_groups: tuple[CandidateGroupSpec, ...]
    workflow_template: WorkflowTemplateSpec


@dataclass(frozen=True, slots=True)
class ApprovedWorkflowSpec:
    id: UUID
    compatibility_key: str
    available: bool


@dataclass(frozen=True, slots=True)
class StaffingCount:
    managers: int = 0
    analysts: int = 0


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    severity: FindingSeverity
    code: str
    message: str
    path: str
    unit_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PreviewChange:
    type: PreviewChangeType
    unit_id: UUID
    code: str
    message: str
    effective_at: datetime
