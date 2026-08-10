import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ModalDrawer } from "../../components/ModalDrawer";
import type { BoardFilters, BoardItem, WorkPackage } from "../../lib/api/boardTypes";
import type { PlanningCockpit } from "../../lib/api/planningEvolutionTypes";
import { TestProviders } from "../../test/render";
import {
  boardLabel,
  boardPresetFilters,
  builtInBoardViews,
  daysInState,
  dueSignal,
  filtersActive,
} from "./boardPresentation";
import { BoardSurface } from "./BoardSurface";
import { WorkItemInspector } from "./WorkItemInspector";

const emptyBoardFilters: BoardFilters = {
  search: "",
  columns: [],
  priorities: [],
  ownerUserId: null,
  itemTypes: [],
  dueBefore: null,
};

const requestItem: BoardItem = {
  id: "request-blocked",
  itemType: "SERVICE_REQUEST",
  reference: "REQ-101",
  title: "Blocked customer request",
  column: "BLOCKED",
  priority: "URGENT",
  dueOn: "2020-01-01",
  ownerUserId: null,
  ownerDisplayName: null,
  version: 1,
  linkedRequestId: "request-blocked",
  availableColumns: [],
  changedAt: "2999-01-01T00:00:00Z",
};

const packageItem: BoardItem = {
  ...requestItem,
  id: "package-rich",
  itemType: "WORK_PACKAGE",
  reference: "WP-101",
  title: "Rich work package",
  column: "READY",
  dueOn: new Date().toISOString().slice(0, 10),
  ownerUserId: "analyst-one",
  ownerDisplayName: "Analyst One",
  linkedRequestId: null,
  availableColumns: ["IN_PROGRESS", "BLOCKED"],
  changedAt: new Date(Date.now() - 86_400_000).toISOString(),
};

const richPackage: WorkPackage = {
  id: packageItem.id,
  teamId: "team-one",
  linkedRequestId: "request-one",
  iterationId: "iteration-one",
  title: packageItem.title,
  description: "A complete synthetic package description.",
  ownerUserId: "analyst-one",
  ownerDisplayName: "Analyst One",
  contributors: [{ userId: "analyst-two", displayName: "Analyst Two" }],
  estimatePoints: 5,
  remainingEffortMinutes: 120,
  dueOn: packageItem.dueOn,
  priority: "HIGH",
  status: "READY",
  blockers: "A synthetic dependency.",
  acceptanceCriteria: "All synthetic checks pass.",
  dependencyIds: ["dependency-known", "dependency-missing"],
  version: 1,
  activities: [{ id: "activity-one", type: "CREATED", summary: "Package created", actorDisplayName: "Manager One", createdAt: "2026-08-01T09:00:00Z" }],
  reservations: [
    { id: "reservation-one", userId: "analyst-one", userDisplayName: "Analyst One", startsAt: "2026-08-11T09:00:00Z", endsAt: "2026-08-11T11:00:00Z", minutes: 90, status: "ACTIVE", reason: "Synthetic delivery", version: 1 },
    { id: "reservation-old", userId: "analyst-one", userDisplayName: "Analyst One", startsAt: "2026-08-01T09:00:00Z", endsAt: "2026-08-01T10:00:00Z", minutes: 60, status: "CANCELLED", reason: "Superseded", version: 2 },
  ],
};

const dependencyPackage: WorkPackage = {
  ...richPackage,
  id: "dependency-known",
  title: "Known dependency",
  dependencyIds: [],
  activities: [],
  reservations: [],
};

const planning: PlanningCockpit = {
  teamId: "team-one",
  generatedAt: "2026-08-10T09:00:00Z",
  advisoryOnly: true,
  freshness: { health: "READY", label: "Current", sourceVersion: 1 },
  summary: { backlogCount: 1, activeIterationCount: 1, dueRiskCount: 1, wipCount: 1, blockedCount: 1, availableMinutes: 300, reservedMinutes: 90 },
  lanes: [{ key: "ready", label: "Ready", items: [{ id: packageItem.id, kind: "PACKAGE", reference: packageItem.reference, title: packageItem.title, ownerDisplayName: "Analyst One", priority: "HIGH", dueOn: packageItem.dueOn, status: "READY", iterationName: "Iteration one", blockerAgeDays: 1, dependencyWarningCount: 1 }] }],
  blockers: [],
  dependencies: [{ packageId: packageItem.id, reference: packageItem.reference, title: packageItem.title, dependencyReference: "WP-100", status: "AT_RISK", warning: "Dependency is at risk." }],
  iteration: null,
  checklists: [{ packageId: packageItem.id, packageTitle: packageItem.title, templateName: "Standard", completedCount: 1, totalCount: 2, items: [{ id: "check-one", label: "Complete", required: true, completed: true }, { id: "check-two", label: "Outstanding", required: false, completed: false }] }],
};

