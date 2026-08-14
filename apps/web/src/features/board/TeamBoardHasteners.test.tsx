import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { RequestDetail } from "../../lib/api/types";
import { requestDetail } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import { board, managerAccess, managerSession, mockBoard } from "./teamBoardTestSupport";

describe("team workflow board", () => {
  it("deep-links to a request and lets a Manager hasten all or one assigned Analyst", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    const assigned: RequestDetail = {
      ...requestDetail,
      id: "request-one",
      title: "Customer request projection",
      status: "CUSTOMER_INFORMATION_REQUIRED",
      assignedDeliveryTeam: null,
      assignedSpecialist: null,
      contributors: [{ id: "analyst-two", displayName: "Nathan Patterson" }],
      clarifications: [
        {
          id: "clarification-one",
          sequence: 1,
          question: "Which synthetic location should be prioritised?",
          reason: "The request needs a bounded scope.",
          responseDeadline: "2026-08-15T12:00:00Z",
          status: "OPEN",
          version: 1,
          assignedSpecialist: { id: "analyst-ssg", displayName: "Lewis Ferguson" },
          messages: [],
          createdAt: "2026-08-11T09:00:00Z",
          closedAt: null,
        },
      ],
      events: [],
    };
    mockBoard(managerSession, managerAccess, calls, { ...board, items: [] }, false, assigned);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/board?itemId=request-one");
    const dialog = await screen.findByRole("dialog", { name: "Work item details" });
    expect(within(dialog).getByText("Rework", { selector: "dd" })).toBeInTheDocument();
    expect(
      await within(dialog).findByRole("heading", { name: "Waiting for customer information" }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Routing in progress")).toBeInTheDocument();
    expect(within(dialog).getAllByText("Unassigned", { selector: "dd" })).toHaveLength(2);
    await user.click(await screen.findByRole("button", { name: "Send hastener" }));
    expect(await screen.findByLabelText(/^Recipients/)).toHaveValue("ALL_ASSIGNED");
    await user.type(
      screen.getByLabelText(/^Message/),
      "Please confirm progress before this afternoon's review.",
    );
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.path.endsWith("/hasteners") &&
            call.body.audience === "ALL_ASSIGNED" &&
            !call.body.recipientUserId,
        ),
      ).toBe(true),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Hastener sent and recorded");
    expect(
      await screen.findByText(/Hastener sent to Lewis Ferguson, Nathan Patterson/),
    ).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Send hastener" }));
    await user.selectOptions(await screen.findByLabelText(/^Recipients/), "analyst-two");
    await user.type(
      screen.getByLabelText(/^Message/),
      "Please update your assigned contribution before the review.",
    );
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.body.audience === "ONE_ASSIGNED" && call.body.recipientUserId === "analyst-two",
        ),
      ).toBe(true),
    );
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("reports an unavailable exact deep link without opening another item", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls, board, false, requestDetail, null);
    renderApp("/teams/team-ssg/board?itemId=request-one");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The linked request could not be opened",
    );
    expect(screen.queryByRole("dialog", { name: "Work item details" })).not.toBeInTheDocument();
  });
});
