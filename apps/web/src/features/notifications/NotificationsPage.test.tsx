import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type {
  NotificationList,
  NotificationPreferences,
} from "../../lib/api/actionNotificationTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const notifications: NotificationList = {
  items: [
    {
      id: "notice-1",
      eventType: "REQUEST_ASSIGNED",
      eventGroup: "WORK",
      subject: "Request assigned to SSG",
      occurredAt: "2026-08-07T09:00:00Z",
      deepLink: "/requests/request-1",
      isRead: false,
      isArchived: false,
      isActionCompleted: false,
      readAt: null,
      archivedAt: null,
      actionCompletedAt: null,
      version: 2,
    },
    {
      id: "notice-2",
      eventType: "PRODUCT_RELEASED",
      eventGroup: "RELEASE",
      subject: "Product ready",
      occurredAt: "2026-08-06T09:00:00Z",
      deepLink: "https://attacker.test/product",
      isRead: true,
      isArchived: false,
      isActionCompleted: true,
      readAt: "2026-08-06T10:00:00Z",
      archivedAt: null,
      actionCompletedAt: "2026-08-06T11:00:00Z",
      version: 4,
    },
    {
      id: "notice-3",
      eventType: "REQUEST_CLOSED",
      eventGroup: "WORK",
      subject: "Request archived",
      occurredAt: "2026-08-05T09:00:00Z",
      deepLink: null,
      isRead: true,
      isArchived: true,
      isActionCompleted: false,
      readAt: "2026-08-05T10:00:00Z",
      archivedAt: "2026-08-05T11:00:00Z",
      actionCompletedAt: null,
      version: 1,
    },
    {
      id: "notice-4",
      eventType: "REQUEST_UPDATED",
      eventGroup: "WORK",
      subject: "Request updated",
      occurredAt: "2026-08-04T09:00:00Z",
      deepLink: null,
      isRead: true,
      isArchived: false,
      isActionCompleted: false,
      readAt: "2026-08-04T10:00:00Z",
      archivedAt: null,
      actionCompletedAt: null,
      version: 1,
    },
  ],
  unreadCount: 1,
  nextCursor: null,
  freshness: {
    status: "DEGRADED",
    projectedAt: null,
    sourceChangedAt: null,
    lagSeconds: null,
    pendingCount: 0,
  },
};
const preferences: NotificationPreferences = {
  groups: [
    { eventGroup: "SECURITY", enabled: true, mandatory: true, reminderDays: [1], version: 1 },
    { eventGroup: "WORK", enabled: true, mandatory: false, reminderDays: [1, 3], version: 2 },
  ],
};

