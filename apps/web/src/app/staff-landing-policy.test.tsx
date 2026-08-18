import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { adminSession, enabledCapabilities, staffSession } from "../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../test/render";
import { disabledCapabilities } from "../lib/api/capabilityClient";

const emptyActions = {
  items: [],
  savedViews: [],
  nextCursor: null,
  counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
  freshness: {
    status: "CURRENT",
    projectedAt: null,
    sourceChangedAt: null,
    lagSeconds: null,
    pendingCount: 0,
  },
};
const overviewScope = {
  id: "scope-overview",
  unitId: "unit-overview",
  name: "Platform service",
  kind: "ROOT",
  includeDescendants: true,
  units: [],
};
const emptyStatistics = { summary: [], dueRisk: [] };
const overviewWorkspace = {
  teamId: "crioc",
  teamCode: "CRIOC",
  teamName: "CRIOC",
  unitKind: "ROOT",
  workspacePosition: "MEMBER",
  grantId: null,
  permissions: [],
};

describe("staff landing policy", () => {
  it("opens the Administrator Home without loading request content", async () => {
    mockFeatureFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(adminSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/me/actions")) return json(emptyActions);
        if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [overviewScope] });
        if (url.pathname.endsWith("/statistics")) return json(emptyStatistics);
        throw new Error("Request content must not be fetched");
      },
      { emptyActionWorkspace: false, emptyStatisticsScopes: false },
    );

    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Welcome, Andy" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /User accounts/ })[0]).toHaveAttribute(
      "href",
      "/admin/users",
    );
    expect(screen.queryByText("My requests")).not.toBeInTheDocument();
  });

  it("redirects staff away from Customer routes to Home", async () => {
    mockFeatureFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(staffSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/me/actions")) return json(emptyActions);
        if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [overviewScope] });
        if (url.pathname.endsWith("/statistics")) return json(emptyStatistics);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [overviewWorkspace] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      {
        emptyActionWorkspace: false,
        emptyStatisticsScopes: false,
        emptyTeamWorkspaces: false,
      },
    );

    renderApp("/requests");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /CRIOC workspace/ })[0]).toHaveAttribute(
      "href",
      "/teams/crioc/overview",
    );
  });

  it("keeps staff Home available when optional dashboards are disabled", async () => {
    const fetchMock = mockFeatureFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(staffSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(disabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [overviewWorkspace] });
        throw new Error(`Disabled Home must not request ${url.pathname}`);
      },
      { emptyTeamWorkspaces: false },
    );

    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Welcome, Scott" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Your workload" })).toHaveTextContent(
      "Needs your action0",
    );
    const paths = fetchMock.mock.calls.map(
      ([input]) => new URL(String(input), "http://localhost").pathname,
    );
    expect(paths).not.toContain("/api/v1/me/actions");
    expect(paths).not.toContain("/api/v1/statistics/scopes");
  });
});
