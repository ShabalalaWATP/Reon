"""Managed package mutations obey the authoritative request lifecycle."""

from uuid import uuid4

import pytest

from conftest import ApiHarness
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.product_errors import ProductConflict
from mist_service.schemas.products import ManagedArtefactCreate, PackageCreate
from product_test_support import (
    PDF_MEDIA,
    InMemoryPrivateObjectStorage,
    RecordingAudit,
    create_product_request,
    product_actors,
    product_service,
)


async def test_cancelled_request_rejects_saved_draft_mutation(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        service = product_service(
            session,
            InMemoryPrivateObjectStorage(),
            RecordingAudit(),
        )
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.CANCELLED
        with pytest.raises(ProductConflict):
            await service.add_managed(
                analyst,
                package.id,
                ManagedArtefactCreate(
                    expected_version=package.version,
                    label="Cancelled request product",
                    filename="cancelled.pdf",
                    media_type=PDF_MEDIA,
                    size_bytes=10,
                    sha256="a" * 64,
                    idempotency_key=uuid4(),
                ),
            )
