"""Merge direct membership and management grants into workspace authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from mist_service.management_models import ManagementAction
from mist_service.organisation_models import OrganisationKind, OrganisationUnit
from mist_service.team_models import WorkspacePosition


@dataclass(slots=True)
class WorkspaceAuthority:
    team: OrganisationUnit
    position: WorkspacePosition | None = None
    grant_id: UUID | None = None
    permissions: set[ManagementAction] = field(default_factory=set)
    descendant_permissions: set[ManagementAction] = field(default_factory=set)


def merge_authority(
    authority: dict[UUID, WorkspaceAuthority], row: Any
) -> dict[UUID, WorkspaceAuthority]:
    grant, action, team = row
    item = authority.setdefault(team.id, WorkspaceAuthority(team=team))
    if item.grant_id is None or action in {
        ManagementAction.ROSTER,
        ManagementAction.CALENDAR,
    }:
        item.grant_id = grant.id
    item.permissions.add(action)
    if grant.include_descendants:
        item.descendant_permissions.add(action)
    return authority


def workspace_views(authority: WorkspaceAuthority) -> list[str]:
    """Return only projections authorised by membership or named grants."""
    member = authority.position is not None
    views = {"OVERVIEW", "HANDOVER"}
    if member:
        views.update({"CALENDAR", "PEOPLE", "ACTIVITY"})
        if authority.team.kind is OrganisationKind.TEAM:
            views.update({"BOARD", "PLANNING"})
        else:
            views.add("QUEUE")
    if ManagementAction.ROSTER in authority.permissions:
        views.update({"PEOPLE", "ACTIVITY"})
    if ManagementAction.CALENDAR in authority.permissions:
        views.add("CALENDAR")
    if ManagementAction.BOARD in authority.permissions:
        views.add("BOARD")
    if authority.permissions.intersection(
        {ManagementAction.BOARD, ManagementAction.CAPACITY}
    ):
        views.add("PLANNING")
    if ManagementAction.STATISTICS in authority.permissions:
        views.add("STATISTICS")
    order = (
        "OVERVIEW",
        "QUEUE",
        "BOARD",
        "CALENDAR",
        "PEOPLE",
        "PLANNING",
        "STATISTICS",
        "HANDOVER",
        "ACTIVITY",
    )
    return [view for view in order if view in views]


def own_authority(row: Any) -> tuple[UUID, WorkspaceAuthority]:
    unit, position = row
    return unit.id, WorkspaceAuthority(team=unit, position=position)
