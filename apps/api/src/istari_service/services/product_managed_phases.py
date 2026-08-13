"""Transactional preparation and projection of a managed artefact grant."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from istari_service.domain import Actor
from istari_service.product_errors import ProductConflict, ProductValidationFailed
from istari_service.product_security import validate_managed_metadata
from istari_service.product_types import ArtefactRecord, UploadGrant
from istari_service.schemas.products import (
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    UploadIntentView,
)
from istari_service.services.product_service_support import ProductServiceSupport
from istari_service.services.product_transfer_types import ManagedPreparation


class ProductManagedPhases(ProductServiceSupport):
    """Perform only database work; storage grants are passed in as values."""

    async def prepare_managed(
        self,
        actor: Actor,
        package_id: UUID,
        command: ManagedArtefactCreate,
    ) -> ManagedPreparation:
        self._require_managed_file_uploads()
        package, request = await self._authorised_package(actor, package_id, lock=False)
        self._require_draft_author(actor, package, request)
        filename, media_type = validate_managed_metadata(
            filename=command.filename,
            media_type=command.media_type,
            size_bytes=command.size_bytes,
            checksum=command.sha256,
        )
        if command.size_bytes > self._maximum_file_bytes:
            raise ProductValidationFailed(
                "The attachment exceeds the configured limit."
            )
        retry = await self._repository.managed_retry(
            package.id, command.idempotency_key
        )
        if retry is not None:
            artefact, intent = retry
            self._require_matching_metadata(artefact, filename, media_type, command)
            object_key = intent.object_key
        else:
            if package.version != command.expected_version:
                raise ProductConflict()
            await self._require_storage_capacity(package, command.size_bytes)
            object_id = uuid5(package.id, str(command.idempotency_key))
            object_key = f"quarantine/{package.id}/{object_id}"
            await self._repository.create_managed(
                package.id,
                label=command.label,
                filename=filename,
                media_type=media_type,
                size_bytes=command.size_bytes,
                checksum=command.sha256.lower(),
                creation_key=command.idempotency_key,
                intent_key=command.idempotency_key,
                object_key=object_key,
                token_hash=self._token_hash(f"pending:{object_id}"),
                expires_at=datetime.now(UTC) + self._upload_ttl,
            )
        return ManagedPreparation(
            package.id,
            command,
            filename,
            media_type,
            object_key,
        )

    async def finalise_managed(
        self,
        actor: Actor,
        plan: ManagedPreparation,
        grant: UploadGrant,
    ) -> ManagedArtefactIntent:
        package, request = await self._authorised_package(
            actor, plan.package_id, lock=True
        )
        self._require_draft_author(actor, package, request)
        command = plan.command
        retry = await self._repository.managed_retry(
            package.id, command.idempotency_key
        )
        if retry is not None:
            artefact, intent = retry
            self._require_matching_metadata(
                artefact, plan.filename, plan.media_type, command
            )
            if intent.object_key != grant.object_key:
                raise ProductConflict()
            intent = await self._repository.refresh_upload_grant(
                intent.id,
                token_hash=self._token_hash(grant.token),
                expires_at=grant.expires_at,
            )
        else:
            raise ProductConflict("The upload reservation is unavailable.")
        view = await self._repository.view(package.id)
        artefact_view = next(item for item in view.artefacts if item.id == artefact.id)
        return ManagedArtefactIntent(
            package=view,
            artefact=artefact_view,
            upload_intent=UploadIntentView(
                id=intent.id,
                object_key=intent.object_key,
                upload_token=grant.token,
                expires_at=intent.expires_at,
            ),
        )

    @staticmethod
    def _require_matching_metadata(
        artefact: ArtefactRecord,
        filename: str,
        media_type: str,
        command: ManagedArtefactCreate,
    ) -> None:
        if (
            artefact.filename != filename
            or artefact.media_type != media_type
            or artefact.size_bytes != command.size_bytes
            or artefact.checksum != command.sha256.lower()
        ):
            raise ProductConflict(
                "The idempotency key belongs to different upload metadata."
            )
