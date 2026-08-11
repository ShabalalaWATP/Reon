"""Focused product-download and security branch regressions."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api_helpers import current_item, submit_request
from conftest import ApiHarness
from istari_service.audit import AUDIT_KEY_INFO
from istari_service.config import Settings
from istari_service.domain import Actor, ProductDownload, RequestRecord
from istari_service.errors import ObjectNotFound
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    RequestStatus,
    ServiceRequest,
    UserRole,
)
from istari_service.policies import allowed_actions
from istari_service.repositories.event_store import (
    append_request_event,
    audit_key_for_session,
    verify_request_event_integrity,
)
from istari_service.repositories.requests import SqlAlchemyRequestRepository
from istari_service.response_security import SecurityHeadersMiddleware
from istari_service.services.request_service import RequestRepository, RequestService
from istari_service.team_models import TeamMembership


class ProductRepository:
    def __init__(self, product: ProductDownload | None) -> None:
        self.product = product
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_record_for_actor(
        self,
        request_id: UUID,
        actor: Actor,
        *,
        lock: bool = False,
    ) -> RequestRecord:
        del lock
        return RequestRecord(
            request_id,
            actor.id,
            RequestStatus.COMPLETED,
            None,
            None,
            1,
        )

    async def get_released_product(
        self, request_id: UUID, requester_id: UUID
    ) -> ProductDownload | None:
        self.calls.append((request_id, requester_id))
        return self.product


def requester() -> Actor:
    return Actor(
        uuid4(),
        "requester.synthetic@example.test",
        "Synthetic Requester",
        UserRole.REQUESTER,
        "Synthetic Area",
    )


@pytest.mark.asyncio
async def test_product_service_conceals_denials_and_sanitises_filename() -> None:
    request_id = uuid4()
    staff = Actor(
        uuid4(),
        "staff.synthetic@example.test",
        "Synthetic Staff",
        UserRole.INTAKE_TRIAGE,
        "CRIOC",
    )
    repository = ProductRepository(None)
    service = RequestService(cast(RequestRepository, repository))
    with pytest.raises(ObjectNotFound):
        await service.download_product(staff, request_id)
    assert repository.calls == []

    actor = requester()
    with pytest.raises(ObjectNotFound):
        await service.download_product(actor, request_id)
    repository.product = ProductDownload("../synthetic product??", "Synthetic text.")
    assert await service.download_product(actor, request_id) == (
        "synthetic_product-service-product.txt",
        "Synthetic text.",
    )
    repository.product = ProductDownload("../../", "Fallback reference.")
    assert await service.download_product(actor, request_id) == (
        f"{request_id}-service-product.txt",
        "Fallback reference.",
    )


@pytest.mark.asyncio
async def test_repository_requires_latest_exact_released_product(
    api_harness: ApiHarness,
) -> None:
    request_id = UUID(await submit_request(api_harness))
    requester_id = await api_harness.user_id("admin2")
    author_id = await api_harness.user_id("admin11")
    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyRequestRepository(
            session, process_id="service-request-v1"
        )
        assert await repository.get_released_product(uuid4(), requester_id) is None
        assert await repository.get_released_product(request_id, requester_id) is None
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.COMPLETED
        assert await repository.get_released_product(request_id, requester_id) is None

        deliverable = Deliverable(
            request_id=request_id,
            version=1,
            title="Synthetic product",
            text="Synthetic released product text.",
            author_user_id=author_id,
        )
        session.add(deliverable)
        assert await repository.get_released_product(request_id, requester_id) is None
        deliverable.status = DeliverableStatus.RELEASED
        assert await repository.get_released_product(request_id, requester_id) is None
        deliverable.released_at = datetime.now(UTC)
        product = await repository.get_released_product(request_id, requester_id)
        assert product is not None
        assert product.text == "Synthetic released product text."

        session.add(
            Deliverable(
                request_id=request_id,
                version=2,
                title="New unreleased revision",
                text="This later revision must conceal the earlier release.",
                author_user_id=author_id,
            )
        )
        assert await repository.get_released_product(request_id, requester_id) is None


@pytest.mark.asyncio
async def test_staff_detail_is_concealed_after_route_membership_revocation(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[UserRole, bool]] = []
    original = SqlAlchemyRequestRepository.get_record_for_actor

    async def tracked_authorisation(
        repository: SqlAlchemyRequestRepository,
        requested_id: UUID,
        actor: Actor,
        *,
        lock: bool = False,
    ) -> RequestRecord | None:
        calls.append((actor.role, lock))
        return await original(repository, requested_id, actor, lock=lock)

    monkeypatch.setattr(
        SqlAlchemyRequestRepository,
        "get_record_for_actor",
        tracked_authorisation,
    )
    request_id = await submit_request(api_harness)
    login = await api_harness.login("admin4")
    assert login["user"]["role"] == "INTAKE_TRIAGE"
    current_session = await api_harness.client.get("/api/v1/auth/me")
    assert current_session.json()["user"]["role"] == "INTAKE_TRIAGE"
    api_harness.csrf_token = current_session.json()["csrfToken"]
    await current_item(api_harness)
    visible = await api_harness.client.get(f"/api/v1/requests/{request_id}")
    assert visible.status_code == 200
    assert calls == [(UserRole.INTAKE_TRIAGE, True)]

    user_id = await api_harness.user_id("admin4")
    unit_id = await api_harness.unit_id("CRIOC")
    async with api_harness.sessions() as session, session.begin():
        membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.team_id == unit_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert membership is not None
        await session.delete(membership)

    concealed = await api_harness.client.get(f"/api/v1/requests/{request_id}")
    assert concealed.status_code == 404
    assert calls[-1] == (UserRole.INTAKE_TRIAGE, True)


class EmptyScalars:
    def all(self) -> list[Any]:
        return []


class AuditSession:
    def __init__(self, request: SimpleNamespace | None, key: object = b"a" * 32):
        self.request = request
        self.info = {AUDIT_KEY_INFO: key}

    async def get(self, model: object, request_id: UUID) -> SimpleNamespace | None:
        del model, request_id
        return self.request

    async def scalars(self, statement: object) -> EmptyScalars:
        del statement
        return EmptyScalars()


def audit_request(
    *, count: int, head: str | None = None, anchor: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        audit_event_count=count,
        audit_head_hash=head,
        audit_anchor_mac=anchor,
    )


@pytest.mark.asyncio
async def test_audit_anchor_rejects_invalid_empty_and_positive_states() -> None:
    for invalid_key in (None, "a" * 32, b"short"):
        session = AuditSession(None, invalid_key)
        with pytest.raises(RuntimeError, match="valid audit HMAC key"):
            audit_key_for_session(cast(AsyncSession, session))

    clean = AuditSession(audit_request(count=0))
    assert await verify_request_event_integrity(cast(AsyncSession, clean), uuid4())
    dirty = AuditSession(audit_request(count=0, head="f" * 64))
    assert not await verify_request_event_integrity(cast(AsyncSession, dirty), uuid4())
    missing_head = AuditSession(audit_request(count=1))
    assert not await verify_request_event_integrity(
        cast(AsyncSession, missing_head), uuid4()
    )
    missing_anchor = AuditSession(audit_request(count=1, head="f" * 64))
    assert not await verify_request_event_integrity(
        cast(AsyncSession, missing_anchor), uuid4()
    )
    invalid_anchor = AuditSession(
        audit_request(count=1, head="f" * 64, anchor="0" * 64)
    )
    assert not await verify_request_event_integrity(
        cast(AsyncSession, invalid_anchor), uuid4()
    )


@pytest.mark.asyncio
async def test_append_event_conceals_missing_anchor(api_harness: ApiHarness) -> None:
    async with api_harness.sessions() as session, session.begin():
        with pytest.raises(LookupError, match="audit anchor is unavailable"):
            await append_request_event(
                session,
                request_id=uuid4(),
                actor_id=None,
                event_type="synthetic",
                message="Synthetic event.",
                prior_status=None,
                next_status=None,
            )


@pytest.mark.asyncio
async def test_security_headers_middleware_passes_non_http_scope_through() -> None:
    seen: list[str] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del receive, send
        seen.append(scope["type"])

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        del message

    middleware = SecurityHeadersMiddleware(cast(ASGIApp, app))
    await middleware(cast(Scope, {"type": "lifespan"}), receive, send)
    assert seen == ["lifespan"]


def test_small_configuration_and_policy_branches() -> None:
    assert Settings.parse_allowed_hosts(" Example.TEST, ,API.EXAMPLE.TEST ") == {
        "example.test",
        "api.example.test",
    }
    settings = Settings(audit_hmac_key="a" * 32)
    assert settings.audit_hmac_key_bytes == b"a" * 32

    actor = requester()
    request = RequestRecord(
        uuid4(), actor.id, RequestStatus.ROUTING_PENDING, None, None, 1
    )
    assert allowed_actions(actor, request) == ()
