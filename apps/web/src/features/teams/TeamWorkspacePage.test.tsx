import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type {
  EligibleRosterAnalyst,
  TeamActivity,
  TeamMember,
  TeamWorkspaceAccess,
} from "../../lib/api/teamTypes";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";

const managerSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-osg",
    username: "admin8",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "OSG Team",
  },
};
const analystSession: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "analyst-osg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
  },
};
const managerAccess: TeamWorkspaceAccess = {
  teamId: "team-osg",
  teamCode: "OSG_TEAM",
  teamName: "OSG Team",
  grantId: "grant-osg",
  permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"],
};
const analystAccess: TeamWorkspaceAccess = {
  ...managerAccess,
  grantId: null,
  permissions: [],
};
const people: TeamMember[] = [
  {
    membershipId: "membership-manager",
    accountId: "manager-osg",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    startReason: "Established synthetic team baseline.",
    endReason: null,
  },
  {
    membershipId: "membership-lewis",
    accountId: "analyst-osg",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 2,
    activeWorkCount: 0,
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
    startReason: "Historical team membership.",
    endReason: "The Analyst transferred to another team.",
  },
];
const eligible: EligibleRosterAnalyst[] = [
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

describe("team workspace", () => {
  it("provides an accessible overview, all workspace views and immutable activity", async () => {
    mockTeamApi(managerSession, managerAccess);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-osg/overview");
    expect(await screen.findByRole("heading", { name: "OSG Team" })).toBeInTheDocument();
    expect(await screen.findByText("3", { selector: ".team-metric strong" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace" })).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Organisation workspace views" })).getAllByRole("link")).toHaveLength(7);
    expect(await axe(view.container)).toHaveNoViolations();

    const tabs = screen.getByRole("navigation", { name: "Organisation workspace views" });
    await user.click(within(tabs).getByRole("link", { name: "Board" }));
    expect(await screen.findByRole("heading", { name: "Workflow board" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("navigation", { name: "Organisation workspace views" })).getByRole("link", { name: "Calendar" }));
    expect(await screen.findByRole("heading", { name: "Add calendar activity" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("navigation", { name: "Organisation workspace views" })).getByRole("link", { name: "Planning" }));
    expect(await screen.findByRole("heading", { name: "Team planning" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("navigation", { name: "Organisation workspace views" })).getByRole("link", { name: "Activity" }));
    expect(await screen.findByText("A scheduled Analyst transfer became effective.")).toBeInTheDocument();
    expect(screen.getByText(/scheduled membership service/)).toBeInTheDocument();
  });

  it("lets an exact-team Manager add, transfer and end Analysts with mandatory evidence", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    mockTeamApi(managerSession, managerAccess, bodies);
    const user = userEvent.setup();
    renderApp("/teams/team-osg/people");
    expect(await screen.findByRole("heading", { name: "People" })).toBeInTheDocument();
    expect(screen.getByText("The Analyst transferred to another team.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "End membership" })[0]).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "End membership" })[1]).toBeDisabled();

    await user.selectOptions(screen.getByLabelText(/^Member/), "alan");
    await user.type(screen.getByLabelText(/^Reason/), "Alan is joining to balance current delivery demand.");
    await user.click(screen.getByRole("button", { name: "Add Member" }));
    await waitFor(() => expect(bodies.some((body) => body.analystId === "alan")).toBe(true));

    await user.click(screen.getByRole("button", { name: "Schedule transfer" }));
    await user.selectOptions(screen.getByLabelText(/^Member/), "beth");
    fireEvent.change(screen.getByLabelText(/Effective date/), { target: { value: "2026-08-20T10:00" } });
    await user.type(screen.getByLabelText(/^Reason/), "Beth will transfer after the current planning cycle.");
    await user.click(screen.getByRole("button", { name: "Confirm transfer" }));
    await waitFor(() => expect(bodies.some((body) => body.currentMembershipId === "membership-beth")).toBe(true));

    await user.click(screen.getAllByRole("button", { name: "End membership" })[0]);
    await user.type(screen.getByLabelText(/Reason for ending/), "Lewis is moving after all assigned work was completed.");
    await user.click(screen.getByRole("button", { name: "Confirm end" }));
    await waitFor(() => expect(bodies.some((body) => body.expectedVersion === 2 && !body.analystId)).toBe(true));
  });

  it("keeps Analysts read-only and handles unavailable, missing and invalid workspace routes", async () => {
    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-osg/people");
    expect(await screen.findByText("Lewis Ferguson")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Change roster" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "End membership" })).not.toBeInTheDocument();

    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-other/overview");
    expect(await screen.findByRole("heading", { name: "Team workspace unavailable" })).toBeInTheDocument();

    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-osg/not-a-view");
    expect(await screen.findByText("One team, one operational picture")).toBeInTheDocument();
  });

  it("reports an empty assignment and recovers workspace and overview queries", async () => {
    mockFeatureFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/teams/team-osg/overview");
    expect(await screen.findByRole("heading", { name: "No team workspace assigned" })).toBeInTheDocument();

    let workspaceAttempts = 0;
    let overviewAttempts = 0;
    const quartz = { ...managerAccess, teamId: "team-quartz", teamCode: "QUARTZ_TEAM", teamName: "Quartz Team" };
    mockFeatureFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) {
        workspaceAttempts += 1;
        return workspaceAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: [managerAccess, quartz] });
      }
      if (url.pathname.endsWith("/team-workspaces/team-osg")) {
        overviewAttempts += 1;
        return overviewAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ access: managerAccess, managerCount: 2, analystCount: 4, activeWorkCount: 1, dueSoonCount: 0, overdueCount: 0 });
      }
      if (url.pathname.endsWith("/team-workspaces/team-quartz")) return json({ access: quartz, managerCount: 1, analystCount: 2, activeWorkCount: 0, dueSoonCount: 0, overdueCount: 0 });
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    const user = userEvent.setup();
    renderApp("/teams/team-osg/overview");
    expect(await screen.findByRole("heading", { name: "Team workspace could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(workspaceAttempts).toBe(2));
    expect(await screen.findByRole("heading", { name: "Team workspace could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("One team, one operational picture")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Workspace"), "team-quartz");
    expect(await screen.findByRole("heading", { name: "Quartz Team" })).toBeInTheDocument();
  });

  it("recovers activity, people and roster-option errors and reports failed changes", async () => {
    let activityAttempts = 0;
    mockFeatureFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
      if (url.pathname.endsWith("/activity")) {
        activityAttempts += 1;
        return activityAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    const user = userEvent.setup();
    renderApp("/teams/team-osg/activity");
    expect(await screen.findByRole("heading", { name: "Team activity could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No team activity recorded" })).toBeInTheDocument();

    let peopleAttempts = 0;
    let eligibleAttempts = 0;
    mockFeatureFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
      if (url.pathname.endsWith("/people")) {
        peopleAttempts += 1;
        return peopleAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: people });
      }
      if (url.pathname.endsWith("/eligible-analysts")) {
        eligibleAttempts += 1;
        return eligibleAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: eligible });
      }
      if (url.pathname.endsWith("/end")) return json({ detail: "Membership end conflict" }, 409);
      if (url.pathname.endsWith("/memberships")) return json({ detail: "Roster conflict" }, 409);
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    renderApp("/teams/team-osg/people");
    expect(await screen.findByRole("heading", { name: "Team people could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Eligible Members could not be loaded.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await user.selectOptions(await screen.findByLabelText(/^Member/), "alan");
    await user.type(screen.getByLabelText(/^Reason/), "Alan cannot join while a conflicting change is pending.");
    await user.click(screen.getByRole("button", { name: "Add Member" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Roster conflict");
    await user.click(screen.getByRole("button", { name: "Schedule transfer" }));
    await user.selectOptions(screen.getByLabelText(/^Member/), "beth");
    fireEvent.submit(screen.getByRole("button", { name: "Confirm transfer" }).closest("form")!);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Complete the transfer details"));
    await user.click(screen.getAllByRole("button", { name: "End membership" })[0]);
    await user.type(screen.getByLabelText(/Reason for ending/), "Lewis cannot leave during a conflicting roster update.");
    await user.click(screen.getByRole("button", { name: "Confirm end" }));
    const endForm = screen.getByRole("button", { name: "Confirm end" }).closest("form")!;
    expect(await within(endForm).findByRole("alert")).toHaveTextContent("Membership end conflict");
  });
});

function mockTeamApi(
  session: Session,
  access: TeamWorkspaceAccess,
  bodies: Array<Record<string, unknown>> = [],
) {
  return mockFeatureFetch(async (url, init) => {
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
    if (url.pathname.endsWith("/eligible-analysts")) return json({ items: eligible });
    if (url.pathname.endsWith("/people")) return json({ items: people.map((item) => access.grantId ? item : { ...item, startReason: null, endReason: null }) });
    if (url.pathname.endsWith("/activity")) return json({ items: activity });
    if (url.pathname.endsWith("/board")) return json({ items: [], nextCursor: null, wipLimits: {}, configurationVersion: 0, savedViews: [], generatedAt: "2026-08-07T12:00:00Z" });
    if (url.pathname.endsWith("/iterations")) return json({ items: [] });
    if (url.pathname.endsWith("/packages")) return json({ items: [] });
    if (url.pathname.endsWith("/calendar")) return json({ items: [] });
    if (url.pathname.endsWith("/memberships") || url.pathname.endsWith("/transfers") || url.pathname.endsWith("/end")) {
      bodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return json({ items: people });
    }
    if (url.pathname.endsWith(`/team-workspaces/${access.teamId}`)) return json({ access, managerCount: 3, analystCount: 7, activeWorkCount: 4, dueSoonCount: 2, overdueCount: 1 });
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, true, false);
}
