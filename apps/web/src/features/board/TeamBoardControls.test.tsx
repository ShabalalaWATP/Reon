import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { json, mockFetch, renderApp } from "../../test/render";
import {
  analystAccess,
  analystSession,
  board,
  managerAccess,
  managerSession,
  mockBoard,
  packageItem,
  people,
} from "./teamBoardTestSupport";

describe("team workflow board", () => {
  it("filters board views, pages results and updates WIP limits", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Exceptions and downstream/ }));
    await user.click(screen.getByRole("button", { name: /Completed and cancelled/ }));
    await user.click(await screen.findByRole("button", { name: "Table" }));
    expect(
      screen.getByRole("table", { name: /Service request workflow board/ }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search work"), "product");
    await user.click(screen.getByText(/Filters/));
    await user.selectOptions(screen.getByLabelText("Item type"), "WORK_PACKAGE");
    await user.selectOptions(screen.getByLabelText("Status"), "READY");
    await user.selectOptions(screen.getByLabelText("Priority"), "HIGH");
    await user.selectOptions(screen.getByLabelText("Owner"), "analyst-ssg");
    fireEvent.change(screen.getByLabelText("Due by"), { target: { value: "2026-08-31" } });
    const packageTable = await screen.findByRole("table", { name: /Work package Kanban/ });
    expect(within(packageTable).getByText("Lewis Ferguson")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Board" }));
    expect(await screen.findByRole("region", { name: "Work package Kanban" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table" }));
    await screen.findByRole("table", { name: /Work package Kanban/ });
    await user.selectOptions(screen.getByLabelText("Item type"), "");
    await screen.findByRole("table", { name: /Service request workflow board/ });
    await user.selectOptions(screen.getByLabelText("Item type"), "SERVICE_REQUEST");
    expect(screen.queryByText("Work package Kanban")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Item type"), "");
    fireEvent.change(screen.getByLabelText("Due by"), { target: { value: "" } });
    await user.selectOptions(await screen.findByLabelText("Status"), "");
    await user.selectOptions(await screen.findByLabelText("Priority"), "");
    await user.selectOptions(await screen.findByLabelText("Owner"), "");
    await screen.findByRole("table", { name: /Service request workflow board/ });
    const requestSection = screen
      .getByRole("heading", { name: "Service request board" })
      .closest("section") as HTMLElement;
    await user.click(within(requestSection).getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Page 2")).toBeInTheDocument();
    const secondPageRequestSection = screen
      .getByRole("heading", { name: "Service request board" })
      .closest("section") as HTMLElement;
    await user.click(
      within(secondPageRequestSection).getByRole("button", { name: "Previous page" }),
    );
    const refreshedRequestSection = screen
      .getByRole("heading", { name: "Service request board" })
      .closest("section") as HTMLElement;
    expect(await within(refreshedRequestSection).findByText("Page 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Board settings" }));
    const wip = (await screen.findByRole("heading", { name: "Work in progress limits" })).closest(
      "section",
    );
    await user.clear(within(wip as HTMLElement).getByLabelText("Ready"));
    await user.type(within(wip as HTMLElement).getByLabelText("Ready"), "6");
    await user.click(within(wip as HTMLElement).getByRole("button", { name: "Save limits" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) => call.path.endsWith("/board/configuration") && call.body.expectedVersion === 2,
        ),
      ).toBe(true),
    );
  });

  it("keeps Analyst controls scoped, reports empty and retries board failures", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(analystSession, analystAccess, calls, {
      ...board,
      items: [],
      columnCounts: { ...board.columnCounts, READY: 0, IN_PROGRESS: 0 },
      totalCount: 0,
      nextCursor: null,
      savedViews: [],
      wipLimits: {},
      configurationVersion: 0,
    });
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(
      await screen.findByRole("heading", { name: "No service requests match this view" }),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Work package Kanban"));
    expect(
      await screen.findByRole("heading", { name: "No work packages match this view" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Work in progress limits" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create internal card" }));
    const createCard = await screen.findByRole("dialog", { name: "Create internal card" });
    const owner = within(createCard).getByLabelText(/^Owner/);
    expect(owner).toBeDisabled();
    expect(owner).toHaveValue("analyst-ssg");
    await user.type(screen.getByLabelText(/^Title/, { selector: "input" }), "Analyst package");
    await user.type(
      screen.getByLabelText(/^Description/),
      "A complete package without optional links.",
    );
    await user.selectOptions(screen.getByLabelText(/^Contributor/), "analyst-ssg");
    fireEvent.change(screen.getByLabelText(/^Due date/), { target: { value: "2026-08-30" } });
    await user.type(screen.getByLabelText(/^Blockers or none/), "No known blockers.");
    await user.type(screen.getByLabelText(/^Acceptance criteria/), "The package is complete.");
    await user.click(screen.getByRole("button", { name: "Add card to Kanban" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.path.endsWith("/packages") &&
            call.body.ownerUserId === "analyst-ssg" &&
            call.body.grantId === null &&
            call.body.linkedRequestId === null &&
            call.body.iterationId === null,
        ),
      ).toBe(true),
    );

    let attempts = 0;
    mockFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
        if (url.pathname.endsWith("/board")) {
          attempts += 1;
          return attempts === 1 ? json({ detail: "Unavailable" }, 503) : json(board);
        }
        if (url.pathname.endsWith("/people")) return json({ items: people });
        if (url.pathname.endsWith("/iterations")) return json({ items: [] });
        if (url.pathname.endsWith("/packages")) return json({ items: [packageItem] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    renderApp("/teams/team-ssg/board");
    expect(
      await screen.findByRole("heading", { name: "Team delivery could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Customer request projection")).toBeInTheDocument();
  });
});
