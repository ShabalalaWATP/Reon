import type {
  AddMemberInput,
  EligibleRosterAnalystList,
  EndMembershipInput,
  TeamActivityList,
  TeamPeople,
  TeamMemberProfile,
  TeamWorkspaceList,
  TeamWorkspaceOverview,
  TransferMemberInput,
} from "./teamTypes";
import { apiRequest } from "./transport";

export const teamApi = {
  teamWorkspaces: () => apiRequest<TeamWorkspaceList>("/team-workspaces"),
  teamWorkspace: (teamId: string) =>
    apiRequest<TeamWorkspaceOverview>(
      `/team-workspaces/${encodeURIComponent(teamId)}`,
    ),
  teamPeople: (teamId: string) =>
    apiRequest<TeamPeople>(
      `/team-workspaces/${encodeURIComponent(teamId)}/people`,
    ),
  teamMemberProfile: (teamId: string, memberId: string) =>
    apiRequest<TeamMemberProfile>(
      `/team-workspaces/${encodeURIComponent(teamId)}/people/${encodeURIComponent(memberId)}/profile`,
    ),
  eligibleRosterAnalysts: (teamId: string, grantId: string) =>
    apiRequest<EligibleRosterAnalystList>(
      `/team-workspaces/${encodeURIComponent(teamId)}/eligible-analysts?grantId=${encodeURIComponent(grantId)}`,
    ),
  teamActivity: (teamId: string) =>
    apiRequest<TeamActivityList>(
      `/team-workspaces/${encodeURIComponent(teamId)}/activity`,
    ),
  addTeamMember: (teamId: string, input: AddMemberInput, csrfToken: string) =>
    apiRequest<TeamPeople>(
      `/team-workspaces/${encodeURIComponent(teamId)}/memberships`,
      { body: input, csrfToken, method: "POST" },
    ),
  transferTeamMember: (
    teamId: string,
    input: TransferMemberInput,
    csrfToken: string,
  ) => apiRequest<TeamPeople>(
    `/team-workspaces/${encodeURIComponent(teamId)}/transfers`,
    { body: input, csrfToken, method: "POST" },
  ),
  endTeamMembership: (
    teamId: string,
    membershipId: string,
    input: EndMembershipInput,
    csrfToken: string,
  ) => apiRequest<TeamPeople>(
    `/team-workspaces/${encodeURIComponent(teamId)}/memberships/${encodeURIComponent(membershipId)}/end`,
    { body: input, csrfToken, method: "POST" },
  ),
};
