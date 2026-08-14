import { describe, expect, it } from "vitest";

import { json, mockFetch } from "../../test/render";
import { api, ApiError, productDownloadUrl, SESSION_EXPIRED_EVENT } from "./client";
import {
  adminManagedUser,
  organisationUnits,
  requestDetail,
  requestSummary,
  requesterSession,
  trackedRequest,
  workItem,
} from "../../test/fixtures";

describe("API client", () => {
  it("calls every endpoint with cookies, JSON and CSRF protection", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    const draft = {
      id: "draft-id",
      requesterId: requesterSession.user.id,
      title: "Draft title",
      version: 1,
      createdAt: requestDetail.createdAt,
      updatedAt: requestDetail.updatedAt,
    };
    mockFetch(
      (url, init) => {
        calls.push({ path: `${url.pathname}${url.search}`, init });
        if (url.pathname.endsWith("/auth/logout")) return new Response(null, { status: 204 });
        if (url.pathname.endsWith("/auth/login") || url.pathname.endsWith("/auth/me"))
          return json(requesterSession);
        if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [] });
        if (url.pathname.endsWith("/statistics")) return json({ summary: [] });
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [] });
        if (url.pathname.includes("/team-workspaces/")) return json({ items: [] });
        if (url.pathname.includes("/admin/users"))
          return url.pathname.endsWith("/admin/users")
            ? json({ items: [adminManagedUser] })
            : json(adminManagedUser);
        if (url.pathname.endsWith("/feedback"))
          return json({
            id: "feedback",
            rating: 5,
            comments: "Very useful.",
            createdAt: requestDetail.updatedAt,
          });
        if (url.pathname.endsWith("/request-drafts/draft-id/submit")) return json(requestDetail);
        if (url.pathname.endsWith("/request-drafts/draft-id") && init.method === "DELETE")
          return new Response(null, { status: 204 });
        if (url.pathname.endsWith("/request-drafts/draft-id")) return json(draft);
        if (url.pathname.endsWith("/request-drafts"))
          return init.method === "POST" ? json(draft) : json({ items: [draft] });
        if (url.pathname.endsWith("/claim")) return json(workItem);
        if (url.pathname.endsWith("/complete")) return json(requestDetail);
        if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
        if (url.pathname.endsWith("/tracked-requests")) return json({ items: [trackedRequest] });
        if (url.pathname.endsWith("/routing-options")) return json({ items: organisationUnits });
        if (url.pathname.endsWith("/eligible-specialists")) {
          return json({ items: [{ id: "specialist-id", displayName: "Eligible colleague" }] });
        }
        if (url.pathname.endsWith("/work-items")) return json({ items: [workItem] });
        if (url.pathname.endsWith("/requests") && init.method === "POST")
          return json(requestDetail);
        if (url.pathname.endsWith("/requests")) return json({ items: [requestSummary] });
        return json(requestDetail);
      },
      false,
      false,
      false,
    );

    await api.login({ username: "admin2", password: "admin" });
    await api.session();
    await api.statisticsScopes();
    await api.statistics({
      scopeId: "scope & one",
      unitId: "unit/one",
      from: "2026-08-01",
      to: "2026-08-07",
      timeZone: "Europe/London",
    });
    await api.logout("token");
    await api.requests();
    await api.request("id with space");
    await api.createRequest(requestDetail, "token");
    await api.feedback(requestDetail.id, { rating: 5, comments: "Very useful." }, "token");
    await api.workItems();
    await api.organisationUnits();
    await api.trackedRequests();
    await api.routingOptions("route item");
    await api.eligibleSpecialists("work item");
    await api.claimWorkItem(workItem.id, "token");
    await api.completeWorkItem(workItem.id, { action: "approve" }, "token");
    await api.adminUsers("John & Erin");
    await api.adminUser("managed user");
    await api.createAdminUser(
      {
        displayName: "New User",
        email: "new@example.test",
        role: "REQUESTER",
        scope: "Area",
        organisationUnitIds: [],
      },
      "token",
    );
    await api.updateAdminUser(
      "managed user",
      {
        displayName: "New Name",
        email: "new@example.test",
        role: "REQUESTER",
        scope: "Area",
        organisationUnitIds: [],
        expectedVersion: 2,
      },
      "token",
    );
    await api.updateAdminUserStatus(
      "managed user",
      { isActive: false, expectedVersion: 3 },
      "token",
    );
    await api.renameOrganisationUnit("unit id", { name: "New name", expectedVersion: 4 }, "token");
    await api.drafts();
    await api.draft("draft-id");
    await api.createDraft({ title: "Draft title" }, "token");
    await api.updateDraft("draft-id", { title: "Updated", expectedVersion: 1 }, "token");
    await api.deleteDraft("draft-id", 2, "token");
    await api.submitDraft("draft-id", { ...requestDetail, expectedVersion: 2 }, "token");
    await api.teamWorkspaces();
    await api.teamWorkspace("team id");
    await api.teamPeople("team id");
    await api.eligibleRosterAnalysts("team id", "grant id");
    await api.teamActivity("team id");
    await api.addTeamMember(
      "team id",
      { grantId: "grant", analystId: "analyst", reason: "A sufficiently long reason." },
      "token",
    );
    await api.transferTeamMember(
      "team id",
      {
        grantId: "grant",
        analystId: "analyst",
        reason: "A sufficiently long reason.",
        currentMembershipId: "membership",
        expectedVersion: 2,
        effectiveFrom: "2026-08-09T10:00:00Z",
      },
      "token",
    );
    await api.endTeamMembership(
      "team id",
      "membership id",
      { grantId: "grant", expectedVersion: 2, reason: "A sufficiently long reason." },
      "token",
    );
    const calendarInput = {
      title: "Protected time",
      notes: "Required detail",
      startsAt: "2026-08-09T09:00:00Z",
      endsAt: "2026-08-09T10:00:00Z",
      timeZone: "Europe/London",
      allDay: false,
      category: "OTHER" as const,
      visibility: "PRIVATE" as const,
      recurrence: "NONE" as const,
      recurrenceInterval: 1,
      recurrenceUntil: null,
    };
    await api.personalCalendar("2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z");
    await api.teamCalendar("team id", "2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z");
    await api.createPersonalCalendarEvent(calendarInput, "token");
    await api.createTeamCalendarEvent("team id", { ...calendarInput, grantId: "grant" }, "token");
    await api.createCalendarCommitment(
      "team id",
      { ...calendarInput, grantId: "grant", requestId: "request", subjectUserId: "analyst" },
      "token",
    );
    await api.updateCalendarEvent("event id", { ...calendarInput, expectedVersion: 1 }, "token");
    await api.cancelCalendarEvent(
      "event id",
      {
        expectedVersion: 2,
        occurrenceStart: calendarInput.startsAt,
        reason: "A sufficiently long reason.",
      },
      "token",
    );
    await api.cancelCalendarOccurrence(
      "event id",
      {
        expectedVersion: 2,
        occurrenceStart: calendarInput.startsAt,
        reason: "A sufficiently long reason.",
      },
      "token",
    );
    await api.editCalendarOccurrence(
      "event id",
      {
        expectedVersion: 2,
        occurrenceStart: calendarInput.startsAt,
        reason: "A sufficiently long reason.",
        title: calendarInput.title,
        notes: calendarInput.notes,
        replacementStart: calendarInput.startsAt,
        replacementEnd: calendarInput.endsAt,
      },
      "token",
    );
    await api.splitCalendarSeries(
      "event id",
      {
        ...calendarInput,
        recurrence: "DAILY",
        recurrenceUntil: "2026-08-12T09:00:00Z",
        expectedVersion: 3,
        splitFrom: calendarInput.startsAt,
        reason: "A sufficiently long reason.",
      },
      "token",
    );
    await api.decideCalendarCommitment(
      "event id",
      { expectedVersion: 1, reason: null },
      true,
      "token",
    );
    await api.previewTeamCapacity(
      "team id",
      { grantId: "grant", dateFrom: "2026-08-01", dateTo: "2026-08-07", timeZone: "Europe/London" },
      "token",
    );
    await api.commitTeamCapacity(
      "team id",
      { grantId: "grant", token: "preview-token-value-that-is-long-enough" },
      "token",
    );
    await api.requestConversations("request id");
    await api.postConversationMessage(
      "request id",
      {
        body: "Please confirm the current position.",
        clientMutationId: "99999999-9999-4999-8999-999999999999",
        targetType: "CURRENT_OWNER",
      },
      "token",
    );
    await api.requestConversations("request id", "opaque cursor/+=");
    await api.conversationMessages("request id", "conversation id", "message cursor/+=");
    await api.markConversationRead("request id", "conversation id", "token");

    expect(calls).toHaveLength(54);
    expect(calls.every((call) => call.init.credentials === "include")).toBe(true);
    expect(calls[3].path).toContain("scopeId=scope+%26+one");
    expect(calls[6].path).toContain("id%20with%20space");
    expect(calls[12].path).toBe("/api/v1/work-items/route%20item/routing-options");
    expect(calls[13].path).toBe("/api/v1/work-items/work%20item/eligible-specialists");
    expect(calls[13].init.method).toBeUndefined();
    expect(new Headers(calls[13].init.headers).get("X-CSRF-Token")).toBeNull();
    expect(new Headers(calls[7].init.headers).get("X-CSRF-Token")).toBe("token");
    expect(calls[7].init.body).toContain("Quarterly service readiness");
    expect(new Headers(calls[0].init.headers).get("Content-Type")).toBe("application/json");
    expect(new Headers(calls[1].init.headers).get("Content-Type")).toBeNull();
    expect(calls[16].path).toBe("/api/v1/admin/users?query=John%20%26%20Erin");
    expect(calls[17].path).toBe("/api/v1/admin/users/managed%20user");
    expect(calls[18].init.method).toBe("POST");
    expect(calls[19].init.method).toBe("PATCH");
    expect(calls[20].init.body).toBe(JSON.stringify({ isActive: false, expectedVersion: 3 }));
    expect(calls[21].path).toBe("/api/v1/admin/organisation/units/unit%20id");
    expect(calls[22].path).toBe("/api/v1/request-drafts");
    expect(calls[26].path).toBe("/api/v1/request-drafts/draft-id?expectedVersion=2");
    expect(calls[27].path).toBe("/api/v1/request-drafts/draft-id/submit");
    expect(calls[28].path).toBe("/api/v1/team-workspaces");
    expect(calls[31].path).toContain("grantId=grant%20id");
    expect(calls[35].path).toContain("membership%20id/end");
    expect(calls[48].path).toContain("team%20id/capacity/commits");
    expect(calls[49].path).toBe(
      "/api/v1/requests/request%20id/conversations?limit=20&messageLimit=50",
    );
    expect(calls[50].path).toBe("/api/v1/requests/request%20id/conversations/messages");
    expect(calls[50].init.method).toBe("POST");
    expect(calls[51].path).toContain("cursor=opaque+cursor%2F%2B%3D");
    expect(calls[52].path).toContain(
      "conversations/conversation%20id?limit=50&cursor=message%20cursor%2F%2B%3D",
    );
    expect(calls[53].path).toBe(
      "/api/v1/requests/request%20id/conversations/conversation%20id/read",
    );
    expect(calls[53].init.method).toBe("POST");
    expect(productDownloadUrl("id with space")).toBe("/api/v1/requests/id%20with%20space/product");
  });

  it.each([
    [
      { detail: { code: "AUTHENTICATION_FAILED", message: "Unable to sign in." } },
      "Unable to sign in.",
      "AUTHENTICATION_FAILED",
    ],
    [{ detail: "Plain detail" }, "Plain detail", undefined],
    [{ code: "TOP_LEVEL", message: "Top-level message" }, "Top-level message", "TOP_LEVEL"],
    [{ detail: [] }, "Request failed with status 422.", undefined],
  ])("normalises JSON error responses", async (body, message, code) => {
    mockFetch(() => json(body, 422));
    const error = await api.session().catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message, code, status: 422 });
  });

  it("uses a status fallback for non-JSON errors", async () => {
    mockFetch(() => new Response("unavailable", { status: 503 }));
    await expect(api.session()).rejects.toMatchObject({
      message: "Request failed with status 503.",
      status: 503,
    });
  });

  it("announces expiry when a protected request returns 401", async () => {
    let expired = false;
    window.addEventListener(
      SESSION_EXPIRED_EVENT,
      () => {
        expired = true;
      },
      { once: true },
    );
    mockFetch(() => json({ detail: "Session expired" }, 401));
    await expect(api.requests()).rejects.toMatchObject({ status: 401 });
    expect(expired).toBe(true);
  });
});
