import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ServerCapabilities } from "../lib/api/capabilityClient";
import type { NotificationList } from "../lib/api/actionNotificationTypes";
import { requesterSession, staffSession } from "../test/fixtures";
import { json, mockFeatureFetch, mockFetch, renderApp } from "../test/render";

const enabled: ServerCapabilities = {
  conversationReads: true,
  conversationWrites: true,
  contextSwitching: true,
  myWork: true,
  notifications: true,
  configuration: true,
  products: true,
  managedFileUploads: true,
  planning: true,
  statistics: true,
};
const freshness = {
  status: "CURRENT" as const,
  projectedAt: null,
  sourceChangedAt: null,
  lagSeconds: null,
  pendingCount: 0,
};
const notifications: NotificationList = { items: [], unreadCount: 2, nextCursor: null, freshness };

describe("server capabilities", () => {
  it("hides context switching when the independent capability is absent", async () => {
    const fetchMock = mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/me/capabilities")) {
        return json({ myWork: true, notifications: true });
      }
      if (url.pathname.endsWith("/tracked-requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/tracking");

    await user.click(await screen.findByRole("button", { name: /Open account menu/ }));

    expect(
      screen.queryByRole("button", { name: "Switch to Customer context" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls
        .map(([input]) => String(input))
        .some((path) => path.includes("/auth/switch-context")),
    ).toBe(false);
  });

  it("uses legacy role home and makes no conditional requests when every flag is disabled", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My assigned actions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /unread notifications/ })).not.toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(
      ([input]) => new URL(String(input), "http://localhost").pathname,
    );
    expect(paths).toContain("/api/v1/me/capabilities");
    expect(paths).not.toContain("/api/v1/me/actions");
    expect(paths).not.toContain("/api/v1/me/notifications/count");
    expect(paths).not.toContain("/api/v1/statistics/scopes");
    expect(
      paths.some(
        (path) =>
          path.includes("planning-cockpit") ||
          path.includes("product-packages") ||
          path.includes("configuration"),
      ),
    ).toBe(false);
  });

  it("redirects disabled conditional routes without querying them", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/notifications");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(
      ([input]) => new URL(String(input), "http://localhost").pathname,
    );
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
    expect(screen.queryByRole("link", { name: "My assigned actions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /unread notifications/ })).not.toBeInTheDocument();
    const paths = fetchMock.mock.calls.map(
      ([input]) => new URL(String(input), "http://localhost").pathname,
    );
    expect(paths).not.toContain("/api/v1/me/actions");
    expect(paths).not.toContain("/api/v1/me/notifications/count");
    expect(paths).not.toContain("/api/v1/statistics/scopes");
  });

  it("keeps Customer actions in My requests and preserves notifications", async () => {
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabled);
        if (url.pathname.endsWith("/me/notifications/count"))
          return json({ unreadCount: 2, projectedAt: null });
        if (url.pathname.endsWith("/me/notifications/preferences")) return json({ groups: [] });
        if (url.pathname.endsWith("/me/notifications")) return json(notifications);
        if (url.pathname.endsWith("/request-drafts")) return json({ items: [] });
        if (url.pathname.endsWith("/requests")) return json({ items: [] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      false,
      false,
      false,
    );
    const user = userEvent.setup();
    renderApp("/my-work");

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My assigned actions" })).not.toBeInTheDocument();
    expect(screen.getByText(/New actions also appear in notifications/)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "2 unread notifications" }));
    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getAllByLabelText("2 unread notifications")).toHaveLength(2);
  });

  it("keeps a large unread count compact without hiding the exact accessible count", async () => {
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabled);
        if (url.pathname.endsWith("/me/notifications/count"))
          return json({ unreadCount: 120, projectedAt: null });
        if (url.pathname.endsWith("/request-drafts")) return json({ items: [] });
        if (url.pathname.endsWith("/requests")) return json({ items: [] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      false,
      false,
      false,
    );
    renderApp("/requests");
    const link = await screen.findByRole("link", { name: "120 unread notifications" });
    expect(link).toHaveTextContent("99+");
  });
});
