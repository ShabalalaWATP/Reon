"""Record the current synthetic fixtures as immutable configuration version one."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationCandidateGroup,
    ConfigurationHierarchyEdge,
    ConfigurationRegistry,
    ConfigurationUnitRevision,
    ConfigurationVersion,
    ConfigurationWorkflowTemplate,
)
from istari_service.configuration_policy import (
    CORE_REQUEST_FIELDS,
    HUMAN_TASK_OUTCOMES,
    WORKFLOW_COMPATIBILITY_KEY,
    WORKFLOW_SCHEMA_DIGEST,
    WORKFLOW_SCHEMA_ID,
)
from istari_service.configuration_types import (
    CandidateGroupPurpose,
    ConfigurationStatus,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationKind, OrganisationUnit

CONFIGURATION_NAMESPACE = UUID("69f571ac-2f72-4a86-86b0-7784f3f064b1")
BUNDLED_BPMN_CHECKSUM = (
    "4fb7167bc69744a22efb1c19ff2f84d086a35e4ce10cd416d221dba0a09023c5"
)


def configuration_seed_id(name: str) -> UUID:
    return uuid5(CONFIGURATION_NAMESPACE, name)


async def seed_baseline_configuration(session: AsyncSession) -> bool:
    """Adopt legacy fixtures without claiming an unverified Camunda deployment."""

    registry = await session.get(ConfigurationRegistry, 1)
    if registry is None:
        registry = ConfigurationRegistry(id=1)
        session.add(registry)
        await session.flush()
    existing = await session.scalar(select(ConfigurationVersion.id).limit(1))
    if registry.active_version_id is not None or existing is not None:
        return False
    creator = await session.scalar(
        select(User)
        .where(
            User.role == UserRole.PLATFORM_ADMIN,
            User.is_active.is_(True),
        )
        .order_by(User.username)
    )
    units = list(
        await session.scalars(
            select(OrganisationUnit)
            .where(OrganisationUnit.is_configured.is_(True))
            .order_by(OrganisationUnit.sort_order, OrganisationUnit.code)
        )
    )
    roots = [unit for unit in units if unit.kind is OrganisationKind.ROOT]
    if creator is None or not units or len(roots) != 1:
        return False
    now = datetime.now(UTC)
    effective_from = min(_aware(unit.created_at) for unit in units)
    workflow = ApprovedWorkflowDefinition(
        id=configuration_seed_id("legacy-workflow-definition-v1"),
        process_id="service-request-v1",
        process_definition_key="legacy-unverified-service-request-v1",
        process_version=1,
        deployment_key="legacy-unverified-deployment-v1",
        compatibility_key=WORKFLOW_COMPATIBILITY_KEY,
        checksum=BUNDLED_BPMN_CHECKSUM,
        approved_by_user_id=creator.id,
        approved_at=now,
        is_available=False,
    )
    version = ConfigurationVersion(
        id=configuration_seed_id("legacy-configuration-v1"),
        sequence=1,
        label="Imported baseline configuration",
        status=ConfigurationStatus.ACTIVE,
        effective_from=effective_from,
        created_by_user_id=creator.id,
        based_on_version_id=None,
        reason=None,
        activated_at=now,
    )
    session.add_all([workflow, version])
    await session.flush()
    session.add_all(_unit_revisions(version.id, units, effective_from))
    session.add_all(_hierarchy_edges(version.id, units, effective_from))
    session.add_all(_candidate_groups(version.id, units))
    session.add(
        ConfigurationWorkflowTemplate(
            id=configuration_seed_id("legacy-workflow-template-v1"),
            configuration_version_id=version.id,
            schema_id=WORKFLOW_SCHEMA_ID,
            schema_digest=WORKFLOW_SCHEMA_DIGEST,
            form_version="legacy-v1",
            notification_policy_version="legacy-v1",
            organisation_root_id=roots[0].id,
            route_depth=3,
            core_fields=sorted(CORE_REQUEST_FIELDS),
            service_categories=["General service support"],
            product_types=["Analytical response"],
            task_labels={
                key: key.replace("_", " ").title() for key in HUMAN_TASK_OUTCOMES
            },
            allowed_outcomes={
                key: sorted(values) for key, values in HUMAN_TASK_OUTCOMES.items()
            },
            reminder_days=[7, 3, 1],
            artefact_types=["LEGACY_TEXT"],
            approved_link_domains=[],
            workflow_definition_id=workflow.id,
        )
    )
    registry.active_version_id = version.id
    registry.next_sequence = 2
    registry.version += 1
    await session.flush()
    return True


def _unit_revisions(
    version_id: UUID,
    units: list[OrganisationUnit],
    effective_from: datetime,
) -> list[ConfigurationUnitRevision]:
    return [
        ConfigurationUnitRevision(
            configuration_version_id=version_id,
            unit_id=unit.id,
            code=unit.code,
            name=unit.name,
            kind=unit.kind,
            effective_from=effective_from,
            effective_until=None,
            routing_enabled=True,
            minimum_managers=1 if unit.kind is OrganisationKind.TEAM else 0,
            minimum_analysts=1 if unit.kind is OrganisationKind.TEAM else 0,
        )
        for unit in units
    ]


def _hierarchy_edges(
    version_id: UUID,
    units: list[OrganisationUnit],
    effective_from: datetime,
) -> list[ConfigurationHierarchyEdge]:
    return [
        ConfigurationHierarchyEdge(
            configuration_version_id=version_id,
            parent_unit_id=unit.parent_id,
            child_unit_id=unit.id,
            effective_from=effective_from,
            effective_until=None,
        )
        for unit in units
        if unit.parent_id is not None
    ]


def _candidate_groups(
    version_id: UUID, units: list[OrganisationUnit]
) -> list[ConfigurationCandidateGroup]:
    records: list[ConfigurationCandidateGroup] = []
    for unit in units:
        mappings = (
            (CandidateGroupPurpose.ROUTING, unit.routing_candidate_group),
            (CandidateGroupPurpose.MANAGER, unit.manager_candidate_group),
            (CandidateGroupPurpose.ANALYST, unit.analyst_candidate_group),
        )
        records.extend(
            ConfigurationCandidateGroup(
                configuration_version_id=version_id,
                unit_id=unit.id,
                purpose=purpose,
                candidate_group=group,
            )
            for purpose, group in mappings
            if group is not None
        )
    return records


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
