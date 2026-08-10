import { screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session, UserRole } from "../../lib/api/types";
import type { StatisticsDashboard, StatisticsScope } from "../../lib/api/statisticsTypes";
import { adminSession, enabledCapabilities, requesterSession, staffSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const rootId = "00000000-0000-4000-8000-000000000001";
const childId = "00000000-0000-4000-8000-000000000002";
const teamId = "00000000-0000-4000-8000-000000000003";
const scope: StatisticsScope = {
  id: "scope-jioc",
  unitId: rootId,
  name: "JIOC",
  kind: "ROOT",
  includeDescendants: true,
  units: [
    { id: rootId, parentId: null, name: "JIOC", kind: "ROOT", depth: 0 },
    { id: childId, parentId: rootId, name: "DIGOC", kind: "COMMAND", depth: 1 },
  ],
};
const statistics: StatisticsDashboard = {
  scope,
  selectedUnit: scope.units[0],
  breadcrumb: [scope.units[0]],
  range: { fromDate: "2026-07-10", toDate: "2026-08-08", timeZone: "Europe/London", asOfDate: "2026-08-08" },
  freshness: { health: "READY", lastProjectedAt: "2026-08-08T12:00:00Z", sourceEventCount: 10, projectedRequestCount: 8 },
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
  children: [{ unitId: childId, name: "DIGOC", kind: "COMMAND", received: 7, active: 5, completed: 2, overdue: 1, feedbackCount: 4, averageRating: 4.5, ratingSuppressed: false }],
};
const actions = {
  items: [],
  counts: { needsMyAction: 3, waiting: 2, dueSoon: 1, recentlyCompleted: 4 },
  savedViews: [],
  nextCursor: null,
  freshness: { status: "CURRENT", projectedAt: null, sourceChangedAt: null, lagSeconds: null, pendingCount: 0 },
};

describe("role-specific operational overview", () => {
  it("gives a routing user a scoped, accessible organisation landing page", async () => {
    mockOverview(staffSession);
    const view = renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "JIOC overview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Operational overview measures" })).toHaveTextContent("Needs your action3");
    expect(screen.getByRole("link", { name: /DIGOC/ })).toHaveAttribute(
      "href",
      expect.stringContaining(`unitId=${childId}`),
    );
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("provides the Administrator with platform destinations without request content", async () => {
    mockOverview(adminSession);
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Administration overview" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Overview destinations" })).toHaveTextContent("User accounts");
    expect(screen.queryByText("My requests")).not.toBeInTheDocument();
  });

  it("shows QC-focused measures and destinations", async () => {
    mockOverview(asRole("QUALITY_RELEASE", "QC Manager"));
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Quality overview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Quality work measures" })).toHaveTextContent("Products released4");
    expect(screen.getByRole("link", { name: /Quality statistics/ })).toHaveAttribute("href", expect.stringContaining(scope.id));
  });

  it("uses explicit zero states at the lowest authorised organisation", async () => {
    mockOverview(
      staffSession,
      false,
      false,
      false,
      { ...statistics, children: [], summary: [], dueRisk: [] },
    );
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "Selected scope" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Operational overview measures" })).toHaveTextContent("Active demand0");
  });

  it("redirects a Team Manager to their shared team overview", async () => {
    mockOverview(asRole("DELIVERY_TEAM_LEAD", "Team Manager"), true);
    renderApp("/overview");

    expect(await screen.findByRole("heading", { name: "OSG Team" })).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Workspace staffing" }, { timeout: 5_000 })).toHaveTextContent("Analysts4");
  });

  it("keeps Customer and Analyst home destinations transactional", async () => {
    mockOverview(requesterSession);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();

    mockOverview(asRole("DELIVERY_SPECIALIST", "Team Analyst"));
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "My actions" })).toBeInTheDocument();
  });

  it("reports missing scope and team assignments without broadening access", async () => {
    mockOverview(staffSession, false, true);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "Your overview could not be loaded" })).toBeInTheDocument();

    mockOverview(asRole("DELIVERY_TEAM_LEAD", "Team Manager"), false, false, true);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "No team overview assigned" })).toBeInTheDocument();

    mockOverview(asRole("QUALITY_RELEASE", "QC Manager"), false, true);
    renderApp("/overview");
    expect(await screen.findByRole("heading", { name: "Quality overview could not be loaded" })).toBeInTheDocument();
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
  return mockFeatureFetch((url) => {
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/me/actions")) return json(actions);
    if (url.pathname.endsWith("/statistics/scopes")) {
      if (emptyScopes) return json({ items: [] });
      if (withTeam) return json({ items: [{ ...scope, id: "scope-osg", unitId: teamId, name: "OSG Team", kind: "TEAM", units: [{ id: teamId, parentId: null, name: "OSG Team", kind: "TEAM", depth: 0 }] }] });
      return json({ items: [scope] });
    }
    if (url.pathname.endsWith("/statistics")) return json(dashboard);
    if (url.pathname.endsWith("/team-workspaces")) {
      return json({ items: emptyTeams ? [] : [{ teamId, teamCode: "OSG_TEAM", teamName: "OSG Team", grantId: "grant-osg", permissions: ["STATISTICS"] }] });
    }
    if (url.pathname.endsWith(`/team-workspaces/${teamId}`)) {
      return json({ access: { teamId, teamCode: "OSG_TEAM", teamName: "OSG Team", grantId: "grant-osg", permissions: ["STATISTICS"] }, managerCount: 2, analystCount: 4, activeWorkCount: 5, dueSoonCount: 2, overdueCount: 1 });
    }
    if (url.pathname.endsWith("/requests")) return json({ items: [] });
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, false, false, false, true);
}
