import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type {
  CapacityScenarioPreview,
  PackageTemplate,
  PlanningCockpit,
} from "../../lib/api/planningEvolutionTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { requesterSession } from "../../test/fixtures";
import { json, mockFetch, TestProviders } from "../../test/render";
import { PlanningCockpit as PlanningCockpitView } from "./PlanningCockpit";
import { PlanningEnhancements } from "./PlanningEnhancements";

const session: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-ssg",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "SSG Team",
  },
};
const access: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  grantId: "grant-ssg",
  permissions: ["BOARD", "CAPACITY"],
};
const cockpit: PlanningCockpit = {
  teamId: access.teamId,
  generatedAt: "2026-08-07T10:30:00Z",
  advisoryOnly: true,
  freshness: { health: "READY", label: "Projection current", sourceVersion: 7 },
  summary: {
    backlogCount: 4,
    activeIterationCount: 1,
    dueRiskCount: 2,
    wipCount: 3,
    blockedCount: 1,
    availableMinutes: 1_800,
    reservedMinutes: 420,
  },
  lanes: [
    {
      key: "owner",
      label: "Lewis Ferguson",
      items: [
        {
          id: "package-one", kind: "PACKAGE", reference: "PKG-101",
          title: "Prepare fictional product", ownerDisplayName: "Lewis Ferguson",
          priority: "HIGH", dueOn: "2026-08-14", status: "BLOCKED",
          iterationName: "Pilot iteration", blockerAgeDays: 3,
          dependencyWarningCount: 1,
        },
        {
          id: "package-two", kind: "PACKAGE", reference: "PKG-102",
          title: "Confirm delivery window", ownerDisplayName: null,
          priority: "MEDIUM", dueOn: "2026-08-16", status: "READY",
          iterationName: null, blockerAgeDays: null, dependencyWarningCount: 0,
        },
        {
          id: "package-three", kind: "PACKAGE", reference: "PKG-103",
          title: "Resolve package dependencies", ownerDisplayName: "Lewis Ferguson",
          priority: "HIGH", dueOn: "2026-08-18", status: "READY",
          iterationName: "Pilot iteration", blockerAgeDays: null,
          dependencyWarningCount: 2,
        },
      ],
    },
    { key: "unassigned", label: "Unassigned", items: [] },
  ],
  blockers: [{ packageId: "package-one", reference: "PKG-101", title: "Prepare fictional product", ageDays: 3, reason: "Waiting for a fictional dependency." }],
  dependencies: [{ packageId: "package-one", reference: "PKG-101", title: "Prepare fictional product", dependencyReference: "PKG-099", status: "AT_RISK", warning: "Dependency is due after this package." }],
  iteration: {
    id: "iteration-one",
    name: "Pilot iteration",
    goal: "Complete the agreed fictional service product.",
    startsOn: "2026-08-01",
    endsOn: "2026-08-14",
    status: "ACTIVE",
    committedPoints: 10,
    completedPoints: 4,
    committedPackages: 3,
    completedPackages: 1,
    factualSummary: null,
  },
  checklists: [{
    packageId: "package-one",
    packageTitle: "Prepare fictional product",
    templateName: "Standard product",
    completedCount: 1,
    totalCount: 2,
    items: [
      { id: "check-one", label: "Confirm requirements", required: true, completed: true },
      { id: "check-two", label: "Record review notes", required: false, completed: false },
    ],
  }],
};
const templates: PackageTemplate[] = [{
  id: "template-one",
  name: "Standard product",
  description: "A reusable fictional delivery checklist.",
  version: 2,
  checklist: [
    { id: "template-check", label: "Confirm requirements", required: true },
    { id: "template-optional", label: "Add optional supporting note", required: false },
  ],
}];
const scenarios = [{ id: "scenario-one", name: "Pilot week", version: 2, startsOn: "2026-08-08", endsOn: "2026-08-14", status: "PREVIEWED" as const, updatedAt: "2026-08-07T10:00:00Z" }];

