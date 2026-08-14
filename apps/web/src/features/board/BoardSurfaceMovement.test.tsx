import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BoardSurface } from "./BoardSurface";
import { packageItem, requestItem, richPackage } from "./boardOperationsTestSupport";

describe("board surface movement", () => {
  it("moves a work package by drag and drop with a recorded reason, leaving requests fixed", async () => {
    const move = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    const props = {
      columnCounts: { READY: 1, BLOCKED: 3 },
      context: { packages: [richPackage] },
      filteredColumns: [],
      items: [requestItem, packageItem],
      mode: "board" as const,
      moving: false,
      onInspect: vi.fn(),
      onMove: move,
      showArchive: false,
      showExceptions: false,
      totalCount: 2,
      wipLimits: {},
      onShowArchive: vi.fn(),
      onShowExceptions: vi.fn(),
    };
    render(<BoardSurface {...props} />);
    const requestCard = screen
      .getByText("Blocked customer request")
      .closest("article") as HTMLElement;
    expect(requestCard).not.toHaveAttribute("draggable", "true");
    const packageCard = screen.getByText("Rich work package").closest("article") as HTMLElement;
    expect(packageCard).toHaveAttribute("draggable", "true");
    const inProgress = screen
      .getByRole("heading", { name: "In Progress" })
      .closest(".kanban-column") as HTMLElement;

    fireEvent.dragStart(packageCard);
    expect(screen.getAllByText("Drop here to move")).toHaveLength(2);
    fireEvent.dragOver(inProgress);
    fireEvent.drop(inProgress);

    const dialog = await screen.findByRole("dialog", { name: "Confirm package move" });
    expect(dialog).toHaveTextContent("In Progress");
    const confirm = within(dialog).getByRole("button", { name: "Move to In Progress" });
    expect(confirm).toBeDisabled();
    await user.type(
      within(dialog).getByLabelText(/^Reason/),
      "Sources are gathered so this is ready for active work.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Move to In Progress" }));
    expect(move).toHaveBeenCalledWith(
      packageItem,
      "IN_PROGRESS",
      "Sources are gathered so this is ready for active work.",
    );
  });

  it("moves a work package from the card menu with the same recorded reason", async () => {
    const move = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <BoardSurface
        columnCounts={{ READY: 1 }}
        context={{ packages: [richPackage] }}
        filteredColumns={[]}
        items={[packageItem]}
        mode="board"
        moving={false}
        onInspect={vi.fn()}
        onMove={move}
        showArchive={false}
        showExceptions={false}
        totalCount={1}
        wipLimits={{}}
        onShowArchive={vi.fn()}
        onShowExceptions={vi.fn()}
      />,
    );
    const toggle = screen.getByRole("button", { name: "Move Rich work package" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Move to Blocked" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm package move" });
    await user.type(
      within(dialog).getByLabelText(/^Reason/),
      "The dependency is outstanding so this work is blocked.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Move to Blocked" }));
    expect(move).toHaveBeenCalledWith(
      packageItem,
      "BLOCKED",
      "The dependency is outstanding so this work is blocked.",
    );
  });
});
