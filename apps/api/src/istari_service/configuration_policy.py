"""Pure lifecycle and allow-list policy for configuration administration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from uuid import UUID

from istari_service.configuration_types import (
    CandidateGroupPurpose,
    ConfigurationStatus,
)
from istari_service.models import UserRole
from istari_service.organisation_models import OrganisationKind

WORKFLOW_SCHEMA_ID = "istari.workflow-template/v1"
WORKFLOW_COMPATIBILITY_KEY = "istari-human-route-v1"
ROUTE_DEPTH = 3

CORE_REQUEST_FIELDS = frozenset(
    {
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
    }
)

HUMAN_TASK_OUTCOMES: Mapping[str, frozenset[str]] = {
    "intake_review": frozenset({"request_information", "progress", "close"}),
    "requester_response": frozenset({"provide_information", "withdraw"}),
    "coordination_review": frozenset(
        {"send_to_allocation", "return_to_triage", "hold", "close"}
    ),
    "on_hold": frozenset({"resume", "close"}),
    "allocation_review": frozenset({"allocate", "return_to_coordination"}),
    "delivery_planning": frozenset({"assign", "return_for_reallocation"}),
    "delivery_work": frozenset({"submit"}),
    "lead_review": frozenset({"approve", "changes_required"}),
    "quality_review": frozenset({"approve", "changes_required"}),
    "release": frozenset({"release"}),
}

EXPECTED_GROUPS: Mapping[OrganisationKind, frozenset[CandidateGroupPurpose]] = {
    OrganisationKind.ROOT: frozenset({CandidateGroupPurpose.ROUTING}),
    OrganisationKind.COMMAND: frozenset({CandidateGroupPurpose.ROUTING}),
    OrganisationKind.OPS_GROUP: frozenset({CandidateGroupPurpose.ROUTING}),
    OrganisationKind.TEAM: frozenset(
        {CandidateGroupPurpose.MANAGER, CandidateGroupPurpose.ANALYST}
    ),
}

LEVEL_BY_KIND: Mapping[OrganisationKind, int] = {
    OrganisationKind.ROOT: 0,
    OrganisationKind.COMMAND: 1,
    OrganisationKind.OPS_GROUP: 2,
    OrganisationKind.TEAM: 3,
}

_SCHEMA_DOCUMENT = {
    "schemaId": WORKFLOW_SCHEMA_ID,
    "coreFields": sorted(CORE_REQUEST_FIELDS),
    "humanTasks": {
        task: sorted(outcomes) for task, outcomes in HUMAN_TASK_OUTCOMES.items()
    },
    "routeDepth": ROUTE_DEPTH,
    "artefactTypes": ["LEGACY_TEXT", "PDF", "DOCX", "PPTX"],
}
WORKFLOW_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(_SCHEMA_DOCUMENT, separators=(",", ":"), sort_keys=True).encode()
).hexdigest()


def can_administer_configuration(role: UserRole) -> bool:
    return role is UserRole.PLATFORM_ADMIN


def actor_is_independent(actor_id: UUID, creator_id: UUID) -> bool:
    return actor_id != creator_id


def may_replace_draft(status: ConfigurationStatus) -> bool:
    return status is ConfigurationStatus.DRAFT


def may_validate(status: ConfigurationStatus) -> bool:
    return status in {ConfigurationStatus.DRAFT, ConfigurationStatus.VALIDATED}


def may_submit(status: ConfigurationStatus) -> bool:
    return status is ConfigurationStatus.VALIDATED


def may_review(status: ConfigurationStatus) -> bool:
    return status is ConfigurationStatus.AWAITING_APPROVAL


def may_activate(status: ConfigurationStatus) -> bool:
    return status is ConfigurationStatus.AWAITING_APPROVAL
