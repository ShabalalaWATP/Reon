"""Merge direct membership and management grants into workspace authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from mist_service.management_models import ManagementAction
from mist_service.organisation_models import OrganisationUnit
from mist_service.team_models import WorkspacePosition


@dataclass(slots=True)
class WorkspaceAuthority:
    team: OrganisationUnit
    position: WorkspacePosition | None = None
    grant_id: UUID | None = None
    permissions: set[ManagementAction] = field(default_factory=set)


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
    return authority


def own_authority(row: Any) -> tuple[UUID, WorkspaceAuthority]:
    unit, position = row
    return unit.id, WorkspaceAuthority(team=unit, position=position)
