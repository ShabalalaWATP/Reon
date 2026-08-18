import { screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session, UserRole } from "../../lib/api/types";
import type { StatisticsDashboard, StatisticsScope } from "../../lib/api/statisticsTypes";
import {
  adminSession,
  enabledCapabilities,
  requesterSession,
  staffSession,
} from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { overviewScopes } from "./roleOverviewFixtures";

const rootId = "00000000-0000-4000-8000-000000000001";
const childId = "00000000-0000-4000-8000-000000000002";
const teamId = "00000000-0000-4000-8000-000000000003";
const scope: StatisticsScope = {
  id: "scope-crioc",
  unitId: rootId,
  name: "CRIOC",
  kind: "ROOT",
  includeDescendants: true,
  units: [
    { id: rootId, parentId: null, name: "CRIOC", kind: "ROOT", depth: 0 },
    { id: childId, parentId: rootId, name: "JOCK", kind: "COMMAND", depth: 1 },
  ],
};
const statistics: StatisticsDashboard = {
  scope,
  selectedUnit: scope.units[0],
  breadcrumb: [scope.units[0]],
  range: {
    fromDate: "2026-07-10",
    toDate: "2026-08-08",
    timeZone: "Europe/London",
    asOfDate: "2026-08-08",
  },
  freshness: {
    health: "READY",
    lastProjectedAt: "2026-08-08T12:00:00Z",
    sourceEventCount: 10,
    projectedRequestCount: 8,
  },
  definitions: [],
  summary: [
    { key: "active", label: "Active", value: 8, unit: "count", suppressed: false },
    { key: "overdue", label: "Overdue", value: 2, unit: "count", suppressed: false },
    { key: "completed", label: "Completed", value: 6, unit: "count", suppressed: false },
    { key: "released", label: "Released", value: 4, unit: "count", suppressed: false },
    { key: "rework", label: "Rework", value: 1, unit: "count", suppressed: false },
    { key: "feedback", label: "Feedback", value: 3, unit: "count", suppressed: false },
  ],
  status: [],
  age: [],
  dueRisk: [{ key: "due-1", label: "Due within 7 days", count: 3 }],
  throughputResolution: "DAILY",
  throughput: [],
  stageDurations: [],
  children: [
    {
      unitId: childId,
      name: "JOCK",
      kind: "COMMAND",
      received: 7,
      active: 5,
      completed: 2,
      overdue: 1,
      feedbackCount: 4,
      averageRating: 4.5,
      ratingSuppressed: false,
    },
  ],
};
const actions = {
  items: [],
  counts: { needsMyAction: 3, waiting: 2, dueSoon: 1, recentlyCompleted: 4 },
  savedViews: [],
  nextCursor: null,
  freshness: {
    status: "CURRENT",
    projectedAt: null,
    sourceChangedAt: null,
    lagSeconds: null,
    pendingCount: 0,
  },
};

