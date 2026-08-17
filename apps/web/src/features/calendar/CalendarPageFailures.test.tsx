import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { json, mockFetch, renderApp } from "../../test/render";
import {
  analystAccess,
  analystSession,
  managerAccess,
  managerSession,
  mockCalendar,
  occurrence,
} from "./calendarPageTestSupport";

describe("canonical workforce calendar failure handling", () => {
  it("keeps edits reversible and presents calendar and capacity write conflicts", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(
      managerSession,
      managerAccess,
      [
        occurrence({
          allDay: true,
          kind: "TEAM",
          notes: null,
          subjectUserId: "manager-ssg",
          visibility: "TEAM_DETAIL",
        }),
      ],
      calls,
      { mutationFailure: "/capacity/commits" },
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/calendar");
    await user.click(await screen.findByRole("button", { name: /Protected planning time/ }));
    await user.click(screen.getByRole("button", { name: "Cancel occurrence" }));
    const detail = screen.getByRole("complementary", { name: "Protected planning time" });
    await user.click(within(detail).getByRole("button", { name: "Keep event" }));
    expect(within(detail).queryByLabelText(/^Reason/)).not.toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Close calendar detail" }));
    expect(
      screen.queryByRole("complementary", { name: "Protected planning time" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    await user.click(await screen.findByRole("button", { name: "Commit snapshot" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
  });

  it("reports rejected event writes and capacity previews without losing form context", async () => {
    const personalCalls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [], personalCalls, {
      mutationFailure: "/calendar/events",
    });
    const user = userEvent.setup();
    const personal = renderApp("/calendar/month");
    await screen.findByRole("region", { name: "month calendar" });
    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.type(screen.getByLabelText(/^Title/), "Protected work block");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required detail retained after a rejected write.",
    );
    await user.click(screen.getByRole("button", { name: "Create event" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
    expect(screen.getByLabelText(/^Title/)).toHaveValue("Protected work block");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: "" } });
    fireEvent.submit(screen.getByRole("button", { name: "Create event" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid time value");
    personal.unmount();

    const capacityCalls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(managerSession, managerAccess, [], capacityCalls, {
      mutationFailure: "/capacity/previews",
    });
    const capacity = renderApp("/teams/team-ssg/calendar");
    await screen.findByRole("heading", { name: "Capacity snapshot" });
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-08-10" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-08-14" } });
    await user.selectOptions(screen.getAllByLabelText(/^Time zone/).at(-1)!, "America/New_York");
    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
    capacity.unmount();

    mockCalendar(analystSession, analystAccess, [], []);
    renderApp("/teams/team-ssg/calendar");
    await screen.findByRole("region", { name: "month calendar" });
    expect(screen.queryByRole("heading", { name: "Add to team calendar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Capacity snapshot" })).not.toBeInTheDocument();
  });

  it("fails closed when ticket choices cannot be loaded", async () => {
    mockCalendar(managerSession, managerAccess, [], [], { boardFailure: true });
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/calendar");
    await user.click(await screen.findByRole("button", { name: "Add event" }));
    await user.click(await screen.findByRole("button", { name: "Ticket commitment" }));
    expect(await screen.findByRole("option", { name: "Requests unavailable" })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Service request/)).toBeDisabled();
  });

  it("loads a Calendar-only grant without Board or roster reads", async () => {
    const calendarOnly = {
      ...managerAccess,
      workspacePosition: null,
      permissions: ["CALENDAR"],
      views: ["OVERVIEW", "CALENDAR", "HANDOVER"],
    };
    mockFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [calendarOnly] });
        if (url.pathname.endsWith("/calendar")) return json({ items: [] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();

    renderApp("/teams/team-ssg/calendar");
    await screen.findByRole("region", { name: "month calendar" });
    await user.click(screen.getByRole("button", { name: "Add event" }));

    expect(screen.getByRole("button", { name: "Unit event" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ticket commitment" })).not.toBeInTheDocument();
  });
});
