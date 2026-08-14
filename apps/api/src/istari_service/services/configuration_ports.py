"""Narrow structural ports for configuration administration use cases."""

from __future__ import annotations

from collections.abc import Sequence, Set
from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.configuration_records import (
    ApprovedWorkflowRecord,
    ConfigurationApprovalRecord,
    ConfigurationBundleRecord,
    ConfigurationVersionRecord,
)
from istari_service.configuration_types import (
    ApprovalDecision,
    ConfigurationDraftSpec,
    StaffingCount,
    ValidationFinding,
)


class ConfigurationReadPort(Protocol):
    async def list_versions(self) -> Sequence[ConfigurationVersionRecord]: ...

    async def get_version(self, version_id: UUID) -> ConfigurationVersionRecord: ...

    async def bundle(self, version_id: UUID) -> ConfigurationBundleRecord: ...

    async def active_bundle(self) -> ConfigurationBundleRecord | None: ...

    async def approved_workflow(
        self, workflow_id: UUID
    ) -> ApprovedWorkflowRecord | None: ...

    async def list_workflows(self) -> Sequence[ApprovedWorkflowRecord]: ...


class ConfigurationWritePort(Protocol):
    async def create_draft(
        self,
        *,
        label: str,
        effective_from: datetime,
        created_by_user_id: UUID,
        based_on_version_id: UUID | None,
        specification: ConfigurationDraftSpec,
    ) -> ConfigurationVersionRecord: ...

    async def locked_version(
        self, version_id: UUID, expected_version: int
    ) -> ConfigurationVersionRecord: ...

    async def replace_components(
        self, version_id: UUID, specification: ConfigurationDraftSpec
    ) -> None: ...

    async def replace_findings(
        self, version_id: UUID, findings: list[ValidationFinding]
    ) -> None: ...

    async def create_approval(
        self,
        version: ConfigurationVersionRecord,
        *,
        actor_id: UUID,
        decision: ApprovalDecision,
        reason: str,
        snapshot_digest: str,
    ) -> ConfigurationApprovalRecord: ...

    async def activate(
        self,
        version: ConfigurationVersionRecord,
        approval: ConfigurationApprovalRecord,
        *,
        actor_id: UUID,
        reason: str,
        now: datetime,
    ) -> ConfigurationVersionRecord | None: ...

    async def refresh_version(
        self, version: ConfigurationVersionRecord
    ) -> ConfigurationVersionRecord: ...


class ConfigurationAuditPort(Protocol):
    async def append_configuration_audit(
        self,
        *,
        actor_id: UUID,
        action: str,
        version_id: UUID,
        changed_fields: Sequence[str],
        summary: str,
    ) -> None: ...


class ConfigurationStaffingPort(Protocol):
    async def staffing_counts(
        self, unit_ids: Set[UUID]
    ) -> dict[UUID, StaffingCount]: ...


class ConfigurationMaterialisationPort(Protocol):
    async def materialise_configuration(
        self, specification: ConfigurationDraftSpec, *, at: datetime
    ) -> None: ...


class ConfigurationCommandCorePort(Protocol):
    """Shared persistence capabilities used by every command use case."""

    async def bundle(self, version_id: UUID) -> ConfigurationBundleRecord: ...

    async def refresh_version(
        self, version: ConfigurationVersionRecord
    ) -> ConfigurationVersionRecord: ...

    async def append_configuration_audit(
        self,
        *,
        actor_id: UUID,
        action: str,
        version_id: UUID,
        changed_fields: Sequence[str],
        summary: str,
    ) -> None: ...


class ConfigurationDraftPort(ConfigurationCommandCorePort, Protocol):
    async def create_draft(
        self,
        *,
        label: str,
        effective_from: datetime,
        created_by_user_id: UUID,
        based_on_version_id: UUID | None,
        specification: ConfigurationDraftSpec,
    ) -> ConfigurationVersionRecord: ...

    async def locked_version(
        self, version_id: UUID, expected_version: int
    ) -> ConfigurationVersionRecord: ...

    async def replace_components(
        self, version_id: UUID, specification: ConfigurationDraftSpec
    ) -> None: ...

    async def get_version(self, version_id: UUID) -> ConfigurationVersionRecord: ...


class ConfigurationValidationPort(ConfigurationCommandCorePort, Protocol):
    async def locked_version(
        self, version_id: UUID, expected_version: int
    ) -> ConfigurationVersionRecord: ...

    async def replace_findings(
        self, version_id: UUID, findings: list[ValidationFinding]
    ) -> None: ...

    async def approved_workflow(
        self, workflow_id: UUID
    ) -> ApprovedWorkflowRecord | None: ...

    async def staffing_counts(
        self, unit_ids: Set[UUID]
    ) -> dict[UUID, StaffingCount]: ...


class ConfigurationReviewPort(ConfigurationCommandCorePort, Protocol):
    async def locked_version(
        self, version_id: UUID, expected_version: int
    ) -> ConfigurationVersionRecord: ...

    async def create_approval(
        self,
        version: ConfigurationVersionRecord,
        *,
        actor_id: UUID,
        decision: ApprovalDecision,
        reason: str,
        snapshot_digest: str,
    ) -> ConfigurationApprovalRecord: ...


class ConfigurationActivationPort(ConfigurationValidationPort, Protocol):
    async def activate(
        self,
        version: ConfigurationVersionRecord,
        approval: ConfigurationApprovalRecord,
        *,
        actor_id: UUID,
        reason: str,
        now: datetime,
    ) -> ConfigurationVersionRecord | None: ...

    async def materialise_configuration(
        self, specification: ConfigurationDraftSpec, *, at: datetime
    ) -> None: ...


class ConfigurationQueryPort(
    ConfigurationReadPort,
    ConfigurationStaffingPort,
    Protocol,
):
    """Capabilities needed by read-only configuration use cases."""


class ConfigurationApplicationPort(
    ConfigurationDraftPort,
    ConfigurationReviewPort,
    ConfigurationActivationPort,
    ConfigurationQueryPort,
    Protocol,
):
    """Composition-facing union of the focused configuration capabilities."""
