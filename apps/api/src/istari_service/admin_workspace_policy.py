"""Workspace-position rules for Administrator-managed accounts."""

from istari_service.errors import InvalidAdministrationChange
from istari_service.models import UserRole
from istari_service.schemas.admin import AdminUserCreate, AdminUserPatch
from istari_service.team_models import WorkspacePosition


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
    return payload.workspace_position or WorkspacePosition.MEMBER
