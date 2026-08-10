import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type { TeamWorkspaceAccess, WorkspaceRecord } from "../../lib/api/teamTypes";
import type { WorkItem } from "../../lib/api/workTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const routingManager: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-jioc",
    username: "admin74",
    displayName: "Alan Rough",
    role: "INTAKE_TRIAGE",
    scope: "JIOC",
  },
};
const routingMember: Session = {
  ...routingManager,
  user: {
    ...routingManager.user,
    id: "member-jioc",
    username: "admin75",
    displayName: "Willie Ormond",
  },
};
const managerAccess: TeamWorkspaceAccess = {
  teamId: "jioc",
  teamCode: "JIOC",
  teamName: "JIOC",
  unitKind: "ROOT",
  workspacePosition: "MANAGER",
  grantId: "grant-jioc",
  permissions: ["STATISTICS", "ROSTER", "CALENDAR"],
  views: ["OVERVIEW", "QUEUE", "CALENDAR", "PEOPLE", "STATISTICS", "HANDOVER", "ACTIVITY"],
};

describe("routing organisation workspace", () => {
  it("presents claim-based queue decisions without a manager approval layer", async () => {
    mockRoutingApi(routingManager, managerAccess);
    const view = renderApp("/teams/jioc/queue");
    expect(await screen.findByRole("heading", { name: "Current queue" })).toBeInTheDocument();
    expect(screen.getByText(/Manager status does not add an approval stage/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open routing actions" })).toHaveAttribute("href", "/triage");
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("lets a routing Manager create and resolve bounded handover context", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    mockRoutingApi(routingManager, managerAccess, bodies);
    const user = userEvent.setup();
    renderApp("/teams/jioc/handover");
    expect(await screen.findByRole("heading", { name: "Handover and decisions" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/^Record type/), "RISK");
    await user.type(screen.getByLabelText(/^Title/), "Synthetic routing risk");
    await user.type(screen.getByLabelText(/^Detail/), "A downstream decision may need additional context.");
    await user.click(screen.getByRole("button", { name: "Add record" }));
    expect(await screen.findByText("Synthetic routing risk")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Resolution/), "The additional context was supplied and accepted.");
    await user.click(screen.getByRole("button", { name: "Resolve record" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[0]).toMatchObject({ kind: "RISK", grantId: "grant-jioc" });
    expect(bodies[1]).toMatchObject({ expectedVersion: 1, grantId: "grant-jioc" });
  });

  it("gives a routing Member calendar self-service without unit controls", async () => {
    const memberAccess = { ...managerAccess, workspacePosition: "MEMBER" as const, grantId: null, permissions: [] };
    mockRoutingApi(routingMember, memberAccess);
    const user = userEvent.setup();
    renderApp("/teams/jioc/calendar");
    await user.click(await screen.findByRole("button", { name: "Add event" }));
    expect(await screen.findByRole("heading", { name: "Add calendar activity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "My event" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unit event" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ticket commitment" })).not.toBeInTheDocument();
    expect(within(screen.getByLabelText(/^Category/)).getByRole("option", { name: "LEAVE" })).toBeInTheDocument();
  });

  it("summarises the routing unit and its authorised descendant statistics", async () => {
    mockRoutingApi(routingManager, managerAccess, [], { workItems: [
      routingWork({ id: "available" }),
      routingWork({ id: "mine", assigneeId: "manager-jioc", assigneeDisplayName: "Alan Rough", stage: "INFORMATION_REQUIRED" }),
    ] });
    renderApp("/teams/jioc/overview");
    expect(await screen.findByRole("heading", { name: "JIOC" })).toBeInTheDocument();
    expect(screen.getByText("Shared routing workspace for queue decisions, people, calendar, statistics and handover.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Routing decisions" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Available to claim").closest("div")).toHaveTextContent("1"));
    expect(screen.getByText("Claimed by you").closest("div")).toHaveTextContent("1");
    const decisions = screen.getByRole("region", { name: "Routing decisions" });
    expect(within(decisions).getByText("Information required").closest("div")).toHaveTextContent("1");
    expect(screen.getByRole("heading", { name: "Current stages" })).toBeInTheDocument();
    expect(await screen.findByText("Received in 30 days")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Full statistics" })).toHaveAttribute("href", "/statistics?scopeId=scope-jioc&unitId=jioc");
    expect(screen.getByRole("link", { name: "Open routing queue" })).toHaveAttribute("href", "/triage");
  });

  it("shows claimed and available routing work and recovers a failed queue read", async () => {
    const workItems: WorkItem[] = [
      routingWork({ id: "available", assigneeId: null, assigneeDisplayName: null }),
      routingWork({ id: "claimed", assigneeId: "member-jioc", assigneeDisplayName: null }),
    ];
    mockRoutingApi(routingManager, managerAccess, [], { workItems, workItemFailures: 1 });
    const user = userEvent.setup();
    renderApp("/teams/jioc/queue");
    expect(await screen.findByRole("heading", { name: "Routing queue could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("table", { name: "Current routing work visible to you" })).toBeInTheDocument();
    expect(screen.getByText("Available to claim")).toBeInTheDocument();
    expect(screen.getByText("Claimed")).toBeInTheDocument();
  });

  it("keeps routing workspace records readable to Members without management controls", async () => {
    const memberAccess = { ...managerAccess, workspacePosition: "MEMBER" as const, grantId: null, permissions: [] };
    const records: WorkspaceRecord[] = [
      { id: "link-1", kind: "LINK", status: "RESOLVED", title: "Reference service", body: "A public-safe operating reference.", url: "https://example.test/reference", createdByDisplayName: "Alan Rough", resolution: "The reference was incorporated into the handover.", version: 2, createdAt: "2026-08-09T09:00:00Z", updatedAt: "2026-08-09T10:00:00Z" },
    ];
    mockRoutingApi(routingMember, memberAccess, [], { records });
    renderApp("/teams/jioc/handover");
    expect(await screen.findByRole("link", { name: "Open useful link" })).toHaveAttribute("href", "https://example.test/reference");
    expect(screen.getByText(/The reference was incorporated/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add shared context" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve record" })).not.toBeInTheDocument();
  });

  it("recovers an unavailable collaboration register and reports write conflicts", async () => {
    mockRoutingApi(routingManager, managerAccess, [], { recordFailures: 1, mutationFailure: true });
    const user = userEvent.setup();
    renderApp("/teams/jioc/handover");
    expect(await screen.findByRole("heading", { name: "Workspace records could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No workspace records" })).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Title/), "Conflicting handover record");
    await user.type(screen.getByLabelText(/^Detail/), "This synthetic write is rejected to exercise conflict handling.");
    await user.click(screen.getByRole("button", { name: "Add record" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic collaboration conflict");
  });

  it("stores useful links and keeps failed resolutions open for retry", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    mockRoutingApi(routingManager, managerAccess, bodies, { resolveFailure: true });
    const user = userEvent.setup();
    renderApp("/teams/jioc/handover");
    await screen.findByRole("heading", { name: "Handover and decisions" });
    await user.selectOptions(screen.getByLabelText(/^Record type/), "LINK");
    await user.type(screen.getByLabelText(/^Title/), "Synthetic operating reference");
    await user.type(screen.getByLabelText(/^Detail/), "A public-safe reference for the next routing shift.");
    await user.type(screen.getByLabelText(/^HTTPS link/), "https://example.test/operating-reference");
    await user.click(screen.getByRole("button", { name: "Add record" }));
    expect(await screen.findByRole("link", { name: "Open useful link" })).toHaveAttribute(
      "href",
      "https://example.test/operating-reference",
    );
    expect(bodies[0]).toMatchObject({ kind: "LINK", url: "https://example.test/operating-reference" });
    await user.type(screen.getByLabelText(/^Resolution/), "The reference was incorporated into the handover.");
    await user.click(screen.getByRole("button", { name: "Resolve record" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic resolution conflict");
    expect(screen.getByRole("button", { name: "Resolve record" })).toBeInTheDocument();
  });

  it("shows explicit zeroes when a routing workspace has no recorded activity", async () => {
    mockRoutingApi(routingManager, managerAccess, [], { omitMemberCount: true, statisticsSummary: [] });
    renderApp("/teams/jioc/overview");
    expect(await screen.findByRole("heading", { name: "JIOC" })).toBeInTheDocument();
    expect((await screen.findByText("Members")).closest("div")).toHaveTextContent("0");
    const serviceMeasures = await screen.findByRole("region", { name: "Team service measures" });
    expect(within(serviceMeasures).getByText("Received in 30 days").closest("div")).toHaveTextContent("0");
    expect(within(serviceMeasures).getByText("Completed").closest("div")).toHaveTextContent("0");
    expect(within(serviceMeasures).getByText("Products released").closest("div")).toHaveTextContent("0");
  });
});

type RoutingMockOptions = {
  mutationFailure?: boolean;
  omitMemberCount?: boolean;
  recordFailures?: number;
  records?: WorkspaceRecord[];
  resolveFailure?: boolean;
  statisticsSummary?: Array<{ key: string; label: string; value: number; unit: string; suppressed: boolean }>;
  workItemFailures?: number;
  workItems?: WorkItem[];
};

function mockRoutingApi(
  session: Session,
  access: TeamWorkspaceAccess,
  bodies: Array<Record<string, unknown>> = [],
  options: RoutingMockOptions = {},
) {
  let records: WorkspaceRecord[] = options.records ?? [];
  let recordReads = 0;
  let workItemReads = 0;
  return mockFeatureFetch(async (url, init) => {
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
    if (url.pathname.endsWith(`/team-workspaces/${access.teamId}`)) return json({ access, managerCount: 1, ...(options.omitMemberCount ? {} : { memberCount: 1 }), analystCount: 0, activeWorkCount: 2, dueSoonCount: 1, overdueCount: 0 });
    if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [{ id: "scope-jioc", unitId: "jioc", name: "JIOC", kind: "ROOT", includeDescendants: true, units: [{ id: "jioc", parentId: null, name: "JIOC", kind: "ROOT", depth: 0 }] }] });
    if (url.pathname.endsWith("/statistics")) return json({ summary: options.statisticsSummary ?? [{ key: "received", label: "Received", value: 8, unit: "count", suppressed: false }, { key: "completed", label: "Completed", value: 3, unit: "count", suppressed: false }, { key: "released", label: "Released", value: 2, unit: "count", suppressed: false }] });
    if (url.pathname.endsWith("/work-items")) {
      workItemReads += 1;
      if (workItemReads <= (options.workItemFailures ?? 0)) return json({ detail: "Unavailable" }, 503);
      return json({ items: options.workItems ?? [] });
    }
    if (url.pathname.endsWith("/calendar")) return json({ items: [] });
    if (url.pathname.endsWith("/records")) {
      if ((init.method ?? "GET") === "GET") {
        recordReads += 1;
        if (recordReads <= (options.recordFailures ?? 0)) return json({ detail: "Unavailable" }, 503);
      }
      if ((init.method ?? "GET") === "POST") {
        if (options.mutationFailure) return json({ detail: "Synthetic collaboration conflict" }, 409);
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        bodies.push(body);
        records = [{ id: "record-1", kind: body.kind as WorkspaceRecord["kind"], status: "OPEN", title: String(body.title), body: String(body.body), url: body.url ? String(body.url) : null, createdByDisplayName: session.user.displayName, resolution: null, version: 1, createdAt: "2026-08-09T09:00:00Z", updatedAt: "2026-08-09T09:00:00Z" }];
      }
      return json({ items: records });
    }
    if (url.pathname.endsWith("/resolve")) {
      if (options.resolveFailure) return json({ detail: "Synthetic resolution conflict" }, 409);
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      bodies.push(body);
      records = records.map((item) => ({ ...item, status: "RESOLVED", resolution: String(body.resolution), version: 2 }));
      return json({ items: records });
    }
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