describe("planning cockpit enhancements", () => {
  it("shows advisory cockpit, templates, risks and keyboard-operated scenario previews", async () => {
    const previewBodies: Array<Record<string, unknown>> = [];
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/planning/cockpit")) return json(cockpit);
      if (url.pathname.endsWith("/planning/templates")) return json({ items: templates });
      if (url.pathname.endsWith("/planning/scenarios") && !init.method) return json({ items: scenarios });
      if (url.pathname.endsWith("/planning/scenarios/preview")) {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        previewBodies.push(body);
        return json(preview(body.plannedMinutes === 120));
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = render(<TestProviders><PlanningEnhancements access={access} session={session} /></TestProviders>);

    expect(await screen.findByRole("heading", { name: "Planning cockpit" })).toBeInTheDocument();
    expect(screen.getByText("Advice only. Human decisions remain explicit.")).toBeInTheDocument();
    expect(screen.getByText("3 blocked days · 1 dependency warnings")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");

    await user.click(screen.getByRole("button", { name: "Templates & checklists" }));
    expect(screen.getByText("A reusable fictional delivery checklist.")).toBeInTheDocument();
    expect(screen.getByText("Record review notes")).toBeInTheDocument();
    expect(screen.getByText("Add optional supporting note")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Blockers & dependencies" }));
    expect(screen.getByRole("table", { name: "Current package blockers" })).toHaveTextContent("3 days");
    expect(screen.getByRole("table", { name: "Current dependency warnings" })).toHaveTextContent("AT_RISK");

    await user.click(screen.getByRole("button", { name: "Capacity scenarios" }));
    expect(screen.getByRole("table", { name: "Team capacity scenarios" })).toHaveTextContent("Pilot week");
    await user.type(screen.getByLabelText(/^Scenario name/), "Busy week");
    await user.type(screen.getByLabelText(/^Planned team hours/), "12");
    await user.click(screen.getByRole("button", { name: "Preview scenario" }));
    expect(await screen.findByText("RESERVATION")).toBeInTheDocument();
    expect(previewBodies[0]).toMatchObject({ grantId: "grant-ssg", expectedSourceVersion: 7, plannedMinutes: 720 });

    await user.clear(screen.getByLabelText(/^Planned team hours/));
    await user.type(screen.getByLabelText(/^Planned team hours/), "2");
    await user.click(screen.getByRole("button", { name: "Preview scenario" }));
    expect(await screen.findByText(/No capacity conflicts identified/)).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("keeps preview authority and empty planning states explicit", async () => {
    const analystAccess = { ...access, grantId: null, permissions: [] as TeamWorkspaceAccess["permissions"] };
    const view = render(<TestProviders><PlanningCockpitView access={analystAccess} cockpit={{ ...cockpit, freshness: { ...cockpit.freshness, health: "STALE" }, lanes: [{ key: "empty", label: "No owner", items: [] }], blockers: [], dependencies: [], iteration: null, checklists: [] }} scenarios={[]} session={session} templates={[]} /></TestProviders>);
    expect(screen.getByText("No work in this lane.")).toBeInTheDocument();
    expect(screen.getByText("No active iteration.")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Templates & checklists" }));
    expect(screen.getByText("No package templates are active.")).toBeInTheDocument();
    expect(screen.getByText("No package checklists are in use.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Blockers & dependencies" }));
    expect(screen.getAllByText("No current records.")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Capacity scenarios" }));
    expect(screen.getByText("No scenarios have been recorded.")).toBeInTheDocument();
    expect(screen.getByText(/current exact-team board and capacity grant/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Preview scenario" })).not.toBeInTheDocument();
    view.rerender(<TestProviders><PlanningCockpitView key="zero-iteration" access={analystAccess} cockpit={{ ...cockpit, iteration: { ...cockpit.iteration!, committedPoints: 0, completedPoints: 0, factualSummary: "No committed work entered this iteration." } }} scenarios={[]} session={session} templates={[]} /></TestProviders>);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByText("No committed work entered this iteration.")).toBeInTheDocument();
  });

  it("retries an unavailable cockpit without changing core planning", async () => {
    let attempts = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/planning/cockpit")) { attempts += 1; return attempts === 1 ? json({ detail: "Unavailable" }, 503) : json(cockpit); }
      if (url.pathname.endsWith("/planning/templates")) return json({ items: templates });
      if (url.pathname.endsWith("/planning/scenarios")) return json({ items: scenarios });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    render(<TestProviders><PlanningEnhancements access={access} session={session} /></TestProviders>);
    expect(await screen.findByRole("heading", { name: "Core planning remains available" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try cockpit again" }));
    expect(await screen.findByRole("heading", { name: "Planning cockpit" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Capacity scenarios" }));
    await user.type(screen.getByLabelText(/^Scenario name/), "Failed preview");
    await user.type(screen.getByLabelText(/^Planned team hours/), "4");
    await user.click(screen.getByRole("button", { name: "Preview scenario" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unexpected /api/v1/team-workspaces/team-ssg/planning/scenarios/preview");
  });
});

function preview(clear: boolean): CapacityScenarioPreview {
  const baseline = { availableMinutes: 2_400, reservedMinutes: 300, requestWorkMinutes: 600, packageMinutes: 300, netMinutes: 1_200 };
  return {
    token: "preview-token",
    expiresAt: "2026-08-07T11:00:00Z",
    sourceVersion: 7,
    baseline,
    scenario: { ...baseline, packageMinutes: clear ? 120 : 720, netMinutes: clear ? 1_380 : 780 },
    conflicts: clear ? [] : [{ date: "2026-08-10", kind: "RESERVATION", summary: "Existing package time overlaps the scenario." }],
    estimateLabel: "Aggregate planning estimate",
  };
}
