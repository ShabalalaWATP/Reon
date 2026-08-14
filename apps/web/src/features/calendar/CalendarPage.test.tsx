import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { renderApp } from "../../test/render";
import {
  analystAccess,
  analystSession,
  localTomorrow,
  managerAccess,
  managerSession,
  mockCalendar,
  occurrence,
  staffWithoutWorkspace,
  tomorrow,
} from "./calendarPageTestSupport";

describe("canonical workforce calendar", () => {
  it("gives an account without a workspace a personal-only calendar", async () => {
    mockCalendar(staffWithoutWorkspace, analystAccess, [], [], { noWorkspace: true });
    renderApp("/calendar/month");

    expect(await screen.findByRole("heading", { name: "Personal calendar" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open .* calendar/ })).not.toBeInTheDocument();
    expect(screen.getByText(/has no current workspace/)).toBeInTheDocument();
  });

  it("provides accessible personal month, week and agenda views, creation and commitment response", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    const commitment = occurrence({
      eventId: "event-commitment",
      title: "Delivery commitment",
      kind: "COMMITMENT",
      visibility: "TEAM_DETAIL",
      commitmentStatus: "PENDING",
      recurrence: "NONE",
    });
    mockCalendar(analystSession, analystAccess, [occurrence(), commitment], calls);
    const user = userEvent.setup();
    const view = renderApp("/calendar/month");
    expect(await screen.findByRole("heading", { name: "Personal calendar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Personal calendar" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open SSG Team calendar" })).toHaveAttribute(
      "href",
      "/teams/team-ssg/calendar",
    );
    expect(screen.getByRole("button", { name: "month" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText("Protected planning time")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getAllByRole("button", { name: /^Add event on/ })[0]);
    expect(await screen.findByRole("heading", { name: "Add personal event" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close Add calendar event" }));

    await user.click(screen.getByRole("button", { name: "week" }));
    expect(screen.getByRole("region", { name: "week calendar" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "agenda" }));
    expect(screen.getByRole("region", { name: "Agenda" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Delivery commitment/ }));
    await user.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/acknowledge"))).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.type(screen.getByLabelText(/^Title/), "Personal development block");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required synthetic detail for a personal calendar event.",
    );
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/calendar/events")).toBe(true),
    );
  });

  it("lets an exact-team Manager create team events and commitments and commit capacity", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(
      managerSession,
      managerAccess,
      [occurrence({ title: "Busy", notes: null })],
      calls,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/calendar");
    expect(await screen.findByText("Busy")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add event" }));
    expect(
      await screen.findByRole("heading", { name: "Add calendar activity" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Unit event" }));
    await user.type(screen.getByLabelText(/^Title/), "SSG planning session");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required shared planning detail for the SSG team.",
    );
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/calendar/events"))).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.click(screen.getByRole("button", { name: "Ticket commitment" }));
    fireEvent.submit(screen.getByRole("button", { name: "Create commitment" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Select a request and an Analyst");
    await user.selectOptions(screen.getByLabelText(/^Service request/), "request-one");
    await user.selectOptions(screen.getByLabelText(/^Analyst/), "analyst-ssg");
    await user.type(screen.getByLabelText(/^Title/), "Protected delivery commitment");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required commitment detail for subject acknowledgement.",
    );
    await user.click(screen.getByRole("button", { name: "Create commitment" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/calendar/commitments"))).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    expect(
      await screen.findByRole("table", { name: "Calendar-backed capacity preview" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Commit snapshot" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/capacity/commits"))).toBe(true),
    );
  });

  it("supports occurrence edits while keeping shared personal events read-only", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [occurrence()], calls);
    const user = userEvent.setup();
    renderApp("/calendar/agenda");
    await user.click(await screen.findByRole("button", { name: /Protected planning time/ }));
    await user.click(screen.getByRole("button", { name: "Edit occurrence" }));
    const detail = screen.getByRole("complementary", { name: "Protected planning time" });
    await user.type(
      within(detail).getByLabelText(/^Reason/),
      "This occurrence needs a later delivery planning window.",
    );
    fireEvent.change(within(detail).getByLabelText(/^Starts/), {
      target: { value: localTomorrow(12) },
    });
    fireEvent.change(within(detail).getByLabelText(/^Ends/), {
      target: { value: localTomorrow(14) },
    });
    await user.click(screen.getByRole("button", { name: "Confirm edit" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/occurrences/edit"))).toBe(true),
    );

    calls.length = 0;
    mockCalendar(
      managerSession,
      managerAccess,
      [occurrence({ title: "Busy", notes: null })],
      calls,
    );
    renderApp("/teams/team-ssg/calendar");
    await user.click(await screen.findByRole("button", { name: /Busy/ }));
    expect(screen.queryByRole("button", { name: "Edit occurrence" })).not.toBeInTheDocument();
  });

  it("resets editable values when a different occurrence is selected", async () => {
    const first = occurrence({ eventId: "event-first", title: "First planning block" });
    const secondStart = tomorrow(14);
    const second = occurrence({
      eventId: "event-second",
      occurrenceStart: secondStart,
      startsAt: secondStart,
      endsAt: tomorrow(16),
      title: "Second planning block",
    });
    mockCalendar(analystSession, analystAccess, [first, second], []);
    const user = userEvent.setup();
    renderApp("/calendar/agenda");

    await user.click(await screen.findByRole("button", { name: /First planning block/ }));
    await user.click(screen.getByRole("button", { name: "Edit occurrence" }));
    const firstDetail = screen.getByRole("complementary", { name: "First planning block" });
    const firstTitle = within(firstDetail).getByLabelText(/^Title/);
    await user.clear(firstTitle);
    await user.type(firstTitle, "Unsaved first occurrence value");

    await user.click(screen.getByRole("button", { name: /Second planning block/ }));
    await user.click(screen.getByRole("button", { name: "Edit occurrence" }));
    const secondDetail = screen.getByRole("complementary", { name: "Second planning block" });
    expect(within(secondDetail).getByLabelText(/^Title/)).toHaveValue("Second planning block");
  });

  it("recovers from a failed load and supports bounded navigation and recurring personal events", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [], calls, { calendarFailures: 1 });
    const user = userEvent.setup();
    renderApp("/calendar/not-a-view");
    expect(await screen.findByText("Calendar could not be loaded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("region", { name: "month calendar" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Previous calendar period" }));
    await user.click(screen.getByRole("button", { name: "Next calendar period" }));
    await user.click(screen.getByRole("button", { name: "Today" }));
    await user.click(screen.getByRole("button", { name: "week" }));
    await user.click(screen.getByRole("button", { name: "Previous calendar period" }));
    await user.click(screen.getByRole("button", { name: "Next calendar period" }));
    await user.click(screen.getByRole("button", { name: "agenda" }));
    await user.click(screen.getByRole("button", { name: "Previous calendar period" }));
    await user.click(screen.getByRole("button", { name: "Next calendar period" }));
    expect(await screen.findByText("No calendar activity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.type(screen.getByLabelText(/^Title/), "Weekly protected development");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required recurring development detail for this synthetic event.",
    );
    await user.selectOptions(screen.getByLabelText(/^Category/), "TRAINING");
    expect(screen.getByRole("checkbox", { name: /Private appointment/ })).not.toBeChecked();
    await user.selectOptions(screen.getByLabelText(/^Time zone/), "Europe/Paris");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: localTomorrow(12) } });
    fireEvent.change(screen.getByLabelText(/^Ends/), { target: { value: localTomorrow(14) } });
    await user.selectOptions(screen.getByLabelText(/^Repeats/), "WEEKLY");
    fireEvent.change(screen.getByLabelText(/^Repeat interval/), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/^Repeat until/), {
      target: { value: localTomorrow(18) },
    });
    await user.click(screen.getByLabelText("All-day activity"));
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.body.recurrence === "WEEKLY" &&
            call.body.recurrenceInterval === 2 &&
            call.body.allDay === true &&
            call.body.visibility === "TEAM_DETAIL",
        ),
      ).toBe(true),
    );
  });

  it("supports disputes, occurrence cancellation, future changes and whole-event confirmation", async () => {
    const user = userEvent.setup();
    const cases = [
      {
        action: "Dispute",
        confirm: "Confirm dispute",
        suffix: "/dispute",
        item: occurrence({
          eventId: "commitment",
          kind: "COMMITMENT",
          commitmentStatus: "PENDING",
          recurrence: "NONE",
        }),
      },
      {
        action: "Cancel occurrence",
        confirm: "Confirm cancel occurrence",
        suffix: "/occurrences/cancel",
        item: occurrence(),
      },
      {
        action: "Change this and future",
        confirm: "Confirm split",
        suffix: "/split",
        item: occurrence(),
      },
      {
        action: "Cancel whole event",
        confirm: "Confirm cancel series",
        suffix: "/cancel",
        item: occurrence({ recurrence: "NONE" }),
      },
    ];
    for (const itemCase of cases) {
      const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
      mockCalendar(analystSession, analystAccess, [itemCase.item], calls);
      const rendered = renderApp("/calendar/agenda");
      await user.click(
        await screen.findByRole("button", { name: new RegExp(itemCase.item.title) }),
      );
      await user.click(screen.getByRole("button", { name: itemCase.action }));
      const detail = screen.getByRole("complementary", { name: itemCase.item.title });
      await user.type(
        within(detail).getByLabelText(/^Reason/),
        "Required synthetic reason for this calendar change.",
      );
      if (itemCase.action === "Change this and future") {
        await user.clear(within(detail).getByLabelText(/^Title/));
        await user.type(within(detail).getByLabelText(/^Title/), "Replanned protected time");
        await user.clear(within(detail).getByLabelText(/^Notes/));
        await user.type(
          within(detail).getByLabelText(/^Notes/),
          "Required detail for the changed recurring series.",
        );
        fireEvent.change(within(detail).getByLabelText(/^Starts/), {
          target: { value: localTomorrow(13) },
        });
        fireEvent.change(within(detail).getByLabelText(/^Ends/), {
          target: { value: localTomorrow(15) },
        });
        fireEvent.change(within(detail).getByLabelText(/^Repeat until/), {
          target: { value: localTomorrow(18) },
        });
      }
      await user.click(within(detail).getByRole("button", { name: itemCase.confirm }));
      await waitFor(() =>
        expect(calls.some((call) => call.path.endsWith(itemCase.suffix))).toBe(true),
      );
      rendered.unmount();
    }
  });

  it("never falls back to hidden detail when the unit-name lookup is unavailable", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [], calls, { workspaceFailure: true });
    const user = userEvent.setup();
    renderApp("/calendar/month");
    await user.click(await screen.findByRole("button", { name: "Add event" }));
    expect(screen.getByRole("checkbox", { name: /Private appointment/ })).not.toBeChecked();
    expect(
      screen.getByText(/remains personal while you have no current workspace/),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Title/), "Visible planning activity");
    await user.type(
      screen.getByLabelText(/^Notes/),
      "Required synthetic detail for the unit calendar.",
    );
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() =>
      expect(calls.some((call) => call.body.visibility === "TEAM_DETAIL")).toBe(true),
    );
  });
});
