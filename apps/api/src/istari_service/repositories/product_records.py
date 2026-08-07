"""Mapping between managed-product persistence and application records."""

from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductPackage,
    ProductUploadIntent,
)
from istari_service.product_types import (
    ArtefactRecord,
    PackageRecord,
    UploadIntentRecord,
)


def package_record(package: ProductPackage) -> PackageRecord:
    return PackageRecord(
        id=package.id,
        request_id=package.request_id,
        author_user_id=package.author_user_id,
        status=package.status,
        package_checksum=package.package_checksum,
        version=package.version,
        package_version=package.package_version,
    )


def artefact_record(
    artefact: ProductArtefact, link: ExternalProductLink | None = None
) -> ArtefactRecord:
    return ArtefactRecord(
        id=artefact.id,
        package_id=artefact.package_id,
        kind=artefact.kind,
        lifecycle=artefact.lifecycle,
        filename=artefact.filename,
        media_type=artefact.media_type,
        size_bytes=artefact.size_bytes,
        checksum=artefact.checksum,
        quarantine_key=artefact.quarantine_key,
        released_key=artefact.released_key,
        destination_url=link.destination_url if link else None,
        destination_domain=link.normalised_domain if link else None,
        expires_at=link.expires_at if link else None,
    )


def intent_record(intent: ProductUploadIntent) -> UploadIntentRecord:
    return UploadIntentRecord(
        id=intent.id,
        artefact_id=intent.artefact_id,
        object_key=intent.object_key,
        expected_size_bytes=intent.expected_size_bytes,
        expected_media_type=intent.expected_media_type,
        expected_checksum=intent.expected_checksum,
        expires_at=intent.expires_at,
        uploaded_at=intent.uploaded_at,
        consumed_at=intent.consumed_at,
    )
