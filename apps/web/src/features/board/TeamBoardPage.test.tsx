import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { BoardItem, BoardResult, WorkPackage } from "../../lib/api/boardTypes";
import type { RequestDetail, Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { requestDetail, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const managerSession: Session = { ...requesterSession, user: { ...requesterSession.user, id: "manager-ssg", username: "admin8", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", scope: "SSG Team" } };
const analystSession: Session = { ...managerSession, user: { ...managerSession.user, id: "analyst-ssg", username: "admin11", displayName: "Lewis Ferguson", role: "DELIVERY_SPECIALIST" } };
const managerAccess: TeamWorkspaceAccess = { teamId: "team-ssg", teamCode: "SSG_TEAM", teamName: "SSG Team", unitKind: "TEAM", workspacePosition: "MANAGER", grantId: "grant-ssg", permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"] };
const analystAccess: TeamWorkspaceAccess = { ...managerAccess, workspacePosition: "MEMBER", grantId: null, permissions: [] };
const people: TeamMember[] = [
  { membershipId: "manager-membership", accountId: "manager-ssg", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 0, skills: ["Delivery leadership"], startReason: null, endReason: null },
  { membershipId: "analyst-membership", accountId: "analyst-ssg", displayName: "Lewis Ferguson", role: "DELIVERY_SPECIALIST", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 1, skills: ["Research"], startReason: null, endReason: null },
  { membershipId: "ended-membership", accountId: "former", displayName: "Former Analyst", role: "DELIVERY_SPECIALIST", state: "ENDED", effectiveFrom: "2025-01-01T09:00:00Z", effectiveUntil: "2026-01-01T09:00:00Z", version: 2, activeWorkCount: 0, skills: [], startReason: null, endReason: null },
];
const packageItem: WorkPackage = {
  id: "package-one", teamId: "team-ssg", linkedRequestId: null, iterationId: null,
  title: "Prepare synthetic product", description: "Complete fictional planning detail.",
  ownerUserId: "analyst-ssg", ownerDisplayName: "Lewis Ferguson",
  contributors: [{ userId: "analyst-ssg", displayName: "Lewis Ferguson" }],
  estimatePoints: 5, remainingEffortMinutes: 120, dueOn: "2026-08-21", priority: "HIGH", status: "READY",
  blockers: "No known blockers.", acceptanceCriteria: "The fictional output is complete.", dependencyIds: [], version: 2,
  activities: [{ id: "activity-one", type: "CREATED", summary: "Work package created.", actorDisplayName: "Grant Hanley", createdAt: "2026-08-07T10:00:00Z" }], reservations: [],
};
const iterations = [
  { id: "iteration-active", name: "Pilot iteration", goal: "Deliver the complete product.", startsOn: "2026-08-01", endsOn: "2026-08-14", status: "ACTIVE" as const, completionSummary: null, version: 1 },
  { id: "iteration-closed", name: "Closed iteration", goal: "Retain the delivery history.", startsOn: "2026-07-01", endsOn: "2026-07-14", status: "CLOSED" as const, completionSummary: "Complete.", version: 2 },
];
const board: BoardResult = {
  items: [
    { id: "request-one", itemType: "SERVICE_REQUEST", reference: "SR-000001", title: "Customer request projection", column: "IN_PROGRESS", priority: "HIGH", dueOn: "2026-08-20", ownerUserId: null, ownerDisplayName: null, version: 3, linkedRequestId: "request-one", availableColumns: [], changedAt: "2026-08-07T10:00:00Z" },
    { id: packageItem.id, itemType: "WORK_PACKAGE", reference: "WP-PACKAGE", title: packageItem.title, column: "READY", priority: "HIGH", dueOn: packageItem.dueOn, ownerUserId: "analyst-ssg", ownerDisplayName: "Lewis Ferguson", version: 2, linkedRequestId: null, availableColumns: ["IN_PROGRESS", "BLOCKED"], changedAt: "2026-08-06T10:00:00Z" },
  ],
  nextCursor: "cursor-next", columnCounts: { AWAITING_ASSIGNMENT: 0, BACKLOG: 0, READY: 1, IN_PROGRESS: 1, BLOCKED: 0, MANAGER_REVIEW: 0, QUALITY_REVIEW: 0, REWORK: 0, ON_HOLD: 0, COMPLETED: 0, CANCELLED: 0 }, totalCount: 2, wipLimits: { READY: 4, IN_PROGRESS: 3 }, configurationVersion: 2,
  savedViews: [{ id: "view-one", name: "My delivery", filters: { search: "product", columns: [], priorities: ["HIGH"], ownerUserId: "analyst-ssg", itemTypes: ["WORK_PACKAGE"], dueBefore: null }, version: 1 }], generatedAt: "2026-08-07T12:00:00Z",
};

describe("team workflow board", () => {
  it("renders workflow cards, inspects requests and creates packages", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();
    expect(screen.getByText("Customer request projection")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Quality Review" })).not.toBeInTheDocument();
    const requestCard = screen.getByRole("heading", { name: "Customer request projection" }).closest("article");
    await user.click(within(requestCard as HTMLElement).getByRole("button"));
    expect(await screen.findByRole("dialog", { name: "Work item details" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Customer requirement" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full request" })).toHaveAttribute("href", "/requests/request-one");
    await user.click(screen.getByRole("button", { name: "Close Work item details" }));
    await user.click(screen.getByRole("button", { name: "New work package" }));
    const createPackage = await screen.findByRole("dialog", { name: "Create work package" });
    fireEvent.change(await screen.findByLabelText(/^Title/, { selector: "input" }), { target: { value: "New synthetic package" } });
    fireEvent.change(screen.getByLabelText(/^Description/), { target: { value: "Complete detail for a second synthetic package." } });
    await user.selectOptions(within(createPackage).getByLabelText(/^Owner/), "analyst-ssg");
    await user.selectOptions(screen.getByLabelText(/^Contributor/), "analyst-ssg");
    fireEvent.change(screen.getByLabelText(/^Due date/), { target: { value: "2026-08-28" } });
    fireEvent.change(screen.getByLabelText(/^Blockers or none/), { target: { value: "No known blockers." } });
    fireEvent.change(screen.getByLabelText(/^Acceptance criteria/), { target: { value: "The complete fictional product is delivered." } });
    fireEvent.change(screen.getByLabelText(/^Linked request ID/), { target: { value: "request-two" } });
    await user.selectOptions(screen.getByLabelText(/^Iteration/), "iteration-active");
    await user.click(screen.getByRole("button", { name: "Create package" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/packages") && call.method === "POST" && call.body.linkedRequestId === "request-two" && call.body.iterationId === "iteration-active")).toBe(true));
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
    await waitFor(() => expect(calls.some((call) => call.path.includes("saved-views") && call.method === "POST")).toBe(true));
    await user.click(await screen.findByRole("button", { name: "Delete My delivery" }));
    await waitFor(() => expect(calls.some((call) => call.path.includes("saved-views") && call.method === "DELETE")).toBe(true));

    const packageCard = (await screen.findByRole("heading", { name: "Prepare synthetic product" })).closest("article");
    await user.click(within(packageCard as HTMLElement).getByRole("button"));
    await user.selectOptions(await screen.findByLabelText(/Move package to/), "IN_PROGRESS");
    await user.type(screen.getByLabelText(/^Reason/), "The package is ready for deliberate delivery work.");
    await user.click(screen.getByRole("button", { name: "Move package" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/board/moves") && call.body.target === "IN_PROGRESS")).toBe(true));
  });

  it("deep-links to a request and lets a Manager hasten all or one assigned Analyst", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    const assigned: RequestDetail = {
      ...requestDetail,
      id: "request-one",
      title: "Customer request projection",
      contributors: [{ id: "analyst-two", displayName: "Nathan Patterson" }],
      events: [],
    };
    mockBoard(
      managerSession,
      managerAccess,
      calls,
      { ...board, items: [] },
      false,
      assigned,
    );
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/board?itemId=request-one");
    const dialog = await screen.findByRole("dialog", { name: "Work item details" });
    expect(within(dialog).getByText("Rework", { selector: "dd" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Send hastener" }));
    expect(await screen.findByLabelText(/^Recipients/)).toHaveValue("ALL_ASSIGNED");
    await user.type(screen.getByLabelText(/^Message/), "Please confirm progress before this afternoon's review.");
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/hasteners") && call.body.audience === "ALL_ASSIGNED" && !call.body.recipientUserId)).toBe(true));
    expect(await screen.findByRole("status")).toHaveTextContent("Hastener sent and recorded");
    expect(await screen.findByText(/Hastener sent to Lewis Ferguson, Nathan Patterson/)).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Send hastener" }));
    await user.selectOptions(await screen.findByLabelText(/^Recipients/), "analyst-two");
    await user.type(screen.getByLabelText(/^Message/), "Please update your assigned contribution before the review.");
    await user.click(screen.getByRole("button", { name: "Send and record hastener" }));
    await waitFor(() => expect(calls.some((call) => call.body.audience === "ONE_ASSIGNED" && call.body.recipientUserId === "analyst-two")).toBe(true));
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

  it("filters board views, pages results and updates WIP limits", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Table" }));
    expect(screen.getByRole("table", { name: /Filtered team work/ })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search work"), "product");
    await user.click(screen.getByText(/Filters/));
    await user.selectOptions(screen.getByLabelText("Item type"), "WORK_PACKAGE");
    await user.selectOptions(screen.getByLabelText("Status"), "READY");
    await user.selectOptions(screen.getByLabelText("Priority"), "HIGH");
    await user.selectOptions(screen.getByLabelText("Owner"), "analyst-ssg");
    fireEvent.change(screen.getByLabelText("Due by"), { target: { value: "2026-08-31" } });
    expect(await screen.findByRole("table", { name: /Filtered team work/ })).toBeInTheDocument();
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Board" }));
    expect(await screen.findByRole("region", { name: "Team Kanban board" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table" }));
    await screen.findByRole("table", { name: /Filtered team work/ });
    await user.selectOptions(screen.getByLabelText("Item type"), "");
    await screen.findByRole("table", { name: /Filtered team work/ });
    fireEvent.change(screen.getByLabelText("Due by"), { target: { value: "" } });
    await user.selectOptions(await screen.findByLabelText("Status"), "");
    await user.selectOptions(await screen.findByLabelText("Priority"), "");
    await user.selectOptions(await screen.findByLabelText("Owner"), "");
    await screen.findByRole("table", { name: /Filtered team work/ });
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Page 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByText("Page 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Board settings" }));
    const wip = (await screen.findByRole("heading", { name: "Work in progress limits" })).closest("section");
    await user.clear(within(wip as HTMLElement).getByLabelText("Ready"));
    await user.type(within(wip as HTMLElement).getByLabelText("Ready"), "6");
    await user.click(within(wip as HTMLElement).getByRole("button", { name: "Save limits" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/board/configuration") && call.body.expectedVersion === 2)).toBe(true));
  });

  it("keeps Analyst controls scoped, reports empty and retries board failures", async () => {
    const calls: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
    mockBoard(analystSession, analystAccess, calls, { ...board, items: [], columnCounts: { ...board.columnCounts, READY: 0, IN_PROGRESS: 0 }, totalCount: 0, nextCursor: null, savedViews: [], wipLimits: {}, configurationVersion: 0 });
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "No work matches this view" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Work in progress limits" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New work package" }));
    await user.type(screen.getByLabelText(/^Title/, { selector: "input" }), "Analyst package");
    await user.type(screen.getByLabelText(/^Description/), "A complete package without optional links.");
    await user.selectOptions(screen.getByLabelText(/^Contributor/), "analyst-ssg");
    fireEvent.change(screen.getByLabelText(/^Due date/), { target: { value: "2026-08-30" } });
    await user.type(screen.getByLabelText(/^Blockers or none/), "No known blockers.");
    await user.type(screen.getByLabelText(/^Acceptance criteria/), "The package is complete.");
    await user.click(screen.getByRole("button", { name: "Create package" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/packages") && call.body.linkedRequestId === null && call.body.iterationId === null)).toBe(true));

    let attempts = 0;
    mockFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
      if (url.pathname.endsWith("/board")) { attempts += 1; return attempts === 1 ? json({ detail: "Unavailable" }, 503) : json(board); }
      if (url.pathname.endsWith("/people")) return json({ items: people });
      if (url.pathname.endsWith("/iterations")) return json({ items: [] });
      if (url.pathname.endsWith("/packages")) return json({ items: [packageItem] });
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Customer request projection")).toBeInTheDocument();
  });

  it("surfaces mutation errors without disclosing inaccessible content", async () => {
    mockBoard(managerSession, managerAccess, [], board, true);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByText("Prepare synthetic product")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Board settings" }));
    await user.click(screen.getByRole("button", { name: "Save limits" }));
    expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent?.includes("Planning conflict"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "Close Board settings" }));
    const packageCard = screen.getByRole("heading", { name: "Prepare synthetic product" }).closest("article");
    await user.click(within(packageCard as HTMLElement).getByRole("button"));
    await user.selectOptions(screen.getByLabelText(/Move package to/), "IN_PROGRESS");
    await user.type(screen.getByLabelText(/^Reason/), "The package is ready for deliberate delivery work.");
    await user.click(screen.getByRole("button", { name: "Move package" }));
    expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent?.includes("Planning conflict"))).toBe(true);
  });

  it("fails closed and recovers all required queries after an outage", async () => {
    const attempts = { board: 0, people: 0, iterations: 0 };
    mockFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
      if (url.pathname.endsWith("/board")) { attempts.board += 1; return attempts.board === 1 ? json({ detail: "Unavailable" }, 503) : json(board); }
      if (url.pathname.endsWith("/iterations")) { attempts.iterations += 1; return attempts.iterations === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: iterations }); }
      if (url.pathname.endsWith("/people")) { attempts.people += 1; return attempts.people === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: people }); }
      if (url.pathname.endsWith("/packages")) return json({ items: [packageItem] });
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/board");
    expect(await screen.findByRole("heading", { name: "Team delivery could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Team delivery" })).toBeInTheDocument();
    expect(attempts).toEqual({ board: 2, people: 2, iterations: 2 });
  });
});

function mockBoard(session: Session, access: TeamWorkspaceAccess, calls: Array<{ path: string; method: string; body: Record<string, unknown> }>, value: BoardResult = board, failMutations = false, initialRequest: RequestDetail = { ...requestDetail, id: "request-one", title: "Customer request projection" }, deepLinkedItem: BoardItem | null = { ...board.items[0], column: "REWORK" }) {
  let requestValue = initialRequest;
  return mockFetch(async (url, init) => {
    const method = init.method ?? "GET";
    const body = init.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {};
    if (method !== "GET") calls.push({ path: url.pathname, method, body });
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
    if (url.pathname.endsWith("/people")) return json({ items: people });
    if (url.pathname.endsWith("/iterations")) return json({ items: iterations });
    if (url.pathname.endsWith("/board") && method === "GET") return json(value);
    if (url.pathname.endsWith("/board/requests/request-one") && method === "GET") {
      return deepLinkedItem ? json(deepLinkedItem) : json({ detail: "Not found" }, 404);
    }
    if (url.pathname.endsWith("/packages") && method === "GET") return json({ items: [packageItem] });
    if (url.pathname.endsWith("/requests/request-one") && method === "GET") return json(requestValue);
    if (url.pathname.endsWith("/hasteners") && method === "POST") {
      const recipientNames = body.audience === "ALL_ASSIGNED" ? "Lewis Ferguson, Nathan Patterson" : "Nathan Patterson";
      requestValue = { ...requestValue, events: [...requestValue.events, { id: `hastener-${requestValue.events.length}`, type: "task_hastener", message: `Hastener sent to ${recipientNames}: ${body.message}`, actorDisplayName: session.user.displayName, createdAt: "2026-08-11T10:00:00Z" }] };
      return json({ eventId: "event-hastener", requestId: "request-one", message: body.message, senderDisplayName: session.user.displayName, recipients: [], createdAt: "2026-08-11T10:00:00Z" });
    }
    if (failMutations && method !== "GET") return json({ detail: "Planning conflict" }, 409);
    if (url.pathname.includes("saved-views") && method === "DELETE") return new Response(null, { status: 204 });
    if (url.pathname.includes("saved-views")) return json(value.savedViews[0] ?? { id: "new-view", name: "Urgent work", filters: { search: "", columns: [], priorities: [], ownerUserId: null, itemTypes: [], dueBefore: null }, version: 1 });
    if (url.pathname.endsWith("/board/configuration")) return json({ wipLimits: body.wipLimits, version: 3 });
    if (url.pathname.endsWith("/board/moves") || url.pathname.endsWith("/packages")) return json(packageItem);
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, true, false);
}
