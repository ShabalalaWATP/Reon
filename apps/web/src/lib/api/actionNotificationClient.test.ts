import { describe, expect, it } from "vitest";

import { json, mockFetch } from "../../test/render";
import { actionNotificationApi } from "./actionNotificationClient";
import type { NotificationPreference, PersonalNotification, SavedActionViewInput } from "./actionNotificationTypes";

const view: SavedActionViewInput = {
  name: "Urgent reviews",
  filters: { sections: ["NEEDS_MY_ACTION"], actionTypes: ["LEAD_REVIEW"], dueBefore: "2026-08-12" },
  visibleColumns: ["REFERENCE", "REQUIRED_BY"],
};

describe("action and notification API client", () => {
  it("encodes action filters and protects saved-view mutations", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    mockFetch((url, init) => {
      calls.push({ path: `${url.pathname}${url.search}`, init });
      return init.method === "DELETE" ? new Response(null, { status: 204 }) : json({ id: "view/one", ...view, version: 2 });
    }, true, true, true, false);

    await actionNotificationApi.actions({ ...view.filters, cursor: "next page", limit: 20 });
    await actionNotificationApi.createActionView(view, "csrf");
    await actionNotificationApi.updateActionView("view/one", { ...view, expectedVersion: 2 }, "csrf");
    await actionNotificationApi.deleteActionView("view/one", 3, "csrf");

    expect(calls[0].path).toBe("/api/v1/me/actions?sections=NEEDS_MY_ACTION&actionTypes=LEAD_REVIEW&dueBefore=2026-08-12&limit=20&cursor=next+page");
    expect(calls.slice(1).map(({ path, init }) => [path, init.method, new Headers(init.headers).get("X-CSRF-Token")])).toEqual([
      ["/api/v1/me/actions/saved-views", "POST", "csrf"],
      ["/api/v1/me/actions/saved-views/view%2Fone", "PATCH", "csrf"],
      ["/api/v1/me/actions/saved-views/view%2Fone?expectedVersion=3", "DELETE", "csrf"],
    ]);
    expect(JSON.parse(calls[2].init.body as string)).toMatchObject({ expectedVersion: 2 });
  });

  it("encodes notification filters, state targets and preferences", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    mockFetch((url, init) => {
      calls.push({ path: `${url.pathname}${url.search}`, init });
      return json({ items: [], groups: [], unreadCount: 2, projectedAt: null });
    }, true, true, true, true, false);
    const item = { id: "notice-1", version: 4 } as PersonalNotification;
    const preference = { eventGroup: "RELEASE/SAFETY", version: 7 } as NotificationPreference;

    await actionNotificationApi.notifications({ states: ["UNREAD", "READ"], eventTypes: ["ASSIGNED"], fromDate: "2026-08-01", toDate: "2026-08-07", cursor: "page two", limit: 10 });
    await actionNotificationApi.notificationCount();
    await actionNotificationApi.updateNotificationState("MARK_READ", [item], "csrf");
    await actionNotificationApi.notificationPreferences();
    await actionNotificationApi.updateNotificationPreference(preference, false, [1, 3], "csrf");

    expect(calls.map(({ path }) => path)).toEqual([
      "/api/v1/me/notifications?states=UNREAD&states=READ&eventTypes=ASSIGNED&from=2026-08-01T00%3A00%3A00.000Z&to=2026-08-07T23%3A59%3A59.999Z&limit=10&cursor=page+two",
      "/api/v1/me/notifications/count",
      "/api/v1/me/notifications/state",
      "/api/v1/me/notifications/preferences",
      "/api/v1/me/notifications/preferences/RELEASE%2FSAFETY",
    ]);
    expect(JSON.parse(calls[2].init.body as string)).toEqual({ action: "MARK_READ", targets: [{ id: "notice-1", expectedVersion: 4 }] });
    expect(JSON.parse(calls[4].init.body as string)).toEqual({ enabled: false, reminderDays: [1, 3], expectedVersion: 7 });
    expect(calls[2].init.method).toBe("POST");
    expect(calls[4].init.method).toBe("PATCH");
  });
});
