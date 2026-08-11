import type {
  AddMemberInput,
  EligibleRosterAnalystList,
  EndMembershipInput,
  TeamActivityList,
  TeamPeople,
  TeamWorkspaceList,
  TeamWorkspaceOverview,
  TransferMemberInput,
  WorkspaceRecordKind,
  WorkspaceRecordList,
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
  workspaceRecords: (unitId: string) =>
    apiRequest<WorkspaceRecordList>(`/team-workspaces/${encodeURIComponent(unitId)}/records`),
  createWorkspaceRecord: (unitId: string, input: { grantId: string; kind: WorkspaceRecordKind; title: string; body: string; url: string | null }, csrfToken: string) =>
    apiRequest<WorkspaceRecordList>(`/team-workspaces/${encodeURIComponent(unitId)}/records`, { body: input, csrfToken, method: "POST" }),
  resolveWorkspaceRecord: (unitId: string, recordId: string, input: { grantId: string; expectedVersion: number; resolution: string }, csrfToken: string) =>
    apiRequest<WorkspaceRecordList>(`/team-workspaces/${encodeURIComponent(unitId)}/records/${encodeURIComponent(recordId)}/resolve`, { body: input, csrfToken, method: "POST" }),
};
