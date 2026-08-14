"""Typed request/work policy matrices and architecture boundary tests."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from authorisation_test_support import actor, request, work
from istari_service.authorisation import (
    PolicyDenial,
    RequestOperation,
    WorkOperation,
)
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.policies import (
    decide_request_access,
    decide_work_access,
    decide_work_completion,
)


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
    assert decide_request_access(triage, RequestOperation.VIEW, item).allowed
    assert (
        decide_request_access(
            actor(UserRole.SERVICE_COORDINATION), RequestOperation.VIEW, item
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
        triage, RequestOperation.VIEW_UNRELEASED_PRODUCT, item
    ).allowed
    assert decide_request_access(
        owner, RequestOperation.VIEW_CLARIFICATIONS, item
    ).allowed
    assert (
        decide_request_access(triage, RequestOperation.VIEW_CLARIFICATIONS, item).denial
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
        scope="SSG Team",
        units=frozenset({team_id}),
    )
    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    item = request(
        owner,
        status=RequestStatus.IN_PROGRESS,
        team="SSG Team",
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
    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    waiting = request(
        owner,
        status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        team="SSG Team",
        specialist_id=analyst.id,
    )
    assert decide_request_access(analyst, RequestOperation.VIEW, waiting).allowed
    assert (
        decide_request_access(
            actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team"),
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


def test_shared_routing_work_requires_role_stage_scope_and_assignment() -> None:
    owner = actor(UserRole.REQUESTER)
    triage = actor(UserRole.INTAKE_TRIAGE)
    open_work = work(request(owner))

    assert decide_work_access(triage, open_work, WorkOperation.VIEW).allowed
    assert decide_work_access(triage, open_work, WorkOperation.CLAIM).allowed
    assert decide_work_access(
        triage, open_work, WorkOperation.VIEW_ROUTING_OPTIONS
    ).allowed
    assert (
        decide_work_access(
            actor(UserRole.SERVICE_COORDINATION), open_work, WorkOperation.VIEW
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_work_access(
            triage, open_work, WorkOperation.LIST_ELIGIBLE_SPECIALISTS
        ).denial
        is PolicyDenial.ROLE
    )
    assert (
        decide_work_access(triage, open_work, cast(WorkOperation, "UNKNOWN")).denial
        is PolicyDenial.ACTION
    )

    claimed = replace(
        open_work,
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=triage.id,
    )
    assert decide_work_access(triage, claimed, WorkOperation.COMPLETE).allowed
    assert (
        decide_work_access(
            actor(UserRole.INTAKE_TRIAGE), claimed, WorkOperation.VIEW
        ).denial
        is PolicyDenial.ASSIGNMENT
    )
    assert (
        decide_work_access(
            triage, replace(claimed, completed_at=datetime.now(UTC)), WorkOperation.VIEW
        ).denial
        is PolicyDenial.WORK_STATE
    )


def test_delivery_work_separates_manager_selection_and_analyst_completion() -> None:
    owner = actor(UserRole.REQUESTER)
    team_id = uuid4()
    manager = actor(
        UserRole.DELIVERY_TEAM_LEAD,
        scope="SSG Team",
        units=frozenset({team_id}),
    )
    planning = work(
        request(
            owner,
            status=RequestStatus.DELIVERY_PLANNING,
            team="SSG Team",
            team_id=team_id,
        )
    )
    assert decide_work_access(
        manager, planning, WorkOperation.LIST_ELIGIBLE_SPECIALISTS
    ).allowed
    assert (
        decide_work_access(manager, planning, WorkOperation.VIEW_ROUTING_OPTIONS).denial
        is PolicyDenial.STAGE
    )
    lead_review = work(
        replace(planning.request, status=RequestStatus.LEAD_REVIEW),
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=manager.id,
    )
    assert (
        decide_work_access(
            manager, lead_review, WorkOperation.LIST_ELIGIBLE_SPECIALISTS
        ).denial
        is PolicyDenial.STAGE
    )
    missing_team = replace(
        planning,
        request=replace(planning.request, assigned_delivery_team=None),
    )
    assert (
        decide_work_access(
            manager, missing_team, WorkOperation.LIST_ELIGIBLE_SPECIALISTS
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )

    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    production = work(
        request(
            owner,
            status=RequestStatus.IN_PROGRESS,
            team="SSG Team",
            team_id=team_id,
            specialist_id=analyst.id,
        ),
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=analyst.id,
    )
    assert decide_work_access(analyst, production, WorkOperation.COMPLETE).allowed
    assert (
        decide_work_access(analyst, production, WorkOperation.CLAIM).denial
        is PolicyDenial.ROLE
    )


def test_completion_decision_preserves_action_and_assignment_distinctions() -> None:
    owner = actor(UserRole.REQUESTER)
    triage = actor(UserRole.INTAKE_TRIAGE)
    item = request(owner)
    assert decide_work_completion(triage, item, "progress", triage.id).allowed
    assert (
        decide_work_completion(triage, item, "release", triage.id).denial
        is PolicyDenial.ACTION
    )
    assert (
        decide_work_completion(triage, item, "progress", uuid4()).denial
        is PolicyDenial.ASSIGNMENT
    )
    assert (
        decide_work_completion(
            actor(UserRole.SERVICE_COORDINATION), item, "progress", triage.id
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )


def test_authorisation_domain_has_no_framework_or_adapter_imports() -> None:
    forbidden = ("fastapi", "sqlalchemy", "camunda_orchestration_sdk")
    for filename in (
        "authorisation.py",
        "policies.py",
        "request_access_policy.py",
        "work_access_policy.py",
    ):
        source = Path("src/istari_service", filename).read_text(encoding="utf-8")
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
