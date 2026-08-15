import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { requestDetail, requesterSession } from "../../test/fixtures";
import { json, mockFetch, TestProviders } from "../../test/render";
import { TaskHastenerPanel } from "./TaskHastenerPanel";

const manager: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  unitKind: "TEAM",
  workspacePosition: "MANAGER",
  grantId: "grant-ssg",
  permissions: ["BOARD"],
};
const history = {
  id: "hastener-one",
  type: "task_hastener",
  message: "Hastener sent to Lewis Ferguson: Please confirm progress.",
  actorDisplayName: null,
  createdAt: "2026-08-11T10:00:00Z",
};

function panel(access = manager, request = requestDetail) {
  return (
    <TestProviders>
      <MemoryRouter>
        <TaskHastenerPanel access={access} request={request} session={requesterSession} />
      </MemoryRouter>
    </TestProviders>
  );
}

describe("task hasteners", () => {
  it("shows history without controls and hides an empty unavailable panel", () => {
    const member = {
      ...manager,
      workspacePosition: "MEMBER" as const,
      grantId: null,
      permissions: [],
    };
    const completed = { ...requestDetail, status: "COMPLETED" as const, events: [history] };
    const view = render(panel(member, completed));
    expect(screen.getByText(/Hastener sent to Lewis Ferguson/)).toBeInTheDocument();
    expect(screen.getByText(/Mist service/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send hastener" })).not.toBeInTheDocument();

    view.rerender(panel({ ...manager, unitKind: "COMMAND" }, completed));
    expect(screen.queryByRole("button", { name: "Send hastener" })).not.toBeInTheDocument();
    view.rerender(panel(manager, completed));
    expect(screen.queryByRole("button", { name: "Send hastener" })).not.toBeInTheDocument();
    view.rerender(
      panel(manager, {
        ...requestDetail,
        assignedSpecialist: null,
        contributors: [],
        events: [history],
      }),
    );
    expect(screen.queryByRole("button", { name: "Send hastener" })).not.toBeInTheDocument();
    view.rerender(panel(member, { ...completed, events: [] }));
    expect(view.container).toBeEmptyDOMElement();
  });

  it("reports a safe API failure while retaining the reminder", async () => {
    mockFetch(async (url) => {
      if (url.pathname.endsWith("/hasteners"))
        return json({ detail: "The reminder conflicts with current work." }, 409);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    render(panel());
    await user.click(screen.getByRole("button", { name: "Send hastener" }));
    await user.type(
      screen.getByLabelText(/^Message/),
      "Please confirm current progress before review.",
    );
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The reminder conflicts with current work",
    );
    expect(screen.getByLabelText(/^Message/)).toHaveValue(
      "Please confirm current progress before review.",
    );
  });

  it("uses a generic message for an unexpected transport failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network detail must stay hidden")));
    const user = userEvent.setup();
    render(panel());
    await user.click(screen.getByRole("button", { name: "Send hastener" }));
    await user.type(
      screen.getByLabelText(/^Message/),
      "Please confirm current progress before review.",
    );
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The hastener could not be sent");
  });
});
