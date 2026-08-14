"""Managed package, private upload and authenticated release routes."""

from __future__ import annotations

import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse

from istari_service.dependencies import (
    CurrentActor,
    DatabaseSession,
    DetachedCurrentActor,
    DetachedMutationSession,
    MutationActor,
    SessionFactoryDependency,
)
from istari_service.product_composition import (
    build_download_service,
    build_product_service,
    build_transfer_service,
)
from istari_service.product_dependencies import ProductRuntimeDependency
from istari_service.product_types import DownloadStream
from istari_service.schemas.products import (
    AcceptanceCommand,
    ApprovalCommand,
    CustomerReleaseView,
    DisseminationCommand,
    ExternalLinkCreate,
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    PackageCreate,
    PackageView,
    SubmitPackageCommand,
    UploadContentReceipt,
    VersionCommand,
    WithdrawalCommand,
)

router = APIRouter(prefix="/product-packages", tags=["product packages"])
release_router = APIRouter(prefix="/releases", tags=["product releases"])


def _download_response(
    result: DownloadStream, *, inline_safe_media: bool = False
) -> StreamingResponse:
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", result.filename).strip("._")
    fallback = fallback[:120] or "service-product"
    kind = (
        "inline"
        if inline_safe_media
        and result.media_type in {"application/pdf", "image/jpeg", "image/png"}
        else "attachment"
    )
    disposition = (
        f'{kind}; filename="{fallback}"; '
        f"filename*=UTF-8''{quote(result.filename, safe='')}"
    )
    return StreamingResponse(
        result.chunks,
        media_type=result.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": disposition,
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("", response_model=PackageView, status_code=status.HTTP_201_CREATED)
async def create_package(
    command: PackageCreate,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).create_package(
        actor, command
    )


@router.get("/by-request/{request_id}", response_model=PackageView | None)
async def get_package_for_request(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView | None:
    return await build_product_service(
        session, sessions, runtime
    ).get_package_for_request(actor, request_id)


@router.get("/{package_id}", response_model=PackageView)
async def get_package(
    package_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).get_package(
        actor, package_id
    )


@router.get("/artefacts/{artefact_id}/review")
async def review_artefact(
    artefact_id: UUID,
    request: Request,
    actor: DetachedCurrentActor,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> StreamingResponse:
    result = await build_download_service(sessions, runtime).review(
        actor, artefact_id, getattr(request.state, "correlation_id", None)
    )
    return _download_response(result, inline_safe_media=True)


@router.post("/{package_id}/managed-artefacts", response_model=ManagedArtefactIntent)
async def add_managed_artefact(
    package_id: UUID,
    command: ManagedArtefactCreate,
    mutation_session: DetachedMutationSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> ManagedArtefactIntent:
    return await build_transfer_service(
        sessions, runtime, mutation_session
    ).add_managed(mutation_session.actor, package_id, command)


@router.post("/{package_id}/external-links", response_model=PackageView)
async def add_external_link(
    package_id: UUID,
    command: ExternalLinkCreate,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).add_external(
        actor, package_id, command
    )


@router.put(
    "/{package_id}/uploads/{intent_id}/content",
    response_model=UploadContentReceipt,
)
async def upload_content(
    package_id: UUID,
    intent_id: UUID,
    request: Request,
    mutation_session: DetachedMutationSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
    expected_version: int = Query(alias="expectedVersion", ge=1),
    upload_token: str = Header(alias="X-Upload-Token", min_length=32, max_length=200),
) -> UploadContentReceipt:
    return await build_transfer_service(
        sessions, runtime, mutation_session
    ).upload_content(
        mutation_session.actor,
        package_id,
        intent_id,
        expected_version=expected_version,
        upload_token=upload_token,
        chunks=request.stream(),
    )


@router.post("/{package_id}/uploads/{intent_id}/complete", response_model=PackageView)
async def complete_upload(
    package_id: UUID,
    intent_id: UUID,
    command: VersionCommand,
    mutation_session: DetachedMutationSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_transfer_service(
        sessions, runtime, mutation_session
    ).complete_upload(mutation_session.actor, package_id, intent_id, command)


@router.post("/{package_id}/submit", response_model=PackageView)
async def submit_package(
    package_id: UUID,
    command: SubmitPackageCommand,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).submit(
        actor, package_id, command
    )


@router.post("/{package_id}/manager-approve", response_model=PackageView)
async def manager_approve(
    package_id: UUID,
    command: ApprovalCommand,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).manager_approve(
        actor, package_id, command
    )


@release_router.post("/{package_id}/disseminate", response_model=PackageView)
async def disseminate(
    package_id: UUID,
    command: DisseminationCommand,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).disseminate(
        actor, package_id, command
    )


@release_router.post("/{package_id}/withdraw", response_model=PackageView)
async def withdraw(
    package_id: UUID,
    command: WithdrawalCommand,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> PackageView:
    return await build_product_service(session, sessions, runtime).withdraw(
        actor, package_id, command
    )


@release_router.get("/requests/{request_id}", response_model=CustomerReleaseView | None)
async def customer_release(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> CustomerReleaseView | None:
    return await build_product_service(
        session, sessions, runtime
    ).find_customer_release(actor, request_id)


@release_router.post(
    "/requests/{request_id}/accept",
    response_model=CustomerReleaseView,
)
async def accept_customer_product(
    request_id: UUID,
    command: AcceptanceCommand,
    actor: MutationActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> CustomerReleaseView:
    return await build_product_service(session, sessions, runtime).accept_product(
        actor, request_id, command
    )


@release_router.get("/artefacts/{artefact_id}/download")
async def download(
    artefact_id: UUID,
    request: Request,
    actor: DetachedCurrentActor,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> StreamingResponse:
    result = await build_download_service(sessions, runtime).download(
        actor, artefact_id, getattr(request.state, "correlation_id", None)
    )
    return _download_response(result)


@release_router.get("/artefacts/{artefact_id}/open")
async def open_external(
    artefact_id: UUID,
    request: Request,
    actor: CurrentActor,
    session: DatabaseSession,
    sessions: SessionFactoryDependency,
    runtime: ProductRuntimeDependency,
) -> RedirectResponse:
    destination = await build_product_service(session, sessions, runtime).redirect(
        actor, artefact_id, getattr(request.state, "correlation_id", None)
    )
    return RedirectResponse(
        destination,
        status_code=status.HTTP_303_SEE_OTHER,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Cross-Origin-Opener-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )
