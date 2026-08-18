import type { Session } from "../lib/api/types";
import type { TeamWorkspaceAccess } from "../lib/api/teamTypes";
import { requesterSession } from "./fixtures";

export const managerSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-ssg",
    username: "admin8",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "SSG Team",
  },
};

export const analystSession: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "analyst-ssg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
  },
};

export function createTeamWorkspaceAccess(
  overrides: Partial<TeamWorkspaceAccess> = {},
): TeamWorkspaceAccess {
  return {
    teamId: "team-ssg",
    teamCode: "SSG_TEAM",
    teamName: "SSG Team",
    unitKind: "TEAM",
    workspacePosition: "MANAGER",
    grantId: "grant-ssg",
    permissions: [],
    ...overrides,
  };
}
