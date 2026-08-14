"""Customer product access for staff accounts using their Customer context."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from conftest import ApiHarness
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    ProductMode,
    RequestStatus,
    ServiceRequest,
)
from istari_service.product_models import (
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
)
from istari_service.product_types import ArtefactKind, ArtefactLifecycle, PackageStatus
from product_test_support import chunks, create_product_request, product_actors


async def _switch_to_customer(harness: ApiHarness) -> None:
    switched = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "CUSTOMER"},
        headers=harness.mutation_headers(),
    )
    assert switched.status_code == 200, switched.text
    harness.csrf_token = switched.json()["csrfToken"]


async def test_dual_context_customer_can_use_managed_and_legacy_products(
    api_harness: ApiHarness,
) -> None:
    _requester, _other, manager, analyst, qc = await product_actors(api_harness)
    managed_id = await create_product_request(api_harness, manager, analyst)
    legacy_id = await create_product_request(api_harness, manager, analyst)
    package_id, artefact_id = uuid4(), uuid4()
    content = b"%PDF-1.7\nSynthetic dual-context product"
    checksum = hashlib.sha256(content).hexdigest()
    now = datetime.now(UTC)

    transport = api_harness.client._transport
    app = transport.app  # type: ignore[attr-defined]
    storage = app.state.product_runtime.storage
    source_key = f"quarantine/{package_id}/dual-context-source"
    release_key = f"released/{package_id}/dual-context-release"
    await storage.write_quarantine(source_key, chunks(content), maximum_bytes=1024)
    await storage.promote(source_key, release_key)
    async with api_harness.sessions() as session, session.begin():
        managed = await session.get(ServiceRequest, managed_id)
        legacy = await session.get(ServiceRequest, legacy_id)
        assert managed is not None and legacy is not None
        managed.status = RequestStatus.COMPLETED
        legacy.status = RequestStatus.COMPLETED
        legacy.product_mode = ProductMode.LEGACY
        session.add(
            ProductPackage(
                id=package_id,
                request_id=managed_id,
                package_version=1,
                creation_key=uuid4(),
                author_user_id=analyst.id,
                status=PackageStatus.DISSEMINATED,
                covering_note="Synthetic note to the Customer.",
                package_checksum=checksum,
                disseminated_by_user_id=qc.id,
                disseminated_at=now,
                version=1,
            )
        )
        session.add(
            ProductArtefact(
                id=artefact_id,
                package_id=package_id,
                position=1,
                creation_key=uuid4(),
                kind=ArtefactKind.MANAGED_FILE,
                lifecycle=ArtefactLifecycle.RELEASED,
                label="Synthetic dual-context product",
                filename="dual-context.pdf",
                media_type="application/pdf",
                size_bytes=len(content),
                checksum=checksum,
                released_key=release_key,
                version=1,
            )
        )
        session.add(
            ProductDissemination(
                package_id=package_id,
                recipient_user_id=manager.id,
                disseminated_by_user_id=qc.id,
                idempotency_key=uuid4(),
                package_checksum=checksum,
            )
        )
        session.add(
            Deliverable(
                request_id=legacy_id,
                version=1,
                title="Synthetic legacy product",
                text="Synthetic legacy product text.",
                author_user_id=analyst.id,
                status=DeliverableStatus.RELEASED,
                released_by_user_id=qc.id,
                released_at=now,
            )
        )

    await api_harness.login(manager.username)
    assert (
        await api_harness.client.get(f"/api/v1/releases/requests/{managed_id}")
    ).status_code == 404
    await _switch_to_customer(api_harness)
    release = await api_harness.client.get(f"/api/v1/releases/requests/{managed_id}")
    assert release.status_code == 200, release.text
    downloaded = await api_harness.client.get(
        f"/api/v1/releases/artefacts/{artefact_id}/download"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content
    accepted = await api_harness.client.post(
        f"/api/v1/releases/requests/{managed_id}/accept",
        json={"idempotencyKey": str(uuid4())},
        headers=api_harness.mutation_headers(),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["acceptedAt"] is not None

    legacy_download = await api_harness.client.get(
        f"/api/v1/requests/{legacy_id}/product"
    )
    assert legacy_download.status_code == 200, legacy_download.text
    assert legacy_download.text == "Synthetic legacy product text."
