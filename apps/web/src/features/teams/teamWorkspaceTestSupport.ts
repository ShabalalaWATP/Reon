import type { Session } from "../../lib/api/types";
import type {
  EligibleRosterAnalyst,
  TeamActivity,
  TeamMember,
  TeamWorkspaceAccess,
} from "../../lib/api/teamTypes";
import { enabledCapabilities } from "../../test/fixtures";
import { json, mockFeatureFetch } from "../../test/render";
import { createTeamWorkspaceAccess } from "../../test/teamFixtures";

export { analystSession, managerSession } from "../../test/teamFixtures";

export const managerAccess = createTeamWorkspaceAccess({
  permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"],
  views: ["OVERVIEW", "BOARD", "CALENDAR", "PEOPLE", "STATISTICS", "ACTIVITY"],
});
export const analystAccess: TeamWorkspaceAccess = {
  ...managerAccess,
  grantId: null,
  permissions: [],
};

export const people: TeamMember[] = [
  {
    membershipId: "membership-manager",
    accountId: "manager-ssg",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    skills: ["Delivery leadership", "Briefing"],
    startReason: "Established synthetic team baseline.",
    endReason: null,
  },
  {
    membershipId: "membership-lewis",
    accountId: "analyst-ssg",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 2,
    activeWorkCount: 0,
    skills: ["Research", "Data analysis"],
    startReason: "Established synthetic team baseline.",
    endReason: null,
  },
  {
    membershipId: "membership-busy",
    accountId: "analyst-busy",
    displayName: "Busy Analyst",
    role: "DELIVERY_SPECIALIST",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 2,
    skills: [],
    startReason: "Established synthetic team baseline.",
    endReason: null,
  },
  {
    membershipId: "membership-ended",
    accountId: "analyst-ended",
    displayName: "Former Analyst",
    role: "DELIVERY_SPECIALIST",
    state: "ENDED",
    effectiveFrom: "2025-01-01T09:00:00Z",
    effectiveUntil: "2026-01-01T09:00:00Z",
    version: 2,
    activeWorkCount: 0,
    skills: [],
    startReason: "Historical team membership.",
    endReason: "The Analyst transferred to another team.",
  },
];
export const eligible: EligibleRosterAnalyst[] = [
  {
    accountId: "alan",
    displayName: "Alan Hansen",
    currentTeamId: null,
    currentTeamName: null,
    currentMembershipId: null,
    currentMembershipVersion: null,
    activeWorkCount: 0,
  },
  {
    accountId: "beth",
    displayName: "Beth England",
    currentTeamId: "team-quartz",
    currentTeamName: "Quartz Team",
    currentMembershipId: "membership-beth",
    currentMembershipVersion: 3,
    activeWorkCount: 0,
  },
];
const activity: TeamActivity[] = [
  {
    id: "activity-1",
    type: "MEMBER_ADDED",
    summary: "An Analyst joined the team.",
    actorDisplayName: "Grant Hanley",
    subjectDisplayName: "Alan Hansen",
    createdAt: "2026-08-07T10:00:00Z",
  },
  {
    id: "activity-2",
    type: "TRANSFER_ACTIVATED",
    summary: "A scheduled Analyst transfer became effective.",
    actorDisplayName: null,
    subjectDisplayName: "Beth England",
    createdAt: "2026-08-07T11:00:00Z",
  },
];

export function mockTeamApi(
  session: Session,
  access: TeamWorkspaceAccess,
  bodies: Array<Record<string, unknown>> = [],
) {
  return mockFeatureFetch(
    async (url, init) => {
      const readResponse = teamReadResponse(url, session, access);
      if (readResponse) return readResponse;
      if (
        url.pathname.endsWith("/memberships") ||
        url.pathname.endsWith("/transfers") ||
        url.pathname.endsWith("/end")
      ) {
        bodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return json({ items: people });
      }
      if (url.pathname.endsWith(`/team-workspaces/${access.teamId}`))
        return json({
          access,
          managerCount: 3,
          analystCount: 7,
          activeWorkCount: 4,
          dueSoonCount: 2,
          overdueCount: 1,
        });
      throw new Error(`Unexpected ${url.pathname}`);
    },
    { emptyTeamWorkspaces: false },
  );
}

function teamReadResponse(url: URL, session: Session, access: TeamWorkspaceAccess) {
  if (url.pathname.endsWith("/auth/me")) return json(session);
  if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
  if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
  if (url.pathname.endsWith("/eligible-analysts")) return json({ items: eligible });
  if (url.pathname.endsWith("/people"))
    return json({
      items: people.map((item) =>
        access.grantId ? item : { ...item, startReason: null, endReason: null },
      ),
    });
  if (url.pathname.endsWith("/activity")) return json({ items: activity });
  if (url.pathname.endsWith("/board"))
    return json({
      items: [],
      nextCursor: null,
      columnCounts: { AWAITING_ASSIGNMENT: 2, BLOCKED: 1, MANAGER_REVIEW: 1 },
      totalCount: 4,
      wipLimits: {},
      configurationVersion: 0,
      savedViews: [],
      generatedAt: "2026-08-07T12:00:00Z",
    });
  if (url.pathname.endsWith("/iterations") || url.pathname.endsWith("/packages"))
    return json({ items: [] });
  if (url.pathname.endsWith("/calendar"))
    return json({
      items: [
        {
          eventId: "event-one",
          occurrenceStart: "2026-08-11T09:00:00Z",
          startsAt: "2026-08-11T09:00:00Z",
          endsAt: "2026-08-11T16:00:00Z",
          title: "Synthetic course",
          subjectDisplayName: "Lewis Ferguson",
          category: "TRAINING",
        },
      ],
    });
  if (url.pathname.endsWith("/records"))
    return json({
      items: [
        {
          id: "record-one",
          kind: "RISK",
          status: "OPEN",
          title: "Review capacity assumption",
          body: "Synthetic context.",
          url: null,
          createdByDisplayName: "Grant Hanley",
          resolution: null,
          version: 1,
          createdAt: "2026-08-07T09:00:00Z",
          updatedAt: "2026-08-07T10:00:00Z",
        },
      ],
    });
  return undefined;
}
