"""Shared synthetic builders for configuration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.config import Settings
from istari_service.configuration_events import ConfigurationLifecycleEvent
from istari_service.configuration_models import ApprovedWorkflowDefinition
from istari_service.configuration_policy import WORKFLOW_COMPATIBILITY_KEY
from istari_service.configuration_seed import seed_baseline_configuration
from istari_service.domain import Actor
from istari_service.models import ServiceRequest, User, UserRole
from istari_service.organisation_seed import seed_organisation_units
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.schemas.configuration import (
    ConfigurationDraftCreate,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
    WorkflowTemplateInput,
)
from istari_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)


@dataclass(slots=True)
class CollectingConfigurationPublisher:
    events: list[ConfigurationLifecycleEvent] = field(default_factory=list)

    async def publish(self, event: ConfigurationLifecycleEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True, slots=True)
class ConfigurationActors:
    creator: Actor
    reviewer: Actor
    requester_id: UUID
    workflow_id: UUID
    now: datetime


async def seed_configuration_context(
    session: AsyncSession,
    *,
    baseline_already_seeded: bool = False,
) -> ConfigurationActors:
    await seed_organisation_units(session)
    creator = _user("configuration.creator@example.test", UserRole.PLATFORM_ADMIN)
    reviewer = _user("configuration.reviewer@example.test", UserRole.PLATFORM_ADMIN)
    requester = _user("configuration.requester@example.test", UserRole.REQUESTER)
    session.add_all([creator, reviewer, requester])
    await session.flush()
    baseline_seeded = await seed_baseline_configuration(session)
    assert baseline_seeded or baseline_already_seeded
    now = datetime.now(UTC) + timedelta(minutes=1)
    workflow = ApprovedWorkflowDefinition(
        process_id="service-request-v2",
        process_definition_key="definition-v2",
        process_version=2,
        deployment_key="deployment-v2",
        compatibility_key=WORKFLOW_COMPATIBILITY_KEY,
        checksum="a" * 64,
        approved_by_user_id=reviewer.id,
        approved_at=now,
        is_available=True,
    )
    session.add(workflow)
    await session.flush()
    return ConfigurationActors(
        creator=_actor(creator),
        reviewer=_actor(reviewer),
        requester_id=requester.id,
        workflow_id=workflow.id,
        now=now,
    )


async def draft_from_active(
    session: AsyncSession,
    actors: ConfigurationActors,
    *,
    label: str = "Synthetic configuration change",
    effective_from: datetime | None = None,
) -> ConfigurationDraftCreate:
    repository = SqlAlchemyConfigurationRepository(session)
    active = await repository.active_bundle()
    assert active is not None
    effective_from = effective_from or actors.now
    units = [
        {
            "unitId": item.unit_id,
            "code": item.code,
            "name": item.name,
            "kind": item.kind,
            "effectiveFrom": effective_from,
            "effectiveUntil": None,
            "routingEnabled": item.routing_enabled,
            "minimumManagers": item.minimum_managers,
            "minimumAnalysts": item.minimum_analysts,
        }
        for item in active.units
    ]
    edges = [
        {
            "parentUnitId": item.parent_unit_id,
            "childUnitId": item.child_unit_id,
            "effectiveFrom": effective_from,
            "effectiveUntil": None,
        }
        for item in active.edges
    ]
    groups = [
        {
            "unitId": item.unit_id,
            "purpose": item.purpose,
            "candidateGroup": item.candidate_group,
        }
        for item in active.candidate_groups
    ]
    template = WorkflowTemplateInput.model_validate(
        active.workflow_template
    ).model_copy(update={"workflow_definition_id": actors.workflow_id})
    return ConfigurationDraftCreate(
        label=label,
        effective_from=effective_from,
        based_on_version_id=active.version.id,
        units=units,
        edges=edges,
        candidate_groups=groups,
        workflow_template=template,
    )


async def activate_second_configuration(
    session: AsyncSession,
    settings: Settings,
    actors: ConfigurationActors,
    *,
    effective_from: datetime | None = None,
    payload: ConfigurationDraftCreate | None = None,
) -> ConfigurationVersionDetail:
    lifecycle = ConfigurationLifecycleService(
        SqlAlchemyConfigurationRepository(session),
        settings,
        CollectingConfigurationPublisher(),
        clock=lambda: actors.now + timedelta(minutes=1),
    )
    payload = payload or await draft_from_active(
        session, actors, effective_from=effective_from
    )
    draft = await lifecycle.create(actors.creator, payload)
    validated = await lifecycle.validate(
        actors.creator,
        draft.id,
        ConfigurationVersionCommand(expected_version=draft.version),
    )
    submitted = await lifecycle.submit(
        actors.creator,
        draft.id,
        _reason(validated.version, "Submit for independent review."),
    )
    approved = await lifecycle.approve(
        actors.reviewer,
        draft.id,
        _reason(submitted.version, "Approve the exact configuration content."),
    )
    return await lifecycle.activate(
        actors.reviewer,
        draft.id,
        _reason(approved.version, "Activate only for newly created requests."),
    )


def make_request(requester_id: UUID) -> ServiceRequest:
    return ServiceRequest(
        reference=f"SR-{uuid4().hex[:10].upper()}",
        requester_id=requester_id,
        title="Synthetic configuration pin request",
        service_category="Research",
        description="A detailed synthetic request used only for configuration testing.",
        question_to_answer="What does the synthetic evidence show?",
        desired_outcome="A safe synthetic response.",
        background_context="Synthetic context only.",
        subject_area_or_location="Synthetic subject area",
        coverage_start=datetime.now(UTC).date(),
        coverage_end=datetime.now(UTC).date() + timedelta(days=1),
        customer_urgency="ROUTINE",
        supported_activity_or_decision="A fictional planning decision.",
        required_by=datetime.now(UTC).date() + timedelta(days=7),
        required_by_reason="Needed for a fictional planning exercise.",
        preferred_deliverable_type="Plain text",
        success_criteria="The fictional question is answered clearly.",
        constraints_or_caveats="No known constraints.",
        supporting_information="No supporting material is available.",
        sensitivity="STANDARD",
        handling_instructions="Retain synthetic content only.",
    )


def _user(username: str, role: UserRole) -> User:
    return User(
        username=username,
        email=username,
        display_name=username.split("@", maxsplit=1)[0].replace(".", " ").title(),
        password_hash="$argon2id$synthetic",
        role=role,
        scope="Platform" if role is UserRole.PLATFORM_ADMIN else "Area A",
        is_active=True,
    )


def _actor(user: User) -> Actor:
    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        scope=user.scope,
    )


def _reason(version: int, reason: str) -> ConfigurationReasonCommand:
    return ConfigurationReasonCommand(expected_version=version, reason=reason)
