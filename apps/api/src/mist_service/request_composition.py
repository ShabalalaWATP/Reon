"""Composition boundary for Customer request and draft services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.config import Settings
from mist_service.models import ProductMode
from mist_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from mist_service.repositories.drafts import SqlAlchemyDraftRepository
from mist_service.repositories.requests import SqlAlchemyRequestRepository
from mist_service.services.draft_service import DraftService
from mist_service.services.request_service import RequestService


def build_draft_service(session: AsyncSession, settings: Settings) -> DraftService:
    return DraftService(
        SqlAlchemyDraftRepository(
            session,
            process_id=settings.camunda_process_id,
            default_product_mode=_default_product_mode(settings),
            configuration_pins=SqlAlchemyConfigurationPinRepository(session),
        )
    )


def build_request_service(session: AsyncSession, settings: Settings) -> RequestService:
    return RequestService(
        SqlAlchemyRequestRepository(
            session,
            process_id=settings.camunda_process_id,
            default_product_mode=_default_product_mode(settings),
            configuration_pins=SqlAlchemyConfigurationPinRepository(session),
        )
    )


def _default_product_mode(settings: Settings) -> ProductMode:
    return (
        ProductMode.MANAGED if settings.managed_products_enabled else ProductMode.LEGACY
    )
