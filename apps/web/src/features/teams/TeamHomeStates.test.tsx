import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { TeamWorkspaceAccess, TeamWorkspaceOverview } from "../../lib/api/teamTypes";
import type { WorkItem } from "../../lib/api/workTypes";
import { json, mockFetch, TestProviders } from "../../test/render";
import { staffSession } from "../../test/fixtures";
import { DeliveryTeamHome } from "./DeliveryTeamHome";
import { RoutingTeamHome } from "./RoutingTeamHome";

const deliveryAccess: TeamWorkspaceAccess = {
  teamId: "team-one",
  teamCode: "TEAM_ONE",
  teamName: "Team One",
  unitKind: "TEAM",
  workspacePosition: "MANAGER",
  grantId: "grant-one",
  permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"],
  views: ["OVERVIEW", "BOARD", "CALENDAR", "PEOPLE", "PLANNING", "STATISTICS", "ACTIVITY"],
};

const routingAccess: TeamWorkspaceAccess = {
  ...deliveryAccess,
  teamId: "routing-one",
  teamCode: "ROUTING_ONE",
  teamName: "Routing One",
  unitKind: "COMMAND",
  permissions: ["CALENDAR", "STATISTICS"],
  views: ["OVERVIEW", "QUEUE", "CALENDAR", "PEOPLE", "STATISTICS", "ACTIVITY"],
};

const managerSession = {
  ...staffSession,
  user: { ...staffSession.user, id: "manager-one" },
};

const overview = (access: TeamWorkspaceAccess): TeamWorkspaceOverview => ({
  access,
  managerCount: 1,
  memberCount: 2,
  analystCount: access.unitKind === "TEAM" ? 2 : 0,
  activeWorkCount: 3,
  dueSoonCount: 1,
  overdueCount: 1,
});

function providers(children: ReactNode) {
  return (
    <TestProviders>
      <MemoryRouter>{children}</MemoryRouter>
    </TestProviders>
  );
}

function findText(text: string) {
  return screen.findByText(text, {}, { timeout: 10_000 });
}

function occurrence() {
  return {
    eventId: "event-one",
    occurrenceStart: "2026-08-11T09:00:00Z",
    startsAt: "2026-08-11T09:00:00Z",
    endsAt: "2026-08-11T10:00:00Z",
    title: "Team course",
    notes: null,
    category: "TRAINING",
    visibility: "TEAM_DETAIL",
    kind: "TEAM",
    subjectUserId: "member-one",
    subjectDisplayName: "Member One",
    teamId: "team-one",
    allDay: false,
    timeZone: "Europe/London",
    recurrence: "NONE",
    commitmentStatus: "NOT_REQUIRED",
    version: 1,
    isException: false,
  };
}

