import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { WorkItem } from "../../lib/api/workTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const routingManager: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-crioc",
    username: "admin74",
    displayName: "Alan Rough",
    role: "INTAKE_TRIAGE",
    scope: "CRIOC",
  },
};

const managerAccess: TeamWorkspaceAccess = {
  teamId: "crioc",
  teamCode: "CRIOC",
  teamName: "CRIOC",
  unitKind: "ROOT",
  workspacePosition: "MANAGER",
  grantId: "grant-crioc",
  permissions: ["STATISTICS", "ROSTER", "CALENDAR"],
  views: ["OVERVIEW", "QUEUE", "CALENDAR", "PEOPLE", "STATISTICS", "ACTIVITY"],
};

describe("routing organisation workspace", () => {
  it("contains the actionable unit queue without separate planning or handover", async () => {
    let requestedUnit: string | null = null;
    mockRoutingApi({
      onWorkItems: (url) => { requestedUnit = url.searchParams.get("unitId"); },
      workItems: [routingWork({ id: "available" })],
    });
    const view = renderApp("/teams/crioc/queue");

    expect(await screen.findByRole("heading", { name: "Work queue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Claim work item" })).toBeInTheDocument();
    expect(requestedUnit).toBe("crioc");
    const tabs = screen.getByRole("navigation", { name: "Organisation workspace views" });
    expect(within(tabs).getByRole("link", { name: "Work queue" })).toHaveAttribute(
      "href",
      "/teams/crioc/queue",
    );
    expect(within(tabs).queryByRole("link", { name: "Planning" })).not.toBeInTheDocument();
    expect(within(tabs).queryByRole("link", { name: "Handover" })).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it.each(["planning", "handover"])("returns the old %s view to the workspace overview", async (legacyView) => {
    mockRoutingApi();
    renderApp(`/teams/crioc/${legacyView}`);

    expect(await screen.findByRole("heading", { name: "Routing decisions" })).toBeInTheDocument();
    expect(screen.getByText("Routing work, people, availability and performance in one place.")).toBeInTheDocument();
  });

  it("summarises the routing unit and its authorised descendant statistics", async () => {
    mockRoutingApi({ workItems: [
      routingWork({ id: "available" }),
      routingWork({ id: "mine", assigneeId: "manager-crioc", assigneeDisplayName: "Alan Rough", stage: "INFORMATION_REQUIRED" }),
    ] });
    renderApp("/teams/crioc/overview");

    expect(await screen.findByRole("heading", { name: "CRIOC" })).toBeInTheDocument();
    const decisions = await screen.findByRole("region", { name: "Routing decisions" });
    await waitFor(() => expect(within(decisions).getByText("Available to claim").closest("div")).toHaveTextContent("1"));
    expect(within(decisions).getByText("Claimed by you").closest("div")).toHaveTextContent("1");
    expect(within(decisions).getByText("Information required").closest("div")).toHaveTextContent("1");
    expect(screen.getByRole("link", { name: "Open work queue" })).toHaveAttribute("href", "/teams/crioc/queue");
    expect(await screen.findByText("Received in 30 days")).toBeInTheDocument();
  });

  it("keeps detailed statistics inside the workspace and supports legacy access metadata", async () => {
    mockRoutingApi({ access: { unitKind: undefined, workspacePosition: undefined } });
    renderApp("/teams/crioc/statistics");

    expect(await screen.findByRole("heading", { name: "Operational statistics" })).toBeInTheDocument();
    expect(screen.getByText("CRIOC · authorised")).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Team service measures" })).toBeInTheDocument();
  });

  it("recovers a failed embedded queue read", async () => {
    mockRoutingApi({ workItemFailures: 1, workItems: [routingWork({ id: "available" })] });
    const user = userEvent.setup();
    renderApp("/teams/crioc/queue");

    expect(await screen.findByRole("heading", { name: "Work queue could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByText("Synthetic routing decision")).toHaveLength(2);
  });

  it("shows explicit zeroes when a routing workspace has no recorded activity", async () => {
    mockRoutingApi({ omitMemberCount: true, statisticsSummary: [] });
    renderApp("/teams/crioc/overview");

    expect((await screen.findByText("Members")).closest("div")).toHaveTextContent("0");
    const measures = await screen.findByRole("region", { name: "Team service measures" });
    expect(within(measures).getByText("Received in 30 days").closest("div")).toHaveTextContent("0");
    expect(within(measures).getByText("Completed").closest("div")).toHaveTextContent("0");
    expect(within(measures).getByText("Products released").closest("div")).toHaveTextContent("0");
  });
});

type RoutingMockOptions = {
  access?: Partial<TeamWorkspaceAccess>;
  omitMemberCount?: boolean;
  onWorkItems?: (url: URL) => void;
  statisticsSummary?: Array<{ key: string; label: string; value: number; unit: string; suppressed: boolean }>;
  workItemFailures?: number;
  workItems?: WorkItem[];
};

function mockRoutingApi(options: RoutingMockOptions = {}) {
  let workItemReads = 0;
  const access = { ...managerAccess, ...options.access };
  return mockFeatureFetch((url) => {
    if (url.pathname.endsWith("/auth/me")) return json(routingManager);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
    if (url.pathname.endsWith("/team-workspaces/crioc")) return json({ access, managerCount: 1, ...(options.omitMemberCount ? {} : { memberCount: 1 }), analystCount: 0, activeWorkCount: 2, dueSoonCount: 1, overdueCount: 0 });
    if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [{ id: "scope-crioc", unitId: "crioc", name: "CRIOC", kind: "ROOT", includeDescendants: true, units: [{ id: "crioc", parentId: null, name: "CRIOC", kind: "ROOT", depth: 0 }] }] });
    if (url.pathname.endsWith("/statistics")) return json({ summary: options.statisticsSummary ?? [{ key: "received", label: "Received", value: 8, unit: "count", suppressed: false }, { key: "completed", label: "Completed", value: 3, unit: "count", suppressed: false }, { key: "released", label: "Released", value: 2, unit: "count", suppressed: false }] });
    if (url.pathname.endsWith("/work-items")) {
      options.onWorkItems?.(url);
      workItemReads += 1;
      if (workItemReads <= (options.workItemFailures ?? 0)) return json({ detail: "Unavailable" }, 503);
      return json({ items: options.workItems ?? [], nextCursor: null });
    }
    if (url.pathname.endsWith("/calendar")) return json({ items: [] });
    if (url.pathname.endsWith("/activity")) return json({ items: [] });
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, false, false);
}

function routingWork(overrides: Partial<WorkItem>): WorkItem {
  return {
    id: "work-1",
    requestId: "request-1",
    requestReference: "REQ-001",
    requestVersion: 1,
    title: "Synthetic routing decision",
    stage: "TRIAGE_REVIEW",
    status: "AVAILABLE",
    assigneeId: null,
    assigneeDisplayName: null,
    deliveryTeam: null,
    availableActions: ["progress"],
    createdAt: "2026-08-09T09:00:00Z",
    updatedAt: "2026-08-09T09:00:00Z",
    ...overrides,
  };
}
