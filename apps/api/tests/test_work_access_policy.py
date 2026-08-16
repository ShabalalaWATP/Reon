"""Typed work-access, completion and shared-pool scope policy matrices."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from authorisation_test_support import actor, request, work
from mist_service.authorisation import (
    PolicyDenial,
    RequestOperation,
    WorkOperation,
)
from mist_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from mist_service.policies import (
    POOL_SCOPED_ROLES,
    ROLE_BY_STAGE,
    can_access_work,
    decide_request_access,
    decide_work_access,
    decide_work_completion,
    is_object_scoped,
)

POOL_VERIFIED = {"pool_membership_verified": True}


def test_shared_routing_work_requires_role_stage_scope_and_assignment() -> None:
    owner = actor(UserRole.REQUESTER)
    triage = actor(UserRole.INTAKE_TRIAGE)
    open_work = work(request(owner))

    assert decide_work_access(
        triage, open_work, WorkOperation.VIEW, **POOL_VERIFIED
    ).allowed
    assert decide_work_access(
        triage, open_work, WorkOperation.CLAIM, **POOL_VERIFIED
    ).allowed
    assert decide_work_access(
        triage,
        open_work,
        WorkOperation.VIEW_ROUTING_OPTIONS,
        **POOL_VERIFIED,
    ).allowed
    assert (
        decide_work_access(
            actor(UserRole.SERVICE_COORDINATION),
            open_work,
            WorkOperation.VIEW,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )
    assert (
        decide_work_access(
            triage,
            open_work,
            WorkOperation.LIST_ELIGIBLE_SPECIALISTS,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.ROLE
    )
    assert (
        decide_work_access(
            triage,
            open_work,
            cast(WorkOperation, "UNKNOWN"),
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.ACTION
    )

    claimed = replace(
        open_work,
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=triage.id,
    )
    assert decide_work_access(
        triage, claimed, WorkOperation.COMPLETE, **POOL_VERIFIED
    ).allowed
    assert (
        decide_work_access(
            actor(UserRole.INTAKE_TRIAGE),
            claimed,
            WorkOperation.VIEW,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.ASSIGNMENT
    )
    assert (
        decide_work_access(
            triage,
            replace(claimed, completed_at=datetime.now(UTC)),
            WorkOperation.VIEW,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.WORK_STATE
    )


def test_delivery_work_separates_manager_selection_and_analyst_completion() -> None:
    owner = actor(UserRole.REQUESTER)
    team_id = uuid4()
    manager = actor(
        UserRole.DELIVERY_TEAM_LEAD,
        scope="OSG Team",
        units=frozenset({team_id}),
    )
    planning = work(
        request(
            owner,
            status=RequestStatus.DELIVERY_PLANNING,
            team="OSG Team",
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

    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="OSG Team")
    production = work(
        request(
            owner,
            status=RequestStatus.IN_PROGRESS,
            team="OSG Team",
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
    assert decide_work_completion(
        triage, item, "progress", triage.id, **POOL_VERIFIED
    ).allowed
    assert (
        decide_work_completion(
            triage, item, "release", triage.id, **POOL_VERIFIED
        ).denial
        is PolicyDenial.ACTION
    )
    assert (
        decide_work_completion(
            triage, item, "progress", uuid4(), **POOL_VERIFIED
        ).denial
        is PolicyDenial.ASSIGNMENT
    )
    assert (
        decide_work_completion(
            actor(UserRole.SERVICE_COORDINATION),
            item,
            "progress",
            triage.id,
            **POOL_VERIFIED,
        ).denial
        is PolicyDenial.OBJECT_SCOPE
    )


@pytest.mark.parametrize("role", sorted(POOL_SCOPED_ROLES, key=lambda item: item.value))
def test_pool_roles_are_denied_without_membership_evidence(role: UserRole) -> None:
    """A caller that never checked unit membership must not be granted access.

    The shared-pool roles are scoped by live route or QC membership, which only
    the persistence boundary evaluates. A caller that omits that evidence has to
    fail closed, so that a future route reusing the policy alone cannot read or
    act on a request belonging to another organisational unit.
    """

    owner = actor(UserRole.REQUESTER)
    pooled = actor(role)
    stage = next(status for status, mapped in ROLE_BY_STAGE.items() if mapped is role)
    item = request(owner, status=stage)

    assert not is_object_scoped(pooled, item)
    assert not can_access_work(pooled, item)
    assert not decide_request_access(pooled, RequestOperation.VIEW, item).allowed
    assert is_object_scoped(pooled, item, **POOL_VERIFIED)
    assert can_access_work(pooled, item, **POOL_VERIFIED)
