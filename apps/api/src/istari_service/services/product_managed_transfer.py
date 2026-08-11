"""Managed artefact upload-grant transfer use case."""

from __future__ import annotations

from uuid import UUID

from istari_service.domain import Actor
from istari_service.schemas.products import ManagedArtefactCreate, ManagedArtefactIntent
from istari_service.services.product_transfer_context import ProductTransferContext


class ProductManagedTransfer:
    def __init__(self, context: ProductTransferContext) -> None:
        self._context = context

    async def add_managed(
        self,
        actor: Actor,
        package_id: UUID,
        command: ManagedArtefactCreate,
    ) -> ManagedArtefactIntent:
        async with self._context.sessions() as session, session.begin():
            plan = await self._context.managed_phases(session).prepare_managed(
                actor, package_id, command
            )
        grant = await self._context.runtime.storage.issue_upload(
            plan.object_key,
            expires_at=self._context.upload_expires_at(),
        )
        async with self._context.sessions() as session, session.begin():
            return await self._context.managed_phases(session).finalise_managed(
                actor, plan, grant
            )