describe("Notifications", () => {
  it("shows safe notification summaries, bulk actions and preferences accessibly", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    let failPreference = false;
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        calls.push({ path: `${url.pathname}${url.search}`, init });
        if (url.pathname.endsWith("/me/notifications/preferences") && !init.method)
          return json(preferences);
        if (url.pathname.includes("/me/notifications/preferences/") && init.method === "PATCH")
          return failPreference
            ? json({ detail: { message: "Preference changed" } }, 409)
            : json(preferences.groups[1]);
        if (url.pathname.endsWith("/me/notifications/state")) return json({ items: [] });
        if (url.pathname.endsWith("/me/notifications/count"))
          return json({ unreadCount: 1, projectedAt: null });
        return json(notifications);
      },
      true,
      true,
      true,
      true,
      false,
      false,
    );
    const user = userEvent.setup();
    const view = renderApp("/notifications");

    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getAllByLabelText("1 unread notifications")).toHaveLength(2);
    expect(calls.some(({ path }) => path.endsWith("/me/notifications/count"))).toBe(false);
    expect(screen.getByText(/Live updates are unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Request assigned/ })).toHaveAttribute(
      "href",
      "/requests/request-1",
    );
    expect(screen.getByText("Access ended")).toBeInTheDocument();
    expect(screen.getByText("Action complete")).toBeInTheDocument();
    expect(screen.getAllByText("Archived")).toHaveLength(2);
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByLabelText("Select Request assigned to SSG"));
    await user.click(screen.getByLabelText("Select Request assigned to SSG"));
    await user.click(screen.getByLabelText("Select Request assigned to SSG"));
    await user.click(screen.getByRole("button", { name: "Mark read" }));
    await waitFor(() =>
      expect(calls.some(({ path }) => path === "/api/v1/me/notifications/state")).toBe(true),
    );
    const stateCall = calls.filter(({ path }) => path === "/api/v1/me/notifications/state").at(-1)!;
    expect(JSON.parse(stateCall.init.body as string)).toEqual({
      action: "MARK_READ",
      targets: [{ id: "notice-1", expectedVersion: 2 }],
    });

    await user.click(screen.getByLabelText("Select Product ready"));
    await user.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() =>
      expect(
        JSON.parse(
          calls.filter(({ path }) => path === "/api/v1/me/notifications/state").at(-1)!.init
            .body as string,
        ).action,
      ).toBe("ARCHIVE"),
    );

    const mandatory = screen.getByText("Mandatory safety notification").closest("article")!;
    expect(within(mandatory).getByRole("checkbox", { name: "Enabled" })).toBeDisabled();
    const optional = screen.getByText("May be switched off").closest("article")!;
    await user.click(within(optional).getByRole("checkbox", { name: "Enabled" }));
    await user.click(within(optional).getByRole("checkbox", { name: "2d" }));
    await user.click(within(optional).getByRole("checkbox", { name: "1d" }));
    await user.click(within(optional).getByRole("checkbox", { name: "1d" }));
    await user.click(within(optional).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(calls.some(({ path }) => path.endsWith("/preferences/WORK"))).toBe(true),
    );
    expect(
      JSON.parse(calls.find(({ path }) => path.endsWith("/preferences/WORK"))!.init.body as string),
    ).toMatchObject({ enabled: false, reminderDays: [3, 2, 1], expectedVersion: 2 });
    await waitFor(() =>
      expect(within(optional).getByRole("button", { name: "Save" })).not.toBeDisabled(),
    );
    failPreference = true;
    await user.click(within(optional).getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Preference changed");

    await user.selectOptions(screen.getByLabelText("State"), "UNREAD");
    await user.selectOptions(screen.getByLabelText("Event type"), "REQUEST_ASSIGNED");
    await user.type(screen.getByLabelText("From"), "2026-08-01");
    await user.type(screen.getByLabelText("To"), "2026-08-07");
    await waitFor(() =>
      expect(
        calls.some(
          ({ path }) =>
            path.includes("states=UNREAD") &&
            path.includes("from=2026-08-01T00%3A00%3A00.000Z") &&
            path.includes("to=2026-08-07T23%3A59%3A59.999Z"),
        ),
      ).toBe(true),
    );
    await user.selectOptions(screen.getByLabelText("State"), "");
    await user.selectOptions(screen.getByLabelText("Event type"), "");
    await user.clear(screen.getByLabelText("From"));
    await user.clear(screen.getByLabelText("To"));
  });

  it("loads another page", async () => {
    let releaseNextPage!: () => void;
    const nextPageReady = new Promise<void>((resolve) => {
      releaseNextPage = resolve;
    });
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/me/notifications/preferences")) return json(preferences);
        if (url.pathname.endsWith("/me/notifications/count"))
          return json({ unreadCount: 1, projectedAt: null });
        if (url.pathname.endsWith("/me/notifications"))
          return url.searchParams.has("cursor")
            ? nextPageReady.then(() =>
                json({
                  ...notifications,
                  items: [
                    { ...notifications.items[0], id: "notice-later", subject: "Later update" },
                  ],
                  nextCursor: null,
                }),
              )
            : json({
                ...notifications,
                items: [notifications.items[0]],
                nextCursor: "page-2",
                freshness: { ...notifications.freshness, status: "CURRENT", pendingCount: 1 },
              });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      true,
      false,
      false,
    );
    const user = userEvent.setup();
    renderApp("/notifications");
    await user.click(await screen.findByRole("button", { name: "Load more" }));
    expect(screen.getByRole("button", { name: "Loading…" })).toBeDisabled();
    expect(screen.getByText("Updating")).toBeInTheDocument();
    releaseNextPage();
    expect(await screen.findByRole("link", { name: "Open Later update" })).toBeInTheDocument();
  });

  it("shows empty, denied and retryable states", async () => {
    let response = 200;
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/me/notifications/preferences"))
          return response === 500 ? json({ detail: "Unavailable" }, 500) : json({ groups: [] });
        if (url.pathname.endsWith("/me/notifications/count"))
          return json({ unreadCount: 0, projectedAt: null });
        if (url.pathname.endsWith("/me/notifications")) {
          if (response === 403) return json({ detail: "Denied" }, 403);
          return json({
            ...notifications,
            items: [],
            unreadCount: 0,
            freshness: { ...notifications.freshness, status: "CURRENT" },
          });
        }
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      true,
      false,
      false,
    );
    const empty = renderApp("/notifications");
    expect(
      await screen.findByRole("heading", { name: "No notifications in this view" }),
    ).toBeInTheDocument();
    empty.unmount();
    response = 403;
    const denied = renderApp("/notifications");
    expect(
      await screen.findByRole("heading", { name: "Notification access ended" }),
    ).toBeInTheDocument();
    denied.unmount();
    response = 500;
    renderApp("/notifications");
    expect(
      await screen.findByRole("heading", { name: "Notifications could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
