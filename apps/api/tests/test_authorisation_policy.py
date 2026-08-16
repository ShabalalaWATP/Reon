"""Typed request-policy matrices and architecture boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from authorisation_test_support import actor, request
from mist_service.authorisation import PolicyDenial, RequestOperation
from mist_service.models import RequestStatus, UserRole
from mist_service.policies import decide_request_access

POOL_VERIFIED = {"pool_membership_verified": True}


@pytest.mark.parametrize("role", list(UserRole))
def test_only_customers_may_create_or_list_customer_requests(role: UserRole) -> None:
    current = actor(role)
    expected = role is UserRole.REQUESTER
    assert decide_request_access(current, RequestOperation.CREATE).allowed is expected
    assert decide_request_access(current, RequestOperation.LIST).allowed is expected


@pytest.mark.parametrize(
    ("operation"),
    [
        RequestOperation.CANCEL,
        RequestOperation.FEEDBACK,
        RequestOperation.DOWNLOAD_PRODUCT,
    ],
)
def test_customer_mutations_require_exact_ownership(
    operation: RequestOperation,
) -> None:
    owner = actor(UserRole.REQUESTER)
    item = request(owner)
    assert decide_request_access(owner, operation, item).allowed
    assert (
        decide_request_access(actor(UserRole.REQUESTER), operation, item).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_request_access(actor(UserRole.INTAKE_TRIAGE), operation, item).denial
        is PolicyDenial.ROLE
    )


def test_request_visibility_and_field_disclosure_are_independent_decisions() -> None:
    owner = actor(UserRole.REQUESTER)
    triage = actor(UserRole.INTAKE_TRIAGE)
    item = request(owner)

    assert decide_request_access(owner, RequestOperation.VIEW, item).allowed
    assert (
        decide_request_access(
            actor(UserRole.REQUESTER), RequestOperation.VIEW, item
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert decide_request_access(
        triage, RequestOperation.VIEW, item, **POOL_VERIFIED
    ).allowed
    assert (
        decide_request_access(
            actor(UserRole.SERVICE_COORDINATION),
            RequestOperation.VIEW,
            item,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_request_access(
            owner, RequestOperation.VIEW_UNRELEASED_PRODUCT, item
        ).denial
        is PolicyDenial.ROLE
    )
    assert decide_request_access(
        triage,
        RequestOperation.VIEW_UNRELEASED_PRODUCT,
        item,
        **POOL_VERIFIED,
    ).allowed
    assert decide_request_access(
        owner, RequestOperation.VIEW_CLARIFICATIONS, item
    ).allowed
    assert (
        decide_request_access(
            triage,
            RequestOperation.VIEW_CLARIFICATIONS,
            item,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.ROLE
    )
    assert (
        decide_request_access(owner, RequestOperation.VIEW, None).denial
        is PolicyDenial.OBJECT_SCOPE
    )


def test_team_visibility_requires_exact_membership_or_participation() -> None:
    owner = actor(UserRole.REQUESTER)
    team_id = uuid4()
    manager = actor(
        UserRole.DELIVERY_TEAM_LEAD,
        scope="OSG Team",
        units=frozenset({team_id}),
    )
    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="OSG Team")
    item = request(
        owner,
        status=RequestStatus.IN_PROGRESS,
        team="OSG Team",
        team_id=team_id,
        specialist_id=analyst.id,
        participants=frozenset({analyst.id}),
    )

    assert decide_request_access(manager, RequestOperation.VIEW, item).allowed
    assert decide_request_access(analyst, RequestOperation.VIEW, item).allowed
    assert (
        decide_request_access(
            actor(
                UserRole.DELIVERY_TEAM_LEAD,
                scope="Cedar Team",
                units=frozenset({uuid4()}),
            ),
            RequestOperation.VIEW,
            item,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_request_access(
            actor(UserRole.DELIVERY_SPECIALIST, scope="Cedar Team"),
            RequestOperation.VIEW,
            item,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )


def test_waiting_clarification_and_invalid_request_operation_fail_closed() -> None:
    owner = actor(UserRole.REQUESTER)
    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="OSG Team")
    waiting = request(
        owner,
        status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        team="OSG Team",
        specialist_id=analyst.id,
    )
    assert decide_request_access(analyst, RequestOperation.VIEW, waiting).allowed
    assert (
        decide_request_access(
            actor(UserRole.DELIVERY_SPECIALIST, scope="OSG Team"),
            RequestOperation.VIEW,
            waiting,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_request_access(
            actor(UserRole.REQUESTER),
            RequestOperation.VIEW_CLARIFICATIONS,
            waiting,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_request_access(
            owner,
            cast(RequestOperation, "UNKNOWN"),
            waiting,
        ).denial
        is PolicyDenial.ACTION
    )


def test_authorisation_domain_has_no_framework_or_adapter_imports() -> None:
    forbidden = ("fastapi", "sqlalchemy", "camunda_orchestration_sdk")
    for filename in (
        "authorisation.py",
        "policies.py",
        "request_access_policy.py",
        "work_access_policy.py",
    ):
        source = Path("src/mist_service", filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(module.startswith(forbidden) for module in modules)
