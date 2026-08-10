import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import type { Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const managerSession: Session = { ...requesterSession, user: { ...requesterSession.user, id: "manager-osg", username: "admin8", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", scope: "OSG Team" } };
const analystSession: Session = { ...managerSession, user: { ...managerSession.user, id: "analyst-osg", username: "admin11", displayName: "Lewis Ferguson", role: "DELIVERY_SPECIALIST" } };
const managerAccess: TeamWorkspaceAccess = { teamId: "team-osg", teamCode: "OSG_TEAM", teamName: "OSG Team", unitKind: "TEAM", workspacePosition: "MANAGER", grantId: "grant-osg", permissions: ["CALENDAR", "CAPACITY", "ROSTER"] };
const analystAccess: TeamWorkspaceAccess = { ...managerAccess, grantId: null, permissions: [] };
const people: TeamMember[] = [{ membershipId: "membership-manager", accountId: "manager-osg", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 0, skills: ["Delivery leadership"], startReason: null, endReason: null }, { membershipId: "membership-analyst", accountId: "analyst-osg", displayName: "Lewis Ferguson", role: "DELIVERY_SPECIALIST", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 0, skills: ["Research"], startReason: null, endReason: null }];

function occurrence(overrides: Partial<CalendarOccurrence> = {}): CalendarOccurrence {
  const startsAt = tomorrow(9);
  return {
    eventId: "event-personal",
    occurrenceStart: startsAt,
    startsAt,
    endsAt: tomorrow(11),
    title: "Protected planning time",
    notes: "Synthetic private planning detail.",
    category: "TRAINING",
    visibility: "PRIVATE",
    kind: "PERSONAL",
    subjectUserId: "analyst-osg",
    subjectDisplayName: "Lewis Ferguson",
    teamId: null,
    allDay: false,
    timeZone: "Europe/London",
    recurrence: "DAILY",
    commitmentStatus: "NOT_REQUIRED",
    version: 1,
    isException: false,
    ...overrides,
  };
}

describe("canonical workforce calendar", () => {
  it("provides accessible personal month, week and agenda views, creation and commitment response", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    const commitment = occurrence({ eventId: "event-commitment", title: "Delivery commitment", kind: "COMMITMENT", visibility: "TEAM_DETAIL", commitmentStatus: "PENDING", recurrence: "NONE" });
    mockCalendar(analystSession, analystAccess, [occurrence(), commitment], calls);
    const user = userEvent.setup();
    const view = renderApp("/calendar/month");
    expect(await screen.findByRole("heading", { name: "My calendar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My calendar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "month" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText("Protected planning time")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "week" }));
    expect(screen.getByRole("region", { name: "week calendar" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "agenda" }));
    expect(screen.getByRole("region", { name: "Agenda" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Delivery commitment/ }));
    await user.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/acknowledge"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.type(screen.getByLabelText(/^Title/), "Personal development block");
    await user.type(screen.getByLabelText(/^Notes/), "Required synthetic detail for a personal calendar event.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/api/v1/calendar/events")).toBe(true));
  });

  it("lets an exact-team Manager create team events and commitments and commit capacity", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(managerSession, managerAccess, [occurrence({ title: "Busy", notes: null })], calls);
    const user = userEvent.setup();
    renderApp("/teams/team-osg/calendar");
    expect(await screen.findByText("Busy")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add event" }));
    expect(await screen.findByRole("heading", { name: "Add calendar activity" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Unit event" }));
    await user.type(screen.getByLabelText(/^Title/), "OSG planning session");
    await user.type(screen.getByLabelText(/^Notes/), "Required shared planning detail for the OSG team.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/calendar/events"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.click(screen.getByRole("button", { name: "Ticket commitment" }));
    fireEvent.submit(screen.getByRole("button", { name: "Create commitment" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Select a request and an Analyst");
    await user.selectOptions(screen.getByLabelText(/^Service request/), "request-one");
    await user.selectOptions(screen.getByLabelText(/^Analyst/), "analyst-osg");
    await user.type(screen.getByLabelText(/^Title/), "Protected delivery commitment");
    await user.type(screen.getByLabelText(/^Notes/), "Required commitment detail for subject acknowledgement.");
    await user.click(screen.getByRole("button", { name: "Create commitment" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/calendar/commitments"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    expect(await screen.findByRole("table", { name: "Calendar-backed capacity preview" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Commit snapshot" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/capacity/commits"))).toBe(true));
  });

  it("supports occurrence edits while keeping shared personal events read-only", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [occurrence()], calls);
    const user = userEvent.setup();
    renderApp("/calendar/agenda");
    await user.click(await screen.findByRole("button", { name: /Protected planning time/ }));
    await user.click(screen.getByRole("button", { name: "Edit occurrence" }));
    const detail = screen.getByRole("complementary", { name: "Protected planning time" });
    await user.type(within(detail).getByLabelText(/^Reason/), "This occurrence needs a later delivery planning window.");
    fireEvent.change(within(detail).getByLabelText(/^Starts/), { target: { value: localTomorrow(12) } });
    fireEvent.change(within(detail).getByLabelText(/^Ends/), { target: { value: localTomorrow(14) } });
    await user.click(screen.getByRole("button", { name: "Confirm edit" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/occurrences/edit"))).toBe(true));

    calls.length = 0;
    mockCalendar(managerSession, managerAccess, [occurrence({ title: "Busy", notes: null })], calls);
    renderApp("/teams/team-osg/calendar");
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
    await user.type(screen.getByLabelText(/^Notes/), "Required recurring development detail for this synthetic event.");
    await user.selectOptions(screen.getByLabelText(/^Category/), "TRAINING");
    expect(screen.getByRole("checkbox", { name: /Private appointment/ })).not.toBeChecked();
    await user.selectOptions(screen.getByLabelText(/^Time zone/), "Europe/Paris");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: localTomorrow(12) } });
    fireEvent.change(screen.getByLabelText(/^Ends/), { target: { value: localTomorrow(14) } });
    await user.selectOptions(screen.getByLabelText(/^Repeats/), "WEEKLY");
    fireEvent.change(screen.getByLabelText(/^Repeat interval/), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/^Repeat until/), { target: { value: localTomorrow(18) } });
    await user.click(screen.getByLabelText("All-day activity"));
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(calls.some((call) => call.body.recurrence === "WEEKLY" && call.body.recurrenceInterval === 2 && call.body.allDay === true && call.body.visibility === "TEAM_DETAIL")).toBe(true));
  });

  it("supports disputes, occurrence cancellation, future changes and whole-event confirmation", async () => {
    const user = userEvent.setup();
    const cases = [
      { action: "Dispute", confirm: "Confirm dispute", suffix: "/dispute", item: occurrence({ eventId: "commitment", kind: "COMMITMENT", commitmentStatus: "PENDING", recurrence: "NONE" }) },
      { action: "Cancel occurrence", confirm: "Confirm cancel occurrence", suffix: "/occurrences/cancel", item: occurrence() },
      { action: "Change this and future", confirm: "Confirm split", suffix: "/split", item: occurrence() },
      { action: "Cancel whole event", confirm: "Confirm cancel series", suffix: "/cancel", item: occurrence({ recurrence: "NONE" }) },
    ];
    for (const itemCase of cases) {
      const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
      mockCalendar(analystSession, analystAccess, [itemCase.item], calls);
      const rendered = renderApp("/calendar/agenda");
      await user.click(await screen.findByRole("button", { name: new RegExp(itemCase.item.title) }));
      await user.click(screen.getByRole("button", { name: itemCase.action }));
      const detail = screen.getByRole("complementary", { name: itemCase.item.title });
      await user.type(within(detail).getByLabelText(/^Reason/), "Required synthetic reason for this calendar change.");
      if (itemCase.action === "Change this and future") {
        await user.clear(within(detail).getByLabelText(/^Title/));
        await user.type(within(detail).getByLabelText(/^Title/), "Replanned protected time");
        await user.clear(within(detail).getByLabelText(/^Notes/));
        await user.type(within(detail).getByLabelText(/^Notes/), "Required detail for the changed recurring series.");
        fireEvent.change(within(detail).getByLabelText(/^Starts/), { target: { value: localTomorrow(13) } });
        fireEvent.change(within(detail).getByLabelText(/^Ends/), { target: { value: localTomorrow(15) } });
        fireEvent.change(within(detail).getByLabelText(/^Repeat until/), { target: { value: localTomorrow(18) } });
      }
      await user.click(within(detail).getByRole("button", { name: itemCase.confirm }));
      await waitFor(() => expect(calls.some((call) => call.path.endsWith(itemCase.suffix))).toBe(true));
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
    expect(screen.getByText(/visible to other members of your current unit/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Title/), "Visible planning activity");
    await user.type(screen.getByLabelText(/^Notes/), "Required synthetic detail for the unit calendar.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(calls.some((call) => call.body.visibility === "TEAM_DETAIL")).toBe(true));
  });

  it("keeps edits reversible and presents calendar and capacity write conflicts", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(managerSession, managerAccess, [occurrence({ allDay: true, kind: "TEAM", notes: null, subjectUserId: "manager-osg", visibility: "TEAM_DETAIL" })], calls, { mutationFailure: "/capacity/commits" });
    const user = userEvent.setup();
    renderApp("/teams/team-osg/calendar");
    await user.click(await screen.findByRole("button", { name: /Protected planning time/ }));
    await user.click(screen.getByRole("button", { name: "Cancel occurrence" }));
    const detail = screen.getByRole("complementary", { name: "Protected planning time" });
    await user.click(within(detail).getByRole("button", { name: "Keep event" }));
    expect(within(detail).queryByLabelText(/^Reason/)).not.toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Close calendar detail" }));
    expect(screen.queryByRole("complementary", { name: "Protected planning time" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    await user.click(await screen.findByRole("button", { name: "Commit snapshot" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
  });

  it("reports rejected event writes and capacity previews without losing form context", async () => {
    const personalCalls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(analystSession, analystAccess, [], personalCalls, { mutationFailure: "/calendar/events" });
    const user = userEvent.setup();
    const personal = renderApp("/calendar/month");
    await screen.findByRole("region", { name: "month calendar" });
    await user.click(screen.getByRole("button", { name: "Add event" }));
    await user.type(screen.getByLabelText(/^Title/), "Protected work block");
    await user.type(screen.getByLabelText(/^Notes/), "Required detail retained after a rejected write.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
    expect(screen.getByLabelText(/^Title/)).toHaveValue("Protected work block");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: "" } });
    fireEvent.submit(screen.getByRole("button", { name: "Create event" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid time value");
    personal.unmount();

    const capacityCalls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockCalendar(managerSession, managerAccess, [], capacityCalls, { mutationFailure: "/capacity/previews" });
    const capacity = renderApp("/teams/team-osg/calendar");
    await screen.findByRole("heading", { name: "Capacity snapshot" });
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-08-10" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-08-14" } });
    await user.selectOptions(screen.getAllByLabelText(/^Time zone/).at(-1)!, "America/New_York");
    await user.click(screen.getByRole("button", { name: "Preview capacity" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic calendar conflict");
    capacity.unmount();

    mockCalendar(analystSession, analystAccess, [], []);
    renderApp("/teams/team-osg/calendar");
    await screen.findByRole("region", { name: "month calendar" });
    expect(screen.queryByRole("heading", { name: "Add to team calendar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Capacity snapshot" })).not.toBeInTheDocument();
  });

  it("fails closed when ticket choices cannot be loaded", async () => {
    mockCalendar(managerSession, managerAccess, [], [], { boardFailure: true });
    const user = userEvent.setup();
    renderApp("/teams/team-osg/calendar");
    await user.click(await screen.findByRole("button", { name: "Add event" }));
    await user.click(await screen.findByRole("button", { name: "Ticket commitment" }));
    expect(await screen.findByRole("option", { name: "Requests unavailable" })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Service request/)).toBeDisabled();
  });
});

function mockCalendar(session: Session, access: TeamWorkspaceAccess, items: CalendarOccurrence[], calls: Array<{ path: string; body: Record<string, unknown> }>, options: { boardFailure?: boolean; calendarFailures?: number; mutationFailure?: string; workspaceFailure?: boolean } = {}) {
  let calendarReads = 0;
  return mockFetch(async (url, init) => {
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/team-workspaces")) return options.workspaceFailure ? json({ detail: "Synthetic workspace failure" }, 503) : json({ items: [access] });
    if (url.pathname.endsWith("/people")) return json({ items: people });
    if (url.pathname.endsWith("/board")) return options.boardFailure ? json({ detail: "Synthetic board failure" }, 503) : json({
      items: [{ id: "request-one", itemType: "SERVICE_REQUEST", reference: "REQ-001", title: "Synthetic current request", column: "IN_PROGRESS", priority: "MEDIUM", dueOn: tomorrow(16), ownerUserId: "analyst-osg", ownerDisplayName: "Lewis Ferguson", version: 1, linkedRequestId: null, availableColumns: ["IN_PROGRESS"], changedAt: "2026-08-07T10:00:00Z" }],
      nextCursor: null,
      columnCounts: {},
      totalCount: 1,
      wipLimits: {},
      configurationVersion: 1,
      savedViews: [],
      generatedAt: new Date().toISOString(),
    });
    if (url.pathname.endsWith("/calendar/personal") || url.pathname.endsWith("/calendar")) {
      calendarReads += 1;
      if (calendarReads <= (options.calendarFailures ?? 0)) return json({ detail: "Synthetic calendar read failure" }, 503);
      return json({ items });
    }
    if (init.method && init.method !== "GET") {
      calls.push({ path: url.pathname, body: JSON.parse(String(init.body)) as Record<string, unknown> });
      if (options.mutationFailure && url.pathname.endsWith(options.mutationFailure)) return json({ detail: "Synthetic calendar conflict" }, 409);
      if (url.pathname.endsWith("/capacity/previews")) return json({ token: "preview-token-value-that-is-long-enough", expiresAt: tomorrow(12), days: [{ date: new Date().toISOString().slice(0, 10), memberCount: 2, baselineMinutes: 900, unavailableMinutes: 120, availableMinutes: 780 }] });
      if (url.pathname.endsWith("/capacity/commits")) return json({ snapshotId: "snapshot", days: [] });
      return json({ eventId: "event-result", version: 2 });
    }
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, true, false);
}

function tomorrow(hour: number) { const value = new Date(); value.setDate(value.getDate() + 1); value.setHours(hour, 0, 0, 0); return value.toISOString(); }
function localTomorrow(hour: number) { const value = new Date(tomorrow(hour)); return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16); }
