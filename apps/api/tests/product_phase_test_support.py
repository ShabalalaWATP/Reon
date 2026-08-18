"""Synthetic records and ports for managed-product phase boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from mist_service.domain import Actor
from mist_service.models import ProductMode, RequestStatus, UserRole
from mist_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    ArtefactRecord,
    PackageRecord,
    PackageStatus,
    ProductRequestRecord,
    ProductStorageUsage,
    UploadIntentRecord,
)
from mist_service.schemas.products import (
    ArtefactView,
    ManagedArtefactCreate,
    PackageView,
)
from mist_service.services.product_content_phases import ProductContentPhases
from mist_service.services.product_managed_phases import ProductManagedPhases

CHECKSUM = "a" * 64
TOKEN = "synthetic-upload-token"


def records() -> tuple[
    Actor,
    PackageRecord,
    ProductRequestRecord,
    ArtefactRecord,
    UploadIntentRecord,
    PackageView,
]:
    actor_id, team_id, request_id, package_id, artefact_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    actor = Actor(
        actor_id,
        "synthetic-analyst",
        "Synthetic Analyst",
        UserRole.DELIVERY_SPECIALIST,
        "Synthetic Team",
        frozenset({team_id}),
    )
    package = PackageRecord(
        id=package_id,
        request_id=request_id,
        author_user_id=actor_id,
        status=PackageStatus.DRAFT,
        covering_note=None,
        package_checksum=None,
        version=1,
        package_version=1,
    )
    request = ProductRequestRecord(
        id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.IN_PROGRESS.value,
        product_mode=ProductMode.MANAGED.value,
        assigned_team="Synthetic Team",
        assigned_specialist_id=actor_id,
        version=3,
        assigned_team_id=team_id,
    )
    artefact = ArtefactRecord(
        artefact_id,
        package_id,
        ArtefactKind.MANAGED_FILE,
        ArtefactLifecycle.PENDING_UPLOAD,
        "synthetic.pdf",
        "application/pdf",
        10,
        CHECKSUM,
        f"quarantine/{package_id}/{artefact_id}",
        None,
    )
    intent = UploadIntentRecord(
        uuid4(),
        artefact_id,
        artefact.quarantine_key or "",
        10,
        "application/pdf",
        CHECKSUM,
        datetime.now(UTC) + timedelta(days=1),
        None,
        None,
    )
    view = PackageView(
        id=package_id,
        requestId=request_id,
        requestReference="SR-SYNTHETIC",
        requestTitle="Synthetic product request",
        requestStatus=RequestStatus.IN_PROGRESS,
        authorDisplayName=actor.display_name,
        packageVersion=1,
        status=PackageStatus.DRAFT,
        coveringNote=None,
        packageChecksum=None,
        version=1,
        artefacts=[
            ArtefactView(
                id=artefact_id,
                packageId=package_id,
                position=1,
                kind=ArtefactKind.MANAGED_FILE,
                lifecycle=ArtefactLifecycle.PENDING_UPLOAD,
                label="Synthetic attachment",
                filename=artefact.filename,
                mediaType=artefact.media_type,
                sizeBytes=artefact.size_bytes,
                sha256=artefact.checksum,
                version=1,
            )
        ],
        managerApprovedAt=None,
        managerApprovedBy=None,
        disseminatedAt=None,
        disseminatedBy=None,
        withdrawalReason=None,
    )
    return actor, package, request, artefact, intent, view


DATA = records()


def command(**updates: Any) -> ManagedArtefactCreate:
    values: dict[str, Any] = {
        "expectedVersion": 1,
        "label": "Synthetic attachment",
        "filename": "synthetic.pdf",
        "mediaType": "application/pdf",
        "sizeBytes": 10,
        "sha256": CHECKSUM,
        "idempotencyKey": uuid4(),
    }
    values.update(updates)
    return ManagedArtefactCreate.model_validate(values)


def repository(**updates: object) -> SimpleNamespace:
    _actor, package, request, artefact, intent, view = DATA
    values: dict[str, object] = {
        "package": AsyncMock(return_value=package),
        "active_actor": AsyncMock(return_value=True),
        "live_delivery_membership": AsyncMock(return_value=True),
        "request": AsyncMock(return_value=request),
        "managed_retry": AsyncMock(return_value=None),
        "storage_usage": AsyncMock(
            return_value=ProductStorageUsage(0, 0, 0, 0, 0, 0, 0, 0)
        ),
        "refresh_upload_grant": AsyncMock(return_value=intent),
        "create_managed": AsyncMock(return_value=(artefact, intent)),
        "view": AsyncMock(return_value=view),
        "upload_intent": AsyncMock(return_value=(artefact, intent)),
        "upload_token_hash": AsyncMock(
            return_value=ProductContentPhases._token_hash(TOKEN)
        ),
        "claim_intent_operation": AsyncMock(return_value=1),
        "require_intent_operation": AsyncMock(),
        "release_intent_operation": AsyncMock(return_value=True),
        "mark_uploaded": AsyncMock(),
        "record_scan": AsyncMock(return_value=artefact),
    }
    values.update(updates)
    return SimpleNamespace(**values)


def service(
    service_type: type[Any], repository_value: object, **options: object
) -> Any:
    repository_port = cast(Any, repository_value)
    if service_type is ProductManagedPhases:
        return service_type(repository_port, repository_port, **options)
    if service_type is ProductContentPhases:
        return service_type(
            repository_port,
            repository_port,
            repository_port,
            **options,
        )
    return service_type(repository_port, **options)
