"""New-request configuration pinning contract."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.schemas.configuration import RequestConfigurationPinView


class ConfigurationPinningService:
    """Pin once in the request-creation transaction, never migrate in-flight work."""

    def __init__(self, repository: SqlAlchemyConfigurationPinRepository) -> None:
        self._repository = repository

    async def pin_new_request(
        self, request_id: UUID, *, now: datetime | None = None
    ) -> RequestConfigurationPinView:
        pin = await self._repository.pin_request(request_id, now=now)
        return RequestConfigurationPinView.model_validate(pin)
