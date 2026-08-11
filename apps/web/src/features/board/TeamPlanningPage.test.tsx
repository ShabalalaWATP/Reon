import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Iteration, WorkPackage } from "../../lib/api/boardTypes";
import type { Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const session: Session = { ...requesterSession, user: { ...requesterSession.user, id: "manager-ssg", username: "admin8", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", scope: "SSG Team" } };
const access: TeamWorkspaceAccess = { teamId: "team-ssg", teamCode: "SSG_TEAM", teamName: "SSG Team", grantId: "grant-ssg", permissions: ["BOARD", "CAPACITY"] };
const analystAccess: TeamWorkspaceAccess = { ...access, grantId: null, permissions: [] };
const members: TeamMember[] = [
  { membershipId: "manager", accountId: "manager-ssg", displayName: "Grant Hanley", role: "DELIVERY_TEAM_LEAD", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 0, skills: ["Delivery leadership"], startReason: null, endReason: null },
  { membershipId: "analyst", accountId: "analyst-ssg", displayName: "Lewis Ferguson", role: "DELIVERY_SPECIALIST", state: "CURRENT", effectiveFrom: "2026-01-01T09:00:00Z", effectiveUntil: null, version: 1, activeWorkCount: 1, skills: ["Research"], startReason: null, endReason: null },
];
const iteration: Iteration = { id: "iteration-one", name: "Pilot iteration", goal: "Deliver a synthetic customer product.", startsOn: "2026-08-01", endsOn: "2026-08-14", status: "ACTIVE", completionSummary: null, version: 1 };
const workPackage: WorkPackage = {
  id: "package-one", teamId: "team-ssg", linkedRequestId: "request-one", iterationId: iteration.id,
  title: "Prepare synthetic product", description: "Complete the fictional customer-facing service product.",
  ownerUserId: "analyst-ssg", ownerDisplayName: "Lewis Ferguson", contributors: [{ userId: "manager-ssg", displayName: "Grant Hanley" }],
  estimatePoints: 5, remainingEffortMinutes: 180, dueOn: "2026-08-20", priority: "HIGH", status: "IN_PROGRESS",
  blockers: "No known blockers.", acceptanceCriteria: "Customer outcomes are addressed.", dependencyIds: ["package-dependency"], version: 4,
  activities: [{ id: "activity", type: "MOVED", summary: "Work package moved to in progress.", actorDisplayName: "Grant Hanley", createdAt: "2026-08-07T11:00:00Z" }],
  reservations: [{ id: "reservation-one", userId: "analyst-ssg", userDisplayName: "Lewis Ferguson", startsAt: "2026-08-09T09:00:00Z", endsAt: "2026-08-09T11:00:00Z", minutes: 120, status: "ACTIVE", reason: "Protected focus time.", version: 1 }],
};
const closedIteration: Iteration = { ...iteration, id: "iteration-closed", name: "Closed iteration", status: "CLOSED", completionSummary: "Complete.", version: 2 };
const sparsePackage: WorkPackage = {
  ...workPackage,
  id: "package-two",
  title: "Archive planning record",
  linkedRequestId: null,
  iterationId: null,
  contributors: [],
  dependencyIds: [],
  activities: [],
  reservations: [{ ...workPackage.reservations[0], id: "reservation-cancelled", status: "CANCELLED" }],
};

describe("team agile planning", () => {
  it("shows package history and lets a Manager plan iterations and capacity", async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    mockPlanning(access, [workPackage, sparsePackage], [iteration, closedIteration], calls);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/planning");
    expect(await screen.findByRole(
      "heading",
      { name: "Team planning" },
      { timeout: 5_000 },
    )).toBeInTheDocument();
    expect(screen.getByText("Work package moved to in progress. · Grant Hanley")).toBeInTheDocument();
    expect(screen.getByText("package-dependency")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();

    const edit = screen.getByRole("heading", { name: "Edit or hand over package" }).closest("section");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit title/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit title/), "Reassigned synthetic product");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit description/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit description/), "Replanned after a deliberate Manager handover.");
    await user.selectOptions(within(edit as HTMLElement).getByLabelText(/^Edit owner/), "manager-ssg");
    await user.selectOptions(within(edit as HTMLElement).getByLabelText(/^Edit contributors/), "analyst-ssg");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit estimate points/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit estimate points/), "8");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit remaining minutes/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit remaining minutes/), "240");
    fireEvent.change(within(edit as HTMLElement).getByLabelText(/^Edit due date/), { target: { value: "2026-08-21" } });
    await user.selectOptions(within(edit as HTMLElement).getByLabelText(/^Edit priority/), "URGENT");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit blockers/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit blockers/), "Awaiting synthetic peer review.");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit acceptance criteria/));
    await user.type(within(edit as HTMLElement).getByLabelText(/^Edit acceptance criteria/), "The handed-over package passes review.");
    await user.clear(within(edit as HTMLElement).getByLabelText(/^Edit linked request ID/));
    await user.selectOptions(within(edit as HTMLElement).getByLabelText(/^Edit iteration/), "");
    await user.selectOptions(within(edit as HTMLElement).getByLabelText(/^Edit dependencies/), sparsePackage.id);
    await user.click(within(edit as HTMLElement).getByRole("button", { name: "Save package" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/packages/package-one") && call.body.ownerUserId === "manager-ssg")).toBe(true));

    const reservation = screen.getByRole("heading", { name: "Reserve effort" }).closest(".reservation-panel");
    await user.selectOptions(within(reservation as HTMLElement).getByLabelText(/^Person/), "analyst-ssg");
    await user.type(within(reservation as HTMLElement).getByLabelText(/^Reason/), "Reserve focused time for the synthetic service product.");
    await user.click(within(reservation as HTMLElement).getByRole("button", { name: "Reserve capacity" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/reservations") && call.body.userId === "analyst-ssg")).toBe(true));

    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/cancel"))).toBe(true));

    const create = screen.getByRole("heading", { name: "Create iteration" }).closest("section");
    await user.type(within(create as HTMLElement).getByLabelText(/^Name/), "Second iteration");
    await user.type(within(create as HTMLElement).getByLabelText(/^Goal/), "Deliver the next complete fictional product.");
    fireEvent.change(within(create as HTMLElement).getByLabelText(/^Starts/), { target: { value: "2026-08-15" } });
    fireEvent.change(within(create as HTMLElement).getByLabelText(/^Ends/), { target: { value: "2026-08-28" } });
    await user.click(within(create as HTMLElement).getByRole("button", { name: "Create iteration" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/iterations") && call.body.name === "Second iteration")).toBe(true));

    await user.selectOptions(await screen.findByLabelText(/^Iteration/), iteration.id);
    await user.type(screen.getByLabelText(/^Completion summary/), "The complete synthetic goal was achieved.");
    await user.click(screen.getByRole("button", { name: "Close iteration" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/close") && call.body.expectedVersion === 1)).toBe(true));

    await user.selectOptions(screen.getByLabelText(/^Package/), sparsePackage.id);
    expect(screen.getByRole("heading", { name: "Archive planning record" })).toBeInTheDocument();
    expect(screen.getAllByText("None")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  }, 30_000);

  it("keeps iteration management out of the Analyst view and handles empty planning", async () => {
    mockPlanning(analystAccess, [], [], []);
    renderApp("/teams/team-ssg/planning");
    expect(await screen.findByRole(
      "heading",
      { name: "No work packages" },
      { timeout: 5_000 },
    )).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Create iteration" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close iteration" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Edit or hand over package" })).not.toBeInTheDocument();
  });

  it("retries failed reads and reports planning mutation conflicts", async () => {
    let packageAttempts = 0;
    mockFeatureFetch(async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
      if (url.pathname.endsWith("/packages")) { packageAttempts += 1; return packageAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: [workPackage] }); }
      if (url.pathname.endsWith("/iterations") && !init.method) return json({ items: [iteration] });
      if (url.pathname.endsWith("/people")) return json({ items: members });
      if (init.method) return json({ detail: "Planning conflict" }, 409);
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/planning");
    expect(await screen.findByRole(
      "heading",
      { name: "Team planning could not be loaded" },
      { timeout: 5_000 },
    )).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect((await screen.findAllByText("Prepare synthetic product")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Save package" }));
    expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent?.includes("Planning conflict"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent?.includes("Planning conflict"))).toBe(true);
    const reservation = screen.getByRole("heading", { name: "Reserve effort" }).closest(".reservation-panel");
    await user.selectOptions(within(reservation as HTMLElement).getByLabelText(/^Person/), "analyst-ssg");
    await user.type(within(reservation as HTMLElement).getByLabelText(/^Reason/), "This reservation is expected to conflict.");
    await user.click(within(reservation as HTMLElement).getByRole("button", { name: "Reserve capacity" }));
    await waitFor(() => expect(screen.getAllByRole("alert").length).toBeGreaterThan(0));
    const create = screen.getByRole("heading", { name: "Create iteration" }).closest("section");
    await user.type(within(create as HTMLElement).getByLabelText(/^Name/), "Conflicting iteration");
    await user.type(within(create as HTMLElement).getByLabelText(/^Goal/), "Exercise the conflict response.");
    fireEvent.change(within(create as HTMLElement).getByLabelText(/^Starts/), { target: { value: "2026-08-15" } });
    fireEvent.change(within(create as HTMLElement).getByLabelText(/^Ends/), { target: { value: "2026-08-28" } });
    await user.click(within(create as HTMLElement).getByRole("button", { name: "Create iteration" }));
    await waitFor(() => expect(screen.getAllByRole("alert").length).toBeGreaterThan(1));
    await user.selectOptions(screen.getByLabelText(/^Iteration/), iteration.id);
    await user.type(screen.getByLabelText(/^Completion summary/), "This close is expected to conflict.");
    await user.click(screen.getByRole("button", { name: "Close iteration" }));
    expect((await screen.findAllByRole("alert")).every((alert) => alert.textContent?.includes("Planning conflict"))).toBe(true);
  });
});

function mockPlanning(workspace: TeamWorkspaceAccess, packages: WorkPackage[], iterations: Iteration[], calls: Array<{ path: string; body: Record<string, unknown> }>) {
  return mockFeatureFetch(async (url, init) => {
    const body = init.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {};
    if (init.method) calls.push({ path: url.pathname, body });
    if (url.pathname.endsWith("/auth/me")) return json(workspace.grantId ? session : { ...session, user: { ...session.user, id: "analyst-ssg", role: "DELIVERY_SPECIALIST" } });
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/team-workspaces")) return json({ items: [workspace] });
    if (url.pathname.endsWith("/people")) return json({ items: members });
    if (url.pathname.endsWith("/packages") && !init.method) return json({ items: packages });
    if (url.pathname.includes("/packages/") && init.method === "PUT") return json({ ...workPackage, ...body, version: workPackage.version + 1 });
    if (url.pathname.endsWith("/iterations") && !init.method) return json({ items: iterations });
    if (url.pathname.endsWith("/iterations") || url.pathname.endsWith("/close")) return json(iteration);
    if (url.pathname.includes("/reservations")) return json(workPackage);
    throw new Error(`Unexpected ${url.pathname}`);
  }, true, true, false);
}