describe("role-specific operational overview", () => {
  it("gives a routing user a scoped, accessible organisation landing page", async () => {
    mockOverview(staffSession);
    const view = renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action3",
    );
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Waiting on others2",
    );
    expect(screen.getByRole("region", { name: "CRIOC organisation workload" })).toHaveTextContent(
      "Active demand8",
    );
    expect(screen.getByRole("region", { name: "CRIOC organisation workload" })).toHaveTextContent(
      "not your personal workload",
    );
    const destinations = screen.getByRole("navigation", { name: "Home destinations" });
    expect(
      within(destinations).getByRole("heading", { name: "Continue working" }),
    ).toBeInTheDocument();
    expect(within(destinations).getAllByRole("link")).toHaveLength(6);
    expect(within(destinations).getByRole("link", { name: /My assigned actions/ })).toHaveAttribute(
      "href",
      "/my-work",
    );
    expect(within(destinations).getByRole("link", { name: /CRIOC workspace/ })).toHaveAttribute(
      "href",
      `/teams/${rootId}/overview`,
    );
    expect(within(destinations).getByRole("link", { name: /Personal calendar/ })).toHaveAttribute(
      "href",
      "/calendar/month",
    );
    expect(
      within(destinations).getByRole("link", { name: /Operational statistics/ }),
    ).toHaveAttribute("href", "/statistics");
    expect(screen.queryByText("JOCK")).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("provides the Administrator with platform destinations without request content", async () => {
    mockOverview(adminSession);
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Welcome, Andy" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Home destinations" })).toHaveTextContent(
      "User accounts",
    );
    expect(screen.queryByText("My requests")).not.toBeInTheDocument();
  });

  it("shows QC-focused measures and destinations", async () => {
    mockOverview(asRole("QUALITY_RELEASE", "QC Manager"));
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action3",
    );
    expect(screen.getByRole("region", { name: "QC Team workload" })).toHaveTextContent(
      "Products released4",
    );
    expect(screen.getByRole("link", { name: /Quality statistics/ })).toHaveAttribute(
      "href",
      expect.stringContaining(scope.id),
    );
  });

  it("gives a QC User a review-only home without manager statistics", async () => {
    mockOverview(asRole("QUALITY_RELEASE", "QC User"), false, true);
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Product reviews currently assigned to you.",
    );
    expect(screen.getByText(/Dissemination remains a QC Manager action/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "QC Team workload" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Quality statistics/ })).not.toBeInTheDocument();
  });

  it("uses explicit zero states at the lowest authorised organisation", async () => {
    mockOverview(staffSession, false, false, false, {
      ...statistics,
      children: [],
      summary: [],
      dueRisk: [],
    });
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Continue working" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "CRIOC organisation workload" })).toHaveTextContent(
      "Active demand0",
    );
  });

  it("gives a Team Manager a personal Home distinct from the shared workspace", async () => {
    mockOverview(asRole("DELIVERY_TEAM_LEAD", "Team Manager"), true);
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action3",
    );
    expect(
      screen.getByRole("region", { name: "SSG Team organisation workload" }),
    ).toHaveTextContent("Active demand8");
    const destinations = screen.getByRole("navigation", { name: "Home destinations" });
    expect(within(destinations).getByRole("link", { name: /SSG Team workspace/ })).toHaveAttribute(
      "href",
      `/teams/${teamId}/overview`,
    );
    expect(within(destinations).getByRole("link", { name: /Personal calendar/ })).toHaveAttribute(
      "href",
      "/calendar/month",
    );
  });

  it("keeps the Customer in My requests and gives an Analyst a personal Home", async () => {
    mockOverview(requesterSession);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();

    mockOverview(asRole("DELIVERY_SPECIALIST", "Team Analyst"));
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action3",
    );
    expect(
      within(screen.getByRole("navigation", { name: "Home destinations" })).getByRole("link", {
        name: /My assigned actions/,
      }),
    ).toHaveAttribute("href", "/my-work");
  });

  it("gives a workspace Member a personal home without broadening statistics access", async () => {
    mockOverview(staffSession, false, true);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action3",
    );
    const destinations = screen.getByRole("navigation", { name: "Home destinations" });
    expect(within(destinations).getByRole("link", { name: /CRIOC workspace/ })).toHaveAttribute(
      "href",
      `/teams/${rootId}/overview`,
    );
    expect(screen.queryByRole("link", { name: /Operational statistics/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "CRIOC organisation workload" }),
    ).not.toBeInTheDocument();
  });

  it("reports missing scope and team assignments without broadening access", async () => {
    mockOverview(staffSession, false, true, true);
    renderApp("/overview");
    expect(
      await screen.findByRole("heading", { name: "Your overview could not be loaded" }),
    ).toBeInTheDocument();

    mockOverview(asRole("DELIVERY_TEAM_LEAD", "Team Manager"), false, false, true);
    renderApp("/overview");
    expect(
      await screen.findByRole("heading", { name: "Your overview could not be loaded" }),
    ).toBeInTheDocument();

    mockOverview(asRole("QUALITY_RELEASE", "QC Manager"), false, true);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Quality statistics/ })).not.toBeInTheDocument();
  });
});

function asRole(role: UserRole, scopeName: string): Session {
  return {
    ...staffSession,
    user: { ...staffSession.user, id: `user-${role.toLowerCase()}`, role, scope: scopeName },
  };
}

function mockOverview(
  session: Session,
  withTeam = false,
  emptyScopes = false,
  emptyTeams = false,
  dashboard: StatisticsDashboard = statistics,
) {
  return mockFeatureFetch(
    (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/me/actions")) return json(actions);
      if (url.pathname.endsWith("/statistics/scopes"))
        return json(overviewScopes(emptyScopes, withTeam, scope, teamId));
      if (url.pathname.endsWith("/statistics")) return json(dashboard);
      if (url.pathname.endsWith("/team-workspaces")) {
        const selectedWorkspace =
          session.user.role === "QUALITY_RELEASE"
            ? {
                teamId: "00000000-0000-4000-8000-000000000004",
                teamCode: "QC_TEAM",
                teamName: "Combined QC Team",
                workspacePosition: session.user.scope === "QC User" ? "MEMBER" : "MANAGER",
                grantId: "grant-qc",
                permissions: session.user.scope === "QC User" ? [] : ["STATISTICS"],
              }
            : withTeam
              ? {
                  teamId,
                  teamCode: "SSG_TEAM",
                  teamName: "SSG Team",
                  workspacePosition: "MANAGER",
                  grantId: "grant-ssg",
                  permissions: ["STATISTICS"],
                }
              : {
                  teamId: rootId,
                  teamCode: "CRIOC",
                  teamName: "CRIOC",
                  workspacePosition: "MEMBER",
                  grantId: null,
                  permissions: [],
                };
        return json({ items: emptyTeams ? [] : [selectedWorkspace] });
      }
      if (url.pathname.endsWith(`/team-workspaces/${teamId}`)) {
        return json({
          access: {
            teamId,
            teamCode: "SSG_TEAM",
            teamName: "SSG Team",
            grantId: "grant-ssg",
            permissions: ["STATISTICS"],
          },
          managerCount: 2,
          analystCount: 4,
          activeWorkCount: 5,
          dueSoonCount: 2,
          overdueCount: 1,
        });
      }
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    },
    {
      emptyActionWorkspace: false,
      emptyStatisticsScopes: false,
      emptyTeamWorkspaces: false,
    },
  );
}
