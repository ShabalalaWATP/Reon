"""Workspace-position rules for Administrator-managed accounts."""

from mist_service.errors import InvalidAdministrationChange
from mist_service.models import UserRole
from mist_service.schemas.admin import AdminUserCreate, AdminUserPatch
from mist_service.team_models import WorkspacePosition


def workspace_position_for(
    payload: AdminUserCreate | AdminUserPatch,
) -> WorkspacePosition | None:
    if not payload.organisation_unit_ids:
        return None
    if payload.role is UserRole.DELIVERY_TEAM_LEAD:
        if payload.workspace_position not in {None, WorkspacePosition.MANAGER}:
            raise InvalidAdministrationChange(
                "A Delivery Team Lead must be a workspace Manager."
            )
        return WorkspacePosition.MANAGER
    if payload.role is UserRole.DELIVERY_SPECIALIST:
        if payload.workspace_position not in {None, WorkspacePosition.MEMBER}:
            raise InvalidAdministrationChange(
                "A Delivery Specialist must be a workspace Member."
            )
        return WorkspacePosition.MEMBER
    if payload.role is UserRole.QUALITY_RELEASE:
        if payload.workspace_position not in {None, WorkspacePosition.MANAGER}:
            raise InvalidAdministrationChange(
                "A QC account must be a workspace Manager."
            )
        return WorkspacePosition.MANAGER
    return payload.workspace_position or WorkspacePosition.MEMBER
