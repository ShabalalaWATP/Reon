"""Focused branch contracts for release security boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from mist_service.errors import InvalidAction
from mist_service.models import OutboxStatus, RequestStatus, UserRole
from mist_service.product_errors import ProductConflict
from mist_service.product_types import PackageStatus
from mist_service.repositories.product_requests import ProductRequestRepositoryMixin
from mist_service.repositories.product_workflow import (
    validate_product_workflow_effect,
)
from mist_service.repositories.work_claim_projection import project_claim
from mist_service.schemas.work import ChangesRequired, ReleaseDeliverable
from mist_service.services.product_service_support import ProductServiceSupport
from mist_service.workflow_attestation import (
    WorkflowAttestation,
    attest_workflow_availability,
)
from mist_service.workflow_start_validation import reject_invalid_start_identity


class ScalarSession:
    def __init__(self, *values: object | None) -> None:
        self.values = list(values)

    async def scalar(self, _statement: object) -> object | None:
        return self.values.pop(0)


async def test_managed_workflow_rejects_unfrozen_and_invalid_package_states() -> None:
    request = SimpleNamespace(id=uuid4(), requester_id=uuid4())
    actor_id = uuid4()
    unfrozen = SimpleNamespace(package_checksum=None)
    with pytest.raises(InvalidAction, match="immutable"):
        await validate_product_workflow_effect(  # type: ignore[arg-type]
            ScalarSession(unfrozen),
            request,
            actor_id,
            ChangesRequired(action="changes_required", reason="More detail required."),
        )

    valid = SimpleNamespace(
        package_checksum="a" * 64,
        status=PackageStatus.REVIEW_READY,
    )
    await validate_product_workflow_effect(  # type: ignore[arg-type]
        ScalarSession(valid),
        request,
        actor_id,
        ChangesRequired(action="changes_required", reason="More detail required."),
    )
    invalid = SimpleNamespace(
        package_checksum="a" * 64,
        status=PackageStatus.DISSEMINATED,
    )
    with pytest.raises(InvalidAction, match="not ready"):
        await validate_product_workflow_effect(  # type: ignore[arg-type]
            ScalarSession(invalid),
            request,
            actor_id,
            ChangesRequired(action="changes_required", reason="More detail required."),
        )


async def test_release_requires_exact_dissemination_evidence() -> None:
    request = SimpleNamespace(id=uuid4(), requester_id=uuid4())
    unreleased = SimpleNamespace(
        id=uuid4(),
        package_checksum="a" * 64,
        status=PackageStatus.REVIEW_READY,
    )
    with pytest.raises(InvalidAction, match="not ready"):
        await validate_product_workflow_effect(  # type: ignore[arg-type]
            ScalarSession(unreleased),
            request,
            uuid4(),
            ReleaseDeliverable(
                action="release",
                managed_product=True,
            ),
        )
    package = SimpleNamespace(
        id=uuid4(),
        package_checksum="a" * 64,
        status=PackageStatus.DISSEMINATED,
    )
    with pytest.raises(InvalidAction, match="not ready"):
        await validate_product_workflow_effect(  # type: ignore[arg-type]
            ScalarSession(package, None),
            request,
            uuid4(),
            ReleaseDeliverable(
                action="release",
                managed_product=True,
            ),
        )


class RequestLookup(ProductRequestRepositoryMixin):
    def __init__(self, session: object) -> None:
        self.session = session  # type: ignore[assignment]


class ExecuteSession:
    def __init__(self, row: object | None) -> None:
        self.row = row
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return SimpleNamespace(one_or_none=lambda: self.row)


async def test_product_request_lookup_rejects_missing_and_route_drift() -> None:
    request_id = uuid4()
    assert (
        await RequestLookup(ExecuteSession(None)).request(request_id, lock=False)
        is None
    )
    request = SimpleNamespace(
        id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.IN_PROGRESS,
        assigned_delivery_team="Team",
        assigned_delivery_team_id=uuid4(),
        assigned_specialist_id=uuid4(),
        version=1,
    )
    session = ExecuteSession((request, uuid4()))
    assert await RequestLookup(session).request(request_id, lock=True) is None
    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert sql.endswith("FOR UPDATE OF service_requests")


async def test_projection_and_start_validation_handle_missing_rows() -> None:
    session = SimpleNamespace(
        execute=_async_value(SimpleNamespace(rowcount=1)),
        get=_async_value(None),
    )
    work = SimpleNamespace(id=uuid4(), request=SimpleNamespace(id=uuid4()))
    actor = SimpleNamespace(id=uuid4())
    assert not await project_claim(session, work, actor)  # type: ignore[arg-type]

    outbox = SimpleNamespace(
        status=OutboxStatus.PENDING,
        lease_owner="lease",
        last_error=None,
        payload={},
    )
    request = SimpleNamespace(workflow_error=None)
    assert reject_invalid_start_identity(  # type: ignore[arg-type]
        None, outbox, request, None
    )
    assert outbox.status is OutboxStatus.FAILED


async def test_product_policy_and_attestation_reject_invalid_identity() -> None:
    team_id = uuid4()
    actor = SimpleNamespace(
        id=uuid4(),
        role=UserRole.DELIVERY_SPECIALIST,
        scope="Renamed Team",
        organisation_unit_ids=frozenset({team_id}),
    )
    request = SimpleNamespace(
        assigned_team_id=uuid4(),
        assigned_team="Renamed Team",
        assigned_specialist_id=actor.id,
    )
    assert not ProductServiceSupport._assigned_team(actor, request)  # type: ignore[arg-type]
    package = SimpleNamespace(
        status=PackageStatus.REVIEW_READY,
        author_user_id=actor.id,
        version=1,
        package_checksum="a" * 64,
    )
    with pytest.raises(ProductConflict):
        await object.__new__(ProductServiceSupport)._require_draft_author(  # type: ignore[arg-type]
            actor, package, request
        )
    with pytest.raises(ProductConflict):
        ProductServiceSupport._expect(package, 2, "a" * 64)  # type: ignore[arg-type]

    invalid = WorkflowAttestation(
        process_id="service-request-v1",
        process_version=0,
        process_definition_key="definition",
        deployment_key="deployment",
        compatibility_key="compatibility",
        checksum="a" * 64,
        operator_subject="ops:test",
    )
    with pytest.raises(ValueError, match="version"):
        await attest_workflow_availability(  # type: ignore[arg-type]
            ScalarSession(), invalid, apply=False, confirmation=None
        )


def _async_value(value: object):  # type: ignore[no-untyped-def]
    async def result(*_args: object, **_kwargs: object) -> object:
        return value

    return result