describe("board operational components", () => {
  it("covers presentation boundaries and every built-in view", () => {
    const now = new Date("2026-08-10T12:00:00Z");
    expect(boardLabel("IN_PROGRESS")).toBe("In Progress");
    expect(daysInState(now.toISOString(), now)).toBe("Changed today");
    expect(daysInState("2026-08-09T12:00:00Z", now)).toBe("1 day in state");
    expect(daysInState("2026-08-01T12:00:00Z", now)).toBe("9 days in state");
    expect(dueSignal("2026-08-09", now).label).toBe("Overdue");
    expect(dueSignal("2026-08-10", now).label).toBe("Due today");
    expect(dueSignal("2026-08-14", now).label).toBe("Due soon");
    expect(dueSignal("2026-09-01", now).label).toBe("Scheduled");
    expect(builtInBoardViews("user-one", now)).toHaveLength(6);
    expect(boardPresetFilters("blocked", "user-one").columns).toEqual(["BLOCKED"]);
    expect(boardPresetFilters("unknown", "user-one")).toEqual(emptyBoardFilters);
    expect(filtersActive(emptyBoardFilters)).toBe(false);
    for (const filters of [
      { ...emptyBoardFilters, search: "work" },
      { ...emptyBoardFilters, columns: ["READY" as const] },
      { ...emptyBoardFilters, priorities: ["HIGH"] },
      { ...emptyBoardFilters, ownerUserId: "user-one" },
      { ...emptyBoardFilters, itemTypes: ["WORK_PACKAGE" as const] },
      { ...emptyBoardFilters, dueBefore: "2026-08-12" },
    ]) expect(filtersActive(filters)).toBe(true);
  });

  it("renders focused, exception, archive and tabular board states", async () => {
    const inspect = vi.fn();
    const toggles = { archive: vi.fn(), exceptions: vi.fn() };
    const props = {
      columnCounts: { READY: 1, BLOCKED: 3, QUALITY_REVIEW: 1, COMPLETED: 2 },
      context: { packages: [richPackage], planning },
      filteredColumns: [],
      items: [requestItem, packageItem],
      mode: "board" as const,
      onInspect: inspect,
      showArchive: true,
      showExceptions: true,
      totalCount: 7,
      wipLimits: { READY: 1, BLOCKED: 2 },
      onShowArchive: toggles.archive,
      onShowExceptions: toggles.exceptions,
    };
    const view = render(<BoardSurface {...props} />);
    expect(screen.getByRole("status")).toHaveTextContent("exceeded by 1");
    expect(screen.getByText("Waiting for customer")).toBeInTheDocument();
    expect(screen.getByText("1 dependency warning")).toBeInTheDocument();
    expect(screen.getByText("1/2 checklist")).toBeInTheDocument();
    expect(screen.getByText("1.5h reserved")).toBeInTheDocument();
    expect(screen.getByText("With Analyst Two")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Completed and cancelled/ }));
    expect(toggles.archive).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: /Rich work package/ }));
    expect(inspect).toHaveBeenCalledWith(packageItem);

    view.rerender(<BoardSurface {...props} filteredColumns={["READY"]} showArchive={false} showExceptions={false} />);
    expect(screen.queryByText("Exceptions and downstream")).not.toBeInTheDocument();
    view.rerender(<BoardSurface {...props} mode="table" />);
    expect(screen.getByRole("table")).toHaveTextContent("Unassigned");
    await userEvent.click(within(screen.getByRole("table")).getByRole("button", { name: requestItem.title }));
    expect(inspect).toHaveBeenCalledWith(requestItem);
  });

  it("supports drawer cancellation, backdrop close and focus return", () => {
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const view = render(<ModalDrawer label="Test drawer" onClose={onClose} open><p>Detail</p></ModalDrawer>);
    const dialog = screen.getByRole("dialog", { name: "Test drawer" });
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    fireEvent.click(dialog);
    fireEvent.click(screen.getByRole("button", { name: "Close Test drawer" }));
    expect(onClose).toHaveBeenCalledTimes(3);
    view.unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("shows rich and missing package inspector context", async () => {
    const move = vi.fn();
    const user = userEvent.setup();
    const wrapper = (children: React.ReactNode) => <TestProviders><MemoryRouter>{children}</MemoryRouter></TestProviders>;
    const view = render(wrapper(<WorkItemInspector item={packageItem} moving packages={[]} teamId="team-one" userId="user-one" onClose={vi.fn()} onMove={move} />));
    expect(screen.getByRole("heading", { name: "Package detail is not on this page" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open in Planning" })).toBeInTheDocument();

    view.rerender(wrapper(<WorkItemInspector item={{ ...packageItem, linkedRequestId: "request-one" }} moving={false} packages={[richPackage, dependencyPackage]} planning={planning} teamId="team-one" userId="user-one" onClose={vi.fn()} onMove={move} />));
    expect(screen.getByText("Known dependency")).toBeInTheDocument();
    expect(screen.getByText("dependency-missing")).toBeInTheDocument();
    expect(screen.queryByText("No activity recorded.")).not.toBeInTheDocument();
    expect(screen.getByText("Dependency is at risk.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Outstanding")).toBeInTheDocument();
    expect(screen.getByText(/Analyst One: 90 minutes/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Move package to/), "BLOCKED");
    await user.type(screen.getByLabelText(/^Reason/), "A complete synthetic movement reason.");
    await user.click(screen.getByRole("button", { name: "Move package" }));
    expect(move).toHaveBeenCalledWith(expect.objectContaining({ id: packageItem.id }), "BLOCKED", "A complete synthetic movement reason.");
  });

  it("shows empty package facts without inventing operational context", () => {
    const emptyPackage: WorkPackage = { ...richPackage, id: "package-empty", iterationId: null, contributors: [], dependencyIds: [], activities: [], reservations: [] };
    const emptyItem = { ...packageItem, id: emptyPackage.id, availableColumns: [] };
    render(<TestProviders><MemoryRouter><WorkItemInspector item={emptyItem} moving={false} packages={[emptyPackage]} teamId="team-one" userId="user-one" onClose={vi.fn()} onMove={vi.fn()} /></MemoryRouter></TestProviders>);
    expect(screen.getByText("No dependencies recorded.")).toBeInTheDocument();
    expect(screen.getByText("No checklist is attached.")).toBeInTheDocument();
    expect(screen.getByText("No active reservations.")).toBeInTheDocument();
    expect(screen.getByText("No activity recorded.")).toBeInTheDocument();
    expect(screen.getByText("Not assigned")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Move package to/)).not.toBeInTheDocument();
  });
});
