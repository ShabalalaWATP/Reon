import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  boardLabel,
  boardPresetFilters,
  builtInBoardViews,
  daysInState,
  dueSignal,
  filtersActive,
} from "./boardPresentation";
import { BoardSurface } from "./BoardSurface";
import { BoardToolbar } from "./BoardToolbar";
import {
  emptyBoardFilters,
  packageItem,
  requestItem,
  richPackage,
} from "./boardOperationsTestSupport";

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
    ])
      expect(filtersActive(filters)).toBe(true);
  });

  it("renders focused, exception, archive and tabular board states", async () => {
    const inspect = vi.fn();
    const toggles = { archive: vi.fn(), exceptions: vi.fn() };
    const props = {
      columnCounts: { READY: 1, BLOCKED: 3, QUALITY_REVIEW: 1, COMPLETED: 2 },
      context: { packages: [richPackage] },
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
    expect(screen.getByText("1.5h reserved")).toBeInTheDocument();
    expect(screen.getByText("With Analyst Two")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Completed and cancelled/ }));
    expect(toggles.archive).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: /Rich work package/ }));
    expect(inspect).toHaveBeenCalledWith(packageItem);

    view.rerender(
      <BoardSurface
        {...props}
        filteredColumns={["READY"]}
        showArchive={false}
        showExceptions={false}
      />,
    );
    expect(screen.queryByText("Exceptions and downstream")).not.toBeInTheDocument();
    view.rerender(<BoardSurface {...props} mode="table" />);
    expect(screen.getByRole("table")).toHaveTextContent("Unassigned");
    await userEvent.click(
      within(screen.getByRole("table")).getByRole("button", { name: requestItem.title }),
    );
    expect(inspect).toHaveBeenCalledWith(requestItem);
  });

  it("toggles the owner filter strip between one owner and everyone", async () => {
    const change = vi.fn();
    const user = userEvent.setup();
    const member = (accountId: string, displayName: string) => ({
      membershipId: `membership-${accountId}`,
      accountId,
      displayName,
      role: "DELIVERY_SPECIALIST" as const,
      state: "CURRENT" as const,
      effectiveFrom: "2026-01-01T00:00:00Z",
      effectiveUntil: null,
      version: 1,
      activeWorkCount: 0,
      skills: [],
      startReason: null,
      endReason: null,
    });
    const props = {
      canManage: false,
      canReadPeople: true,
      filters: emptyBoardFilters,
      mode: "board" as const,
      people: [member("owner-one", "Owner One"), member("owner-two", "Owner Two")],
      savedViews: [],
      saving: false,
      userId: "owner-one",
      viewName: "",
      onChange: change,
      onDeleteView: vi.fn(),
      onModeChange: vi.fn(),
      onOpenSettings: vi.fn(),
      onSaveView: vi.fn(),
      onViewNameChange: vi.fn(),
    };
    const view = render(<BoardToolbar {...props} />);
    await user.click(screen.getByRole("button", { name: "Show work owned by Owner Two" }));
    expect(change).toHaveBeenLastCalledWith({ ...emptyBoardFilters, ownerUserId: "owner-two" });
    view.rerender(
      <BoardToolbar {...props} filters={{ ...emptyBoardFilters, ownerUserId: "owner-two" }} />,
    );
    expect(screen.getByRole("button", { name: "Show work owned by Owner Two" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "Show work owned by Owner Two" }));
    expect(change).toHaveBeenLastCalledWith({ ...emptyBoardFilters, ownerUserId: null });
    await user.click(screen.getByRole("button", { name: "All" }));
    expect(change).toHaveBeenLastCalledWith({ ...emptyBoardFilters, ownerUserId: null });
  });
});