describe("team home operational states", () => {
  it("presents focused delivery attention, people, calendar and activity", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/board"))
        return json({
          items: [],
          nextCursor: null,
          columnCounts: { AWAITING_ASSIGNMENT: 1, BLOCKED: 1, MANAGER_REVIEW: 1 },
          totalCount: 3,
          wipLimits: {},
          configurationVersion: 1,
          savedViews: [],
          generatedAt: "2026-08-10T09:00:00Z",
        });
      if (url.pathname.endsWith("/people"))
        return json({
          items: [
            {
              membershipId: "member-one",
              accountId: "member-one",
              displayName: "Member One",
              role: "DELIVERY_SPECIALIST",
              workspacePosition: undefined,
              state: "CURRENT",
              effectiveFrom: "2026-01-01T00:00:00Z",
              effectiveUntil: null,
              version: 1,
              activeWorkCount: 1,
              skills: [],
              startReason: null,
              endReason: null,
            },
            {
              membershipId: "member-two",
              accountId: "member-two",
              displayName: "Member Two",
              role: "DELIVERY_SPECIALIST",
              workspacePosition: "MEMBER",
              state: "CURRENT",
              effectiveFrom: "2026-01-01T00:00:00Z",
              effectiveUntil: null,
              version: 1,
              activeWorkCount: 2,
              skills: ["Research", "Data"],
              startReason: null,
              endReason: null,
            },
          ],
        });
      if (url.pathname.endsWith("/calendar")) return json({ items: [occurrence()] });
      if (url.pathname.endsWith("/activity"))
        return json({
          items: [
            {
              id: "activity-one",
              type: "SYNC",
              summary: "Roster synchronised",
              actorDisplayName: null,
              subjectDisplayName: "Member One",
              createdAt: "2026-08-10T09:00:00Z",
            },
          ],
        });
      throw new Error(url.pathname);
    });
    render(
      providers(
        <DeliveryTeamHome
          access={deliveryAccess}
          overview={overview(deliveryAccess)}
          session={managerSession}
        />,
      ),
    );
    expect(await findText("Team course")).toBeInTheDocument();
    expect(screen.getByText("member · 1 active work item")).toBeInTheDocument();
    expect(screen.getByText(/member · 2 active work items · Research, Data/)).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Delivery outlook" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /handover/i })).not.toBeInTheDocument();
  });

  it("keeps every delivery dependency failure explicit", async () => {
    mockFetch(() => json({ detail: "Unavailable" }, 503));
    render(
      providers(
        <DeliveryTeamHome
          access={deliveryAccess}
          overview={{ ...overview(deliveryAccess), overdueCount: 0 }}
          session={managerSession}
        />,
      ),
    );
    expect(await findText("Board attention unavailable")).toBeInTheDocument();
    expect(await findText("Calendar unavailable")).toBeInTheDocument();
    expect(await findText("People unavailable")).toBeInTheDocument();
    expect(await findText("Activity unavailable")).toBeInTheDocument();
  });

  it("states clearly when a delivery team has no recent activity", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/board"))
        return json({
          items: [],
          nextCursor: null,
          columnCounts: {},
          totalCount: 0,
          wipLimits: {},
          configurationVersion: 1,
          savedViews: [],
          generatedAt: "2026-08-10T09:00:00Z",
        });
      if (
        url.pathname.endsWith("/people") ||
        url.pathname.endsWith("/calendar") ||
        url.pathname.endsWith("/activity")
      )
        return json({ items: [] });
      throw new Error(url.pathname);
    });
    render(
      providers(
        <DeliveryTeamHome
          access={deliveryAccess}
          overview={overview(deliveryAccess)}
          session={managerSession}
        />,
      ),
    );
    expect(await findText("No recent team activity.")).toBeInTheDocument();
  });

  it("presents populated routing stages and shared unit context", async () => {
    const work = (id: string): WorkItem => ({
      id,
      requestId: id,
      requestReference: id,
      requestVersion: 1,
      title: "Synthetic decision",
      stage: "SYNTHETIC_STAGE" as WorkItem["stage"],
      status: "AVAILABLE",
      assigneeId: null,
      assigneeDisplayName: null,
      deliveryTeam: null,
      availableActions: ["progress"],
      createdAt: "2026-08-01T09:00:00Z",
      updatedAt: "2026-08-01T09:00:00Z",
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/work-items"))
        return json({ items: [work("work-one"), work("work-two")] });
      if (url.pathname.endsWith("/calendar")) return json({ items: [occurrence()] });
      if (url.pathname.endsWith("/activity"))
        return json({
          items: [
            {
              id: "activity-one",
              type: "SYNC",
              summary: "Unit synchronised",
              actorDisplayName: null,
              subjectDisplayName: "Member One",
              createdAt: "2026-08-10T09:00:00Z",
            },
          ],
        });
      throw new Error(url.pathname);
    });
    render(
      providers(
        <RoutingTeamHome
          access={routingAccess}
          overview={overview(routingAccess)}
          session={managerSession}
        />,
      ),
    );
    const stages = await screen.findByRole("heading", { name: "Current stages" });
    expect(
      await within(stages.closest("section") as HTMLElement).findByText(
        "Synthetic Stage",
        {},
        { timeout: 10_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("2 visible decisions")).toBeInTheDocument();
    expect(await findText("Team course")).toBeInTheDocument();
    expect(await findText("System")).toBeInTheDocument();
  });

  it("keeps every routing dependency failure explicit", async () => {
    mockFetch(() => json({ detail: "Unavailable" }, 503));
    render(
      providers(
        <RoutingTeamHome
          access={routingAccess}
          overview={overview(routingAccess)}
          session={managerSession}
        />,
      ),
    );
    expect(await findText("Routing queue unavailable")).toBeInTheDocument();
    expect(await findText("Calendar unavailable")).toBeInTheDocument();
    expect(await findText("Activity unavailable")).toBeInTheDocument();
  });

  it("does not present redacted descendant workload as a real zero", async () => {
    mockFetch(() => json({ items: [] }));
    render(
      providers(
        <RoutingTeamHome
          access={routingAccess}
          overview={{ ...overview(routingAccess), activeWorkCount: 0, workloadVisible: false }}
          session={managerSession}
        />,
      ),
    );

    await screen.findByRole("heading", { name: "Routing decisions" });
    expect(screen.queryByText("Active branch work")).not.toBeInTheDocument();
  });
});
