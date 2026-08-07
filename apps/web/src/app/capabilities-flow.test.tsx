import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ServerCapabilities } from "../lib/api/capabilityClient";
import type { ActionWorkspace, NotificationList } from "../lib/api/actionNotificationTypes";
import { requesterSession } from "../test/fixtures";
import { json, mockFeatureFetch, mockFetch, renderApp } from "../test/render";

const enabled: ServerCapabilities = {
  myWork: true,
  notifications: true,
  configuration: true,
  products: true,
  managedFileUploads: true,
  planning: true,
  statistics: true,
};
const freshness = { status: "CURRENT" as const, projectedAt: null, sourceChangedAt: null, lagSeconds: null, pendingCount: 0 };
const actions: ActionWorkspace = {
  items: [],
  counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
  savedViews: [],
  nextCursor: null,
  freshness,
};
const notifications: NotificationList = { items: [], unreadCount: 2, nextCursor: null, freshness };

describe("server capabilities", () => {
  it("uses legacy role home and makes no conditional requests when every flag is disabled", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My work" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /unread notifications/ })).not.toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(([input]) => new URL(String(input), "http://localhost").pathname);
    expect(paths).toContain("/api/v1/me/capabilities");
    expect(paths).not.toContain("/api/v1/me/actions");
    expect(paths).not.toContain("/api/v1/me/notifications/count");
    expect(paths).not.toContain("/api/v1/statistics/scopes");
    expect(paths.some((path) => path.includes("planning-cockpit") || path.includes("product-packages") || path.includes("configuration"))).toBe(false);
  });

  it("redirects disabled conditional routes without querying them", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/notifications");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(([input]) => new URL(String(input), "http://localhost").pathname);
    expect(paths).not.toContain("/api/v1/me/notifications");
    expect(paths).not.toContain("/api/v1/me/notifications/preferences");
  });

  it("fails closed to the legacy role home when capabilities are unavailable", async () => {
    const fetchMock = mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json({ detail: "Unavailable" }, 503);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My work" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /unread notifications/ })).not.toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(([input]) => new URL(String(input), "http://localhost").pathname);
    expect(paths).not.toContain("/api/v1/me/actions");
    expect(paths).not.toContain("/api/v1/me/notifications/count");
    expect(paths).not.toContain("/api/v1/statistics/scopes");
  });

  it("preserves My work and notification journeys when enabled", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabled);
      if (url.pathname.endsWith("/me/actions")) return json(actions);
      if (url.pathname.endsWith("/me/notifications/count")) return json({ unreadCount: 2, projectedAt: null });
      if (url.pathname.endsWith("/me/notifications/preferences")) return json({ groups: [] });
      if (url.pathname.endsWith("/me/notifications")) return json(notifications);
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, true, false, false, false);
    const user = userEvent.setup();
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "My work" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My work" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "2 unread notifications" }));
    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getAllByLabelText("2 unread notifications")).toHaveLength(2);
  });
});
