import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { json, mockFetch, renderApp } from "../../test/render";
import {
  board,
  iterations,
  managerAccess,
  managerSession,
  mockBoard,
  packageItem,
  people,
} from "./teamBoardTestSupport";

describe("team workflow board", () => {
  it("surfaces mutation errors without disclosing inaccessible content", async () => {
    mockBoard(managerSession, managerAccess, [], board, true);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    await screen.findByRole("heading", { name: "Service request board" });
    await user.click(screen.getByText("Work package Kanban"));
    expect(
      await screen.findByRole("heading", { name: "Prepare synthetic product" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Board settings" }));
    await user.click(screen.getByRole("button", { name: "Save limits" }));
    expect(
      (await screen.findAllByRole("alert")).some((alert) =>
        alert.textContent?.includes("Planning conflict"),
      ),
    ).toBe(true);
    await user.click(screen.getByRole("button", { name: "Close Board settings" }));
    await user.click(
      within(
        screen
          .getByRole("heading", { name: "Prepare synthetic product" })
          .closest("article") as HTMLElement,
      ).getByRole("button", { name: /Work package · WP-PACKAGE/ }),
    );
    await user.selectOptions(screen.getByLabelText(/Move package to/), "IN_PROGRESS");
    await user.type(
      screen.getByLabelText(/^Reason/),
      "The package is ready for deliberate delivery work.",
    );
    await user.click(screen.getByRole("button", { name: "Move package" }));
    expect(
      (await screen.findAllByRole("alert")).some((alert) =>
        alert.textContent?.includes("Planning conflict"),
      ),
    ).toBe(true);
  });

  it("recovers the work package Kanban independently", async () => {
    let packageBoardAttempts = 0;
    mockFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
        if (url.pathname.endsWith("/people")) return json({ items: people });
        if (url.pathname.endsWith("/iterations")) return json({ items: iterations });
        if (url.pathname.endsWith("/packages")) return json({ items: [packageItem] });
        if (
          url.pathname.endsWith("/board") &&
          url.searchParams.get("itemType") === "WORK_PACKAGE"
        ) {
          packageBoardAttempts += 1;
          return packageBoardAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json(board);
        }
        if (url.pathname.endsWith("/board")) return json(board);
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    await screen.findByRole("heading", { name: "Service request board" });
    await user.click(screen.getByText("Work package Kanban"));
    expect(
      await screen.findByRole("heading", { name: "Work package Kanban could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "Prepare synthetic product" }),
    ).toBeInTheDocument();
    expect(packageBoardAttempts).toBe(2);
  });

  it("fails closed and recovers all required queries after an outage", async () => {
    const attempts = { board: 0, people: 0, iterations: 0 };
    mockFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
        if (url.pathname.endsWith("/board")) {
          attempts.board += 1;
          return attempts.board === 1 ? json({ detail: "Unavailable" }, 503) : json(board);
        }
        if (url.pathname.endsWith("/iterations")) {
          attempts.iterations += 1;
          return attempts.iterations === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: iterations });
        }
        if (url.pathname.endsWith("/people")) {
          attempts.people += 1;
          return attempts.people === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: people });
        }
        if (url.pathname.endsWith("/packages")) return json({ items: [packageItem] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(
      await screen.findByRole("heading", { name: "Team delivery could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();
    expect(attempts).toEqual({ board: 2, people: 2, iterations: 2 });
  });
});
