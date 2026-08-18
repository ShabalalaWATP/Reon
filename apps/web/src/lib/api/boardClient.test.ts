import { describe, expect, it } from "vitest";

import { json, mockFetch } from "../../test/render";
import { boardApi } from "./boardClient";
import type { BoardFilters, WorkPackageInput } from "./boardTypes";

const filters: BoardFilters = {
  search: "customer & product",
  columns: ["READY", "IN_PROGRESS"],
  priorities: ["HIGH", "URGENT"],
  ownerUserId: "analyst one",
  itemTypes: ["SERVICE_REQUEST", "WORK_PACKAGE"],
  dueBefore: "2026-08-31",
};

const packageInput: WorkPackageInput = {
  grantId: "grant-one",
  title: "Prepare product",
  description: "Prepare the complete synthetic product.",
  ownerUserId: "analyst-one",
  contributorIds: ["manager-one"],
  estimatePoints: 5,
  remainingEffortMinutes: 180,
  dueOn: "2026-08-31",
  priority: "HIGH",
  blockers: "No known blockers.",
  acceptanceCriteria: "The complete product is ready.",
  linkedRequestId: "request-one",
  dependencyIds: ["package-two"],
  iterationId: "iteration-one",
};

describe("board API client", () => {
  it("serialises board filters and calls every team planning endpoint", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    mockFetch(
      (url, init) => {
        calls.push({ path: `${url.pathname}${url.search}`, init });
        if (init.method === "DELETE") return new Response(null, { status: 204 });
        return json({ items: [], id: "result", filters, wipLimits: {}, version: 1 });
      },
      {
        emptyDraftRegister: false,
        emptyStatisticsScopes: false,
        emptyTeamWorkspaces: false,
      },
    );

    await boardApi.board("team one");
    await boardApi.board("team one", filters, { cursor: "cursor one", limit: 25 });
    await boardApi.boardRequest("team one", "request one");
    await boardApi.moveItem(
      "team one",
      {
        grantId: null,
        itemType: "WORK_PACKAGE",
        itemId: "package-one",
        target: "READY",
        expectedVersion: 1,
        reason: "Ready for delivery.",
      },
      "csrf",
    );
    await boardApi.configure(
      "team one",
      { grantId: "grant-one", expectedVersion: 1, wipLimits: { READY: 4 } },
      "csrf",
    );
    await boardApi.createView("team one", { name: "Urgent work", filters }, "csrf");
    await boardApi.updateView(
      "team one",
      "view one",
      { name: "Updated view", filters, expectedVersion: 2 },
      "csrf",
    );
    await boardApi.deleteView("team one", "view one", 3, "csrf");
    await boardApi.packages("team one");
    await boardApi.package("team one", "package one");
    await boardApi.createPackage("team one", packageInput, "csrf");
    await boardApi.updatePackage(
      "team one",
      "package one",
      { ...packageInput, expectedVersion: 2 },
      "csrf",
    );
    await boardApi.movePackage(
      "team one",
      "package one",
      {
        grantId: null,
        expectedVersion: 3,
        target: "BLOCKED",
        reason: "Waiting for customer information.",
      },
      "csrf",
    );
    await boardApi.reserve(
      "team one",
      "package one",
      4,
      {
        grantId: "grant-one",
        userId: "analyst-one",
        startsAt: "2026-08-08T09:00:00Z",
        endsAt: "2026-08-08T11:00:00Z",
        reason: "Focused delivery time.",
      },
      "csrf",
    );
    await boardApi.cancelReservation(
      "team one",
      "package one",
      "reservation one",
      5,
      { grantId: "grant-one", expectedVersion: 1, reason: "Replanned by the team." },
      "csrf",
    );
    await boardApi.iterations("team one");
    await boardApi.createIteration(
      "team one",
      {
        grantId: "grant-one",
        name: "Pilot",
        goal: "Deliver the product.",
        startsOn: "2026-08-01",
        endsOn: "2026-08-14",
      },
      "csrf",
    );
    await boardApi.closeIteration(
      "team one",
      "iteration one",
      { grantId: "grant-one", expectedVersion: 2, completionSummary: "The goal was achieved." },
      "csrf",
    );

    expect(calls).toHaveLength(18);
    expect(calls[0].path).toBe("/api/v1/team-workspaces/team%20one/board");
    expect(calls[1].path).toContain("search=customer+%26+product");
    expect(calls[1].path).toContain("column=READY&column=IN_PROGRESS");
    expect(calls[1].path).toContain("priority=HIGH&priority=URGENT");
    expect(calls[1].path).toContain("itemType=SERVICE_REQUEST&itemType=WORK_PACKAGE");
    expect(calls[1].path).toContain("ownerId=analyst+one");
    expect(calls[1].path).toContain("dueBefore=2026-08-31");
    expect(calls[1].path).toContain("cursor=cursor+one");
    expect(calls[1].path).toContain("limit=25");
    expect(calls[2].path).toContain("board/requests/request%20one");
    expect(calls[3].init.method).toBe("POST");
    expect(calls[4].init.method).toBe("PUT");
    expect(calls[7].init.method).toBe("DELETE");
    expect(calls[9].path).toContain("package%20one");
    expect(calls[13].path).toContain("packageVersion=4");
    expect(calls[14].path).toContain("reservation%20one/cancel?packageVersion=5");
    expect(calls[17].path).toContain("iteration%20one/close");
    expect(new Headers(calls[17].init.headers).get("X-CSRF-Token")).toBe("csrf");
    expect(calls.every((call) => call.init.credentials === "include")).toBe(true);
  });
});
