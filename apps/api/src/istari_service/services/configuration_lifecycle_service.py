"""Versioned configuration draft, review and activation use cases."""

from __future__ import annotations

from uuid import UUID

from istari_service.configuration_digest import configuration_digest
from istari_service.configuration_events import ConfigurationEventType
from istari_service.configuration_materialisation import (
    materialise_configuration_units,
)
from istari_service.configuration_models import ConfigurationVersion
from istari_service.configuration_policy import (
    may_activate,
    may_replace_draft,
    may_submit,
    may_validate,
)
from istari_service.configuration_types import (
    ApprovalDecision,
    ConfigurationStatus,
    FindingSeverity,
    ValidationFinding,
)
from istari_service.configuration_validation import validate_configuration
from istari_service.domain import Actor
from istari_service.errors import InvalidAdministrationChange
from istari_service.repositories.configuration_records import (
    ConfigurationBundle,
    stored_utc,
    workflow_specification,
)
from istari_service.repositories.configuration_staffing import load_staffing_counts
from istari_service.schemas.configuration import (
    ConfigurationDraftCreate,
    ConfigurationDraftReplace,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
)
from istari_service.services.configuration_review_service import (
    ConfigurationReviewOperations,
)


class ConfigurationLifecycleService(ConfigurationReviewOperations):
    async def create(
        self, actor: Actor, payload: ConfigurationDraftCreate
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        await self._validate_base(payload.based_on_version_id)
        version = ConfigurationVersion(
            sequence=await self._repository.next_sequence(),
            label=payload.label,
            status=ConfigurationStatus.DRAFT,
            effective_from=payload.effective_from,
            created_by_user_id=actor.id,
            based_on_version_id=payload.based_on_version_id,
            reason=None,
        )
        self._repository.session.add(version)
        await self._repository.session.flush()
        await self._repository.replace_components(version.id, payload.to_spec())
        await self._audit(
            actor,
            "CONFIGURATION_DRAFT_CREATED",
            version.id,
            ["label", "effectiveFrom", "basedOnVersionId", "snapshot"],
            "Configuration draft created.",
        )
        return await self._detail(version)

    async def replace(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationDraftReplace,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_replace_draft(version.status):
            raise InvalidAdministrationChange("Only Draft versions can be changed.")
        if payload.based_on_version_id == version.id:
            raise InvalidAdministrationChange(
                "A configuration cannot be based on itself."
            )
        await self._validate_base(payload.based_on_version_id)
        version.label = payload.label
        version.effective_from = payload.effective_from
        version.based_on_version_id = payload.based_on_version_id
        version.version += 1
        await self._repository.replace_components(version.id, payload.to_spec())
        await self._audit(
            actor,
            "CONFIGURATION_DRAFT_REPLACED",
            version.id,
            ["label", "effectiveFrom", "basedOnVersionId", "snapshot"],
            "Configuration draft snapshot replaced.",
        )
        return await self._detail(version)

    async def validate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationVersionCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_validate(version.status):
            raise InvalidAdministrationChange("This version cannot be validated.")
        bundle = await self._repository.bundle(version.id, version=version)
        findings = await self._validation_findings(bundle)
        await self._repository.replace_findings(version.id, findings)
        has_errors = any(item.severity is FindingSeverity.ERROR for item in findings)
        version.status = (
            ConfigurationStatus.DRAFT if has_errors else ConfigurationStatus.VALIDATED
        )
        version.validated_at = None if has_errors else self._clock()
        version.version += 1
        await self._audit(
            actor,
            "CONFIGURATION_VALIDATED",
            version.id,
            ["status", "findings", "validatedAt"],
            "Configuration validation completed.",
        )
        return await self._detail(version)

    async def submit(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_submit(version.status):
            raise InvalidAdministrationChange(
                "Only a Validated version can be submitted."
            )
        now = self._clock()
        version.status = ConfigurationStatus.AWAITING_APPROVAL
        version.reason = payload.reason
        version.submitted_at = now
        version.version += 1
        await self._audit(
            actor,
            "CONFIGURATION_SUBMITTED",
            version.id,
            ["status", "reason", "submittedAt"],
            "Configuration submitted for independent approval.",
        )
        await self._publish(ConfigurationEventType.AWAITING_REVIEW, version, actor, now)
        return await self._detail(version)

    async def activate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        bundle = await self._repository.bundle(version.id, version=version)
        self._require_activation_authority(actor, bundle)
        now = self._clock()
        if stored_utc(version.effective_from) > now:
            raise InvalidAdministrationChange(
                "The configured effective time must arrive before activation."
            )
        findings = await self._validation_findings(bundle)
        if any(item.severity is FindingSeverity.ERROR for item in findings):
            raise InvalidAdministrationChange(
                "Validate the current configuration and workflow deployment again."
            )
        await self._repository.replace_findings(version.id, findings)
        approval = bundle.approval
        if approval is None:
            raise InvalidAdministrationChange("Approval evidence is unavailable.")
        if approval.snapshot_digest != configuration_digest(bundle.specification()):
            raise InvalidAdministrationChange(
                "The approved configuration snapshot no longer matches review evidence."
            )
        superseded = await self._repository.activate(
            version,
            approval,
            actor_id=actor.id,
            reason=payload.reason,
            now=now,
        )
        await materialise_configuration_units(
            self._repository.session,
            bundle.specification(),
            at=now,
        )
        await self._audit(
            actor,
            "CONFIGURATION_ACTIVATED",
            version.id,
            ["status", "activatedAt", "activeVersion"],
            "Approved configuration activated for new requests.",
        )
        if superseded is not None:
            await self._audit(
                actor,
                "CONFIGURATION_SUPERSEDED",
                superseded.id,
                ["status"],
                "Earlier active configuration superseded.",
            )
        await self._publish(
            ConfigurationEventType.ACTIVATED,
            version,
            actor,
            now,
            superseded_id=superseded.id if superseded else None,
        )
        if superseded is not None:
            await self._publish(
                ConfigurationEventType.SUPERSEDED, superseded, actor, now
            )
        return await self._detail(version)

    def _require_activation_authority(
        self, actor: Actor, bundle: ConfigurationBundle
    ) -> None:
        version = bundle.version
        approval = bundle.approval
        if not may_activate(version.status) or approval is None:
            raise InvalidAdministrationChange(
                "This version is not approved for activation."
            )
        if approval.decision is not ApprovalDecision.APPROVED:
            raise InvalidAdministrationChange("A rejected version cannot be activated.")
        if actor.id == version.created_by_user_id:
            raise InvalidAdministrationChange(
                "The draft creator cannot activate this version."
            )
        if approval.actor_user_id == version.created_by_user_id:
            raise InvalidAdministrationChange("The approval is not independent.")
        if approval.reviewed_version + 1 != version.version:
            raise InvalidAdministrationChange(
                "The approval does not cover this version."
            )

    async def _validation_findings(
        self, bundle: ConfigurationBundle
    ) -> list[ValidationFinding]:
        specification = bundle.specification()
        workflow = await self._repository.approved_workflow(
            specification.workflow_template.workflow_definition_id
        )
        staffing = await load_staffing_counts(
            self._repository.session,
            {item.unit_id for item in specification.units},
        )
        return validate_configuration(
            specification,
            effective_from=stored_utc(bundle.version.effective_from),
            workflow=workflow_specification(workflow),
            staffing=staffing,
        )

    async def _validate_base(self, version_id: UUID | None) -> None:
        if version_id is None:
            return
        base = await self._repository.get_version(version_id)
        if base.status is ConfigurationStatus.DRAFT:
            raise InvalidAdministrationChange(
                "Create a draft from an immutable configuration version."
            )
