import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ModalDrawer } from "../../components/ModalDrawer";
import type { WorkPackage } from "../../lib/api/boardTypes";
import { requesterSession } from "../../test/fixtures";
import { TestProviders } from "../../test/render";
import { access, dependencyPackage, packageItem, richPackage } from "./boardOperationsTestSupport";
import { WorkItemInspector } from "./WorkItemInspector";

describe("work item inspector", () => {
  it("supports drawer cancellation, backdrop close and focus return", () => {
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const view = render(
      <ModalDrawer label="Test drawer" onClose={onClose} open>
        <p>Detail</p>
      </ModalDrawer>,
    );
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
    const wrapper = (children: React.ReactNode) => (
      <TestProviders>
        <MemoryRouter>{children}</MemoryRouter>
      </TestProviders>
    );
    const view = render(
      wrapper(
        <WorkItemInspector
          access={access}
          item={packageItem}
          moving
          packages={[]}
          session={requesterSession}
          userId="user-one"
          onClose={vi.fn()}
          onMove={move}
        />,
      ),
    );
    expect(
      screen.getByRole("heading", { name: "Package detail is not on this page" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Refresh the board to load the current package detail."),
    ).toBeInTheDocument();

    view.rerender(
      wrapper(
        <WorkItemInspector
          access={access}
          item={{ ...packageItem, linkedRequestId: "request-one" }}
          moving={false}
          packages={[richPackage, dependencyPackage]}
          session={requesterSession}
          userId="user-one"
          onClose={vi.fn()}
          onMove={move}
        />,
      ),
    );
    expect(screen.getByText("Known dependency")).toBeInTheDocument();
    expect(screen.getByText("dependency-missing")).toBeInTheDocument();
    expect(screen.queryByText("No activity recorded.")).not.toBeInTheDocument();
    expect(screen.getByText(/Analyst One: 90 minutes/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Move package to/), "BLOCKED");
    await user.type(screen.getByLabelText(/^Reason/), "A complete synthetic movement reason.");
    await user.click(screen.getByRole("button", { name: "Move package" }));
    expect(move).toHaveBeenCalledWith(
      expect.objectContaining({ id: packageItem.id }),
      "BLOCKED",
      "A complete synthetic movement reason.",
    );
  });

  it("shows empty package facts without inventing operational context", () => {
    const emptyPackage: WorkPackage = {
      ...richPackage,
      id: "package-empty",
      iterationId: null,
      contributors: [],
      dependencyIds: [],
      activities: [],
      reservations: [],
    };
    const emptyItem = { ...packageItem, id: emptyPackage.id, availableColumns: [] };
    render(
      <TestProviders>
        <MemoryRouter>
          <WorkItemInspector
            access={access}
            item={emptyItem}
            moving={false}
            packages={[emptyPackage]}
            session={requesterSession}
            userId="user-one"
            onClose={vi.fn()}
            onMove={vi.fn()}
          />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(screen.getByText("No dependencies recorded.")).toBeInTheDocument();
    expect(screen.getByText("No active reservations.")).toBeInTheDocument();
    expect(screen.getByText("No activity recorded.")).toBeInTheDocument();
    expect(screen.getByText("Not assigned")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Move package to/)).not.toBeInTheDocument();
  });
});
