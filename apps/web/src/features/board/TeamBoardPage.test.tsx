import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { renderApp } from "../../test/render";
import { managerAccess, managerSession, mockBoard } from "./teamBoardTestSupport";

describe("team workflow board", () => {
  it("renders workflow cards, inspects requests and creates packages", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Service request board" })).toBeInTheDocument();
    expect(screen.getByText("(Assigned Analysts are producing the response)")).toBeInTheDocument();
    const packageBoard = screen.getByText("Work package Kanban").closest("details");
    expect(packageBoard).not.toHaveAttribute("open");
    expect(screen.queryByText("Prepare synthetic product")).not.toBeInTheDocument();
    await user.click(screen.getByText("Work package Kanban"));
    expect(
      await screen.findByRole("heading", { name: "Prepare synthetic product" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Customer request projection")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Quality Review" })).not.toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: "Recent internal card activity" }).closest("section"),
    ).toHaveTextContent("Work package created.");
    expect(
      within(
        screen
          .getByRole("heading", { name: "Prepare synthetic product" })
          .closest("article") as HTMLElement,
      ).getByText("Pilot iteration"),
    ).toBeInTheDocument();
    const requestCard = screen
      .getByRole("heading", { name: "Customer request projection" })
      .closest("article");
    await user.click(within(requestCard as HTMLElement).getByRole("button"));
    expect(await screen.findByRole("dialog", { name: "Work item details" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Customer requirement" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full request" })).toHaveAttribute(
      "href",
      "/requests/request-one",
    );
    await user.click(screen.getByRole("button", { name: "Close Work item details" }));
    await user.click(screen.getByRole("button", { name: "Create internal card" }));
    const createPackage = await screen.findByRole("dialog", { name: "Create internal card" });
    fireEvent.change(await screen.findByLabelText(/^Title/, { selector: "input" }), {
      target: { value: "New synthetic package" },
    });
    fireEvent.change(screen.getByLabelText(/^Description/), {
      target: { value: "Complete detail for a second synthetic package." },
    });
    await user.selectOptions(within(createPackage).getByLabelText(/^Owner/), "analyst-ssg");
    await user.selectOptions(screen.getByLabelText(/^Contributor/), "analyst-ssg");
    fireEvent.change(screen.getByLabelText(/^Due date/), { target: { value: "2026-08-28" } });
    fireEvent.change(screen.getByLabelText(/^Blockers or none/), {
      target: { value: "No known blockers." },
    });
    fireEvent.change(screen.getByLabelText(/^Acceptance criteria/), {
      target: { value: "The complete fictional product is delivered." },
    });
    fireEvent.change(screen.getByLabelText(/^Linked request ID/), {
      target: { value: "request-two" },
    });
    await user.selectOptions(screen.getByLabelText(/^Iteration/), "iteration-active");
    await user.click(screen.getByRole("button", { name: "Add card to Kanban" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.path.endsWith("/packages") &&
            call.method === "POST" &&
            call.body.linkedRequestId === "request-two" &&
            call.body.iterationId === "iteration-active",
        ),
      ).toBe(true),
    );
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("supports saved views and reasoned package movement", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();
    await user.click(screen.getByText(/Saved views/));
    await user.click(screen.getByRole("button", { name: "My delivery" }));
    await user.type(await screen.findByLabelText("New saved view name"), "Urgent work");
    await user.click(screen.getByRole("button", { name: "Save current view" }));
    await waitFor(() =>
      expect(
        calls.some((call) => call.path.includes("saved-views") && call.method === "POST"),
      ).toBe(true),
    );
    await user.click(await screen.findByRole("button", { name: "Delete My delivery" }));
    await waitFor(() =>
      expect(
        calls.some((call) => call.path.includes("saved-views") && call.method === "DELETE"),
      ).toBe(true),
    );

    await user.click(
      within(
        (await screen.findByRole("heading", { name: "Prepare synthetic product" })).closest(
          "article",
        ) as HTMLElement,
      ).getByRole("button", { name: /Work package · WP-PACKAGE/ }),
    );
    await user.selectOptions(await screen.findByLabelText(/Move package to/), "IN_PROGRESS");
    await user.type(
      screen.getByLabelText(/^Reason/),
      "The package is ready for deliberate delivery work.",
    );
    await user.click(screen.getByRole("button", { name: "Move package" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) => call.path.endsWith("/board/moves") && call.body.target === "IN_PROGRESS",
        ),
      ).toBe(true),
    );
  });
});
