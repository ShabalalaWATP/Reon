"""Release the database before opening a potentially slow product stream."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from mist_service.domain import Actor
from mist_service.product_types import DownloadStream
from mist_service.services.product_service import ProductService


class ProductDownloadService:
    def __init__(
        self,
        sessions: Callable[[], Any],
        service_factory: Callable[[Any], ProductService],
    ) -> None:
        self._sessions = sessions
        self._service_factory = service_factory

    async def download(
        self,
        actor: Actor,
        artefact_id: UUID,
        correlation_id: str | None,
    ) -> DownloadStream:
        service: ProductService
        async with self._sessions() as session, session.begin():
            service = self._service_factory(session)
            access = await service.authorise_download(
                actor, artefact_id, correlation_id
            )
        return await service.download_authorised(
            actor,
            access,
            correlation_id,
        )

    async def review(
        self,
        actor: Actor,
        artefact_id: UUID,
        correlation_id: str | None,
    ) -> DownloadStream:
        service: ProductService
        async with self._sessions() as session, session.begin():
            service = self._service_factory(session)
            access = await service.authorise_review(actor, artefact_id, correlation_id)
        return await service.review_authorised(actor, access, correlation_id)
