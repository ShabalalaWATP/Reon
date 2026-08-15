"""Strict configuration draft and lifecycle command contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator, model_validator

from mist_service.configuration_types import (
    CandidateGroupPurpose,
    CandidateGroupSpec,
    ConfigurationDraftSpec,
    HierarchyEdgeSpec,
    UnitRevisionSpec,
    WorkflowTemplateSpec,
)
from mist_service.organisation_models import OrganisationKind
from mist_service.schemas.common import StrictApiModel
from mist_service.text_safety import normalise_display_name


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effective times must include a UTC offset")
    return value.astimezone(UTC)


def _unique(values: list[str], label: str) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} values must be unique")
    return values


class UnitRevisionInput(StrictApiModel):
    unit_id: UUID
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=2, max_length=120)
    kind: OrganisationKind
    effective_from: datetime
    effective_until: datetime | None = None
    routing_enabled: bool = True
    minimum_managers: int = Field(default=0, ge=0, le=100)
    minimum_analysts: int = Field(default=0, ge=0, le=500)

    @field_validator("name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return normalise_display_name(value)

    @field_validator("effective_from", "effective_until")
    @classmethod
    def aware_times(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self

    def to_spec(self) -> UnitRevisionSpec:
        return UnitRevisionSpec(
            unit_id=self.unit_id,
            code=self.code,
            name=self.name,
            kind=self.kind,
            effective_from=self.effective_from,
            effective_until=self.effective_until,
            routing_enabled=self.routing_enabled,
            minimum_managers=self.minimum_managers,
            minimum_analysts=self.minimum_analysts,
        )


class HierarchyEdgeInput(StrictApiModel):
    parent_unit_id: UUID
    child_unit_id: UUID
    effective_from: datetime
    effective_until: datetime | None = None

    @field_validator("effective_from", "effective_until")
    @classmethod
    def aware_times(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def valid_edge(self) -> Self:
        if self.parent_unit_id == self.child_unit_id:
            raise ValueError("an organisation unit cannot parent itself")
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self

    def to_spec(self) -> HierarchyEdgeSpec:
        return HierarchyEdgeSpec(
            parent_unit_id=self.parent_unit_id,
            child_unit_id=self.child_unit_id,
            effective_from=self.effective_from,
            effective_until=self.effective_until,
        )


class CandidateGroupInput(StrictApiModel):
    unit_id: UUID
    purpose: CandidateGroupPurpose
    candidate_group: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
    )

    def to_spec(self) -> CandidateGroupSpec:
        return CandidateGroupSpec(
            unit_id=self.unit_id,
            purpose=self.purpose,
            candidate_group=self.candidate_group,
        )


class WorkflowTemplateInput(StrictApiModel):
    schema_id: Literal["istari.workflow-template/v1"]
    form_version: str = Field(
        min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    notification_policy_version: str = Field(
        min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    organisation_root_id: UUID
    route_depth: Literal[3]
    core_fields: list[str] = Field(min_length=1, max_length=30)
    service_categories: list[str] = Field(min_length=1, max_length=50)
    product_types: list[str] = Field(min_length=1, max_length=20)
    task_labels: dict[str, str] = Field(min_length=10, max_length=10)
    allowed_outcomes: dict[str, list[str]] = Field(min_length=10, max_length=10)
    reminder_days: list[int] = Field(min_length=1, max_length=10)
    artefact_types: list[Literal["LEGACY_TEXT", "PDF", "DOCX", "PPTX"]] = Field(
        min_length=1, max_length=4
    )
    approved_link_domains: list[str] = Field(default_factory=list, max_length=50)
    workflow_definition_id: UUID

    @field_validator(
        "core_fields",
        "service_categories",
        "product_types",
        "artefact_types",
    )
    @classmethod
    def unique_strings(cls, value: list[str], info: ValidationInfo) -> list[str]:
        return _unique(value, info.field_name or "list")

    @field_validator("service_categories", "product_types")
    @classmethod
    def bounded_labels(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 120 for item in value):
            raise ValueError("configured labels must contain 1 to 120 characters")
        return [item.strip() for item in value]

    @field_validator("task_labels")
    @classmethod
    def bounded_task_labels(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not label.strip() or len(label) > 120 for label in value.values()):
            raise ValueError("task labels must contain 1 to 120 characters")
        return {key: label.strip() for key, label in value.items()}

    @field_validator("reminder_days")
    @classmethod
    def bounded_reminders(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day < 0 or day > 365 for day in value):
            raise ValueError("reminder days must be unique and between 0 and 365")
        return sorted(value)

    @field_validator("approved_link_domains")
    @classmethod
    def normalised_domains(cls, value: list[str]) -> list[str]:
        normalised = [domain.strip().lower().rstrip(".") for domain in value]
        return _unique(normalised, "approvedLinkDomains")

    def to_spec(self) -> WorkflowTemplateSpec:
        return WorkflowTemplateSpec(
            schema_id=self.schema_id,
            form_version=self.form_version,
            notification_policy_version=self.notification_policy_version,
            organisation_root_id=self.organisation_root_id,
            route_depth=self.route_depth,
            core_fields=tuple(self.core_fields),
            service_categories=tuple(self.service_categories),
            product_types=tuple(self.product_types),
            task_labels=self.task_labels,
            allowed_outcomes={
                key: tuple(values) for key, values in self.allowed_outcomes.items()
            },
            reminder_days=tuple(self.reminder_days),
            artefact_types=tuple(str(item) for item in self.artefact_types),
            approved_link_domains=tuple(self.approved_link_domains),
            workflow_definition_id=self.workflow_definition_id,
        )


class ConfigurationDraftCreate(StrictApiModel):
    label: str = Field(min_length=3, max_length=120)
    effective_from: datetime
    based_on_version_id: UUID | None = None
    units: list[UnitRevisionInput] = Field(min_length=4, max_length=1000)
    edges: list[HierarchyEdgeInput] = Field(min_length=3, max_length=2000)
    candidate_groups: list[CandidateGroupInput] = Field(min_length=4, max_length=3000)
    workflow_template: WorkflowTemplateInput

    @field_validator("effective_from")
    @classmethod
    def aware_effective_time(cls, value: datetime) -> datetime:
        return _utc(value)

    def to_spec(self) -> ConfigurationDraftSpec:
        return ConfigurationDraftSpec(
            units=tuple(item.to_spec() for item in self.units),
            edges=tuple(item.to_spec() for item in self.edges),
            candidate_groups=tuple(item.to_spec() for item in self.candidate_groups),
            workflow_template=self.workflow_template.to_spec(),
        )


class ConfigurationDraftReplace(ConfigurationDraftCreate):
    expected_version: int = Field(ge=1)


class ConfigurationVersionCommand(StrictApiModel):
    expected_version: int = Field(ge=1)


class ConfigurationReasonCommand(ConfigurationVersionCommand):
    reason: str = Field(min_length=10, max_length=2000)
