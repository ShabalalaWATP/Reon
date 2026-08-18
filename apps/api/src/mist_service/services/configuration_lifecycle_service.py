"""Compatibility facade over focused configuration command use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from mist_service.config import Settings
from mist_service.configuration_events import ConfigurationEventPublisher
from mist_service.domain import Actor
from mist_service.schemas.configuration import (
    ConfigurationDraftCreate,
    ConfigurationDraftReplace,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
)
from mist_service.services.configuration_activation_service import (
    ConfigurationActivationService,
)
from mist_service.services.configuration_draft_service import (
    ConfigurationDraftService,
)
from mist_service.services.configuration_ports import (
    ConfigurationActivationPort,
    ConfigurationDraftPort,
    ConfigurationReviewPort,
    ConfigurationValidationPort,
)
from mist_service.services.configuration_review_service import (
    ConfigurationReviewOperations,
)
from mist_service.services.configuration_validation_service import (
    ConfigurationValidationService,
)


class ConfigurationLifecycleService:
    """Retain one route contract while each component has one reason to change."""

    def __init__(
        self,
        drafts: ConfigurationDraftPort,
        validation: ConfigurationValidationPort,
        review: ConfigurationReviewPort,
        activation: ConfigurationActivationPort,
        settings: Settings,
        publisher: ConfigurationEventPublisher | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._draft = ConfigurationDraftService(
            drafts, settings, publisher, clock=clock
        )
        self._validation = ConfigurationValidationService(
            validation, settings, publisher, clock=clock
        )
        self._review = ConfigurationReviewOperations(
            review, settings, publisher, clock=clock
        )
        self._activation = ConfigurationActivationService(
            activation, settings, publisher, clock=clock
        )

    async def create(
        self, actor: Actor, payload: ConfigurationDraftCreate
    ) -> ConfigurationVersionDetail:
        return await self._draft.create(actor, payload)

    async def replace(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationDraftReplace,
    ) -> ConfigurationVersionDetail:
        return await self._draft.replace(actor, version_id, payload)

    async def validate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationVersionCommand,
    ) -> ConfigurationVersionDetail:
        return await self._validation.validate(actor, version_id, payload)

    async def submit(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._validation.submit(actor, version_id, payload)

    async def approve(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._review.approve(actor, version_id, payload)

    async def reject(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._review.reject(actor, version_id, payload)

    async def activate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._activation.activate(actor, version_id, payload)
