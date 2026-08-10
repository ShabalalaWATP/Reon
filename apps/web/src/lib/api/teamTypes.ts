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
  unitKind?: "ROOT" | "COMMAND" | "OPS_GROUP" | "TEAM";
  workspacePosition?: "MANAGER" | "MEMBER" | null;
  grantId: string | null;
  permissions: ManagementAction[];
  views?: string[];
};

export type TeamWorkspaceOverview = {
  access: TeamWorkspaceAccess;
  managerCount: number;
  memberCount?: number;
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
  role: "INTAKE_TRIAGE" | "SERVICE_COORDINATION" | "OPERATIONS_ALLOCATION" | "DELIVERY_TEAM_LEAD" | "DELIVERY_SPECIALIST";
  workspacePosition?: "MANAGER" | "MEMBER";
  state: MembershipState;
  effectiveFrom: string;
  effectiveUntil: string | null;
  version: number;
  activeWorkCount: number;
  skills: string[];
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

export type WorkspaceRecordKind = "DESCRIPTION" | "HANDOVER" | "RISK" | "BLOCKER" | "DECISION" | "LINK";
export type WorkspaceRecord = {
  id: string;
  kind: WorkspaceRecordKind;
  status: "OPEN" | "RESOLVED";
  title: string;
  body: string;
  url: string | null;
  createdByDisplayName: string;
  resolution: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
};
export type WorkspaceRecordList = { items: WorkspaceRecord[] };
