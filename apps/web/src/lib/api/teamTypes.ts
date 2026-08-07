export type ManagementAction =
  | "STATISTICS"
  | "ROSTER"
  | "CALENDAR"
  | "BOARD"
  | "CAPACITY";

export type TeamWorkspaceAccess = {
  teamId: string;
  teamCode: string;
  teamName: string;
  grantId: string | null;
  permissions: ManagementAction[];
};

export type TeamWorkspaceOverview = {
  access: TeamWorkspaceAccess;
  managerCount: number;
  analystCount: number;
  activeWorkCount: number;
  dueSoonCount: number;
  overdueCount: number;
};

export type MembershipState = "CURRENT" | "SCHEDULED" | "ENDED";

export type TeamMember = {
  membershipId: string;
  accountId: string;
  displayName: string;
  role: "DELIVERY_TEAM_LEAD" | "DELIVERY_SPECIALIST";
  state: MembershipState;
  effectiveFrom: string;
  effectiveUntil: string | null;
  version: number;
  activeWorkCount: number;
  startReason: string | null;
  endReason: string | null;
};

export type EligibleRosterAnalyst = {
  accountId: string;
  displayName: string;
  currentTeamId: string | null;
  currentTeamName: string | null;
  currentMembershipId: string | null;
  currentMembershipVersion: number | null;
  activeWorkCount: number;
};

export type TeamActivity = {
  id: string;
  type: string;
  summary: string;
  actorDisplayName: string | null;
  subjectDisplayName: string;
  createdAt: string;
};

export type TeamWorkspaceList = { items: TeamWorkspaceAccess[] };
export type TeamPeople = { items: TeamMember[] };
export type EligibleRosterAnalystList = { items: EligibleRosterAnalyst[] };
export type TeamActivityList = { items: TeamActivity[] };

export type AddMemberInput = {
  grantId: string;
  analystId: string;
  reason: string;
};

export type TransferMemberInput = AddMemberInput & {
  currentMembershipId: string;
  expectedVersion: number;
  effectiveFrom: string;
};

export type EndMembershipInput = {
  grantId: string;
  expectedVersion: number;
  reason: string;
};
