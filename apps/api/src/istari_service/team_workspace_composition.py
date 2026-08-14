"""Compose team-workspace use cases with persistence adapters."""

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.repositories.management_scope_authorisation import (
    SqlAlchemyExactManagementScopeAuthorisation,
)
from istari_service.repositories.team_member_profiles import (
    SqlAlchemyTeamMemberProfileRepository,
)
from istari_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.repositories.workspace_collaboration import (
    WorkspaceCollaborationRepository,
)
from istari_service.services.team_workspace_service import TeamWorkspaceService
from istari_service.services.workspace_collaboration_service import (
    WorkspaceCollaborationService,
)


def team_workspace_service(session: AsyncSession) -> TeamWorkspaceService:
    return TeamWorkspaceService(
        SqlAlchemyTeamWorkspaceRepository(session),
        SqlAlchemyTeamMembershipRepository(session),
        SqlAlchemyTeamMemberProfileRepository(session),
        SqlAlchemyExactManagementScopeAuthorisation(session),
    )


def workspace_collaboration_service(
    session: AsyncSession,
) -> WorkspaceCollaborationService:
    return WorkspaceCollaborationService(
        SqlAlchemyTeamWorkspaceRepository(session),
        WorkspaceCollaborationRepository(session),
        SqlAlchemyExactManagementScopeAuthorisation(session),
    )
