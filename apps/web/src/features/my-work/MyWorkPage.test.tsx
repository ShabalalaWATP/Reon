import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { ActionWorkspace } from "../../lib/api/actionNotificationTypes";
import { enabledCapabilities, staffSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const workspace: ActionWorkspace = {
  items: [
    {
      id: "action-1",
      section: "NEEDS_MY_ACTION",
      actionAccess: "SHARED",
      actionType: "TRIAGE_REVIEW",
      sourceType: "REQUEST",
      reference: "ISR-101",
      title: "Review service request",
      currentOwner: "CRIOC",
      requiredBy: "2026-08-09",
      ageDays: 1,
      lastChangedAt: "2026-08-07T09:00:00Z",
      deepLink: "/triage?requestId=request-1",
      sourceVersion: 3,
      isStale: false,
    },
    {
      id: "action-2",
      section: "WAITING",
      actionAccess: "PERSONAL",
      actionType: "CUSTOMER_INPUT",
      sourceType: "REQUEST",
      reference: "ISR-102",
      title: null,
      currentOwner: null,
      requiredBy: null,
      ageDays: 0,
      lastChangedAt: "2026-08-06T09:00:00Z",
      deepLink: "https://attacker.test/requests/2",
      sourceVersion: 1,
      isStale: false,
    },
    {
      id: "action-3",
      section: "DUE_SOON",
      actionAccess: "PERSONAL",
      actionType: "QUALITY_REVIEW",
      sourceType: "PRODUCT",
      reference: "ISR-103",
      title: "Check deliverable",
      currentOwner: "QC",
      requiredBy: "2026-08-08",
      ageDays: 3,
      lastChangedAt: "2026-08-07T10:00:00Z",
      deepLink: "/quality-release?requestId=request-3",
      sourceVersion: 2,
      isStale: true,
    },
  ],
  counts: { needsMyAction: 1, waiting: 1, dueSoon: 1, recentlyCompleted: 0 },
  savedViews: [
    {
      id: "view-1",
      name: "My urgent work",
      filters: { sections: ["DUE_SOON"], actionTypes: ["QUALITY_REVIEW"], dueBefore: "2026-08-10" },
      visibleColumns: ["REFERENCE", "TITLE"],
      version: 4,
    },
  ],
  nextCursor: null,
  freshness: {
    status: "CURRENT",
    projectedAt: null,
    sourceChangedAt: null,
    lagSeconds: 15,
    pendingCount: 2,
  },
};

describe("My actions", () => {
  it("presents role work, saved views, safe links and configurable columns accessibly", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(staffSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        calls.push({ path: `${url.pathname}${url.search}`, init });
        if (url.pathname.endsWith("/saved-views") && init.method === "POST")
          return json({ ...workspace.savedViews[0], id: "created" });
        if (url.pathname.includes("/saved-views/") && init.method === "PATCH")
          return json({ ...workspace.savedViews[0], version: 5 });
        if (url.pathname.includes("/saved-views/") && init.method === "DELETE")
          return new Response(null, { status: 204 });
        return json(workspace);
      },
      true,
      true,
      true,
      false,
      true,
      false,
    );
    const user = userEvent.setup();
    const view = renderApp("/my-work");

    expect(await screen.findByRole("heading", { name: "My actions" })).toBeInTheDocument();
    expect(screen.getAllByText("CRIOC Routing User")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Needs attention 1/ })).toBeInTheDocument();
    expect(screen.getByText("Available to CRIOC")).toBeInTheDocument();
    expect(screen.getAllByText("Assigned to you")).toHaveLength(2);
    expect(screen.getByText("Restricted item")).toBeInTheDocument();
    expect(screen.getByText("Access ended")).toBeInTheDocument();
    expect(screen.getByText(/2 updates are still being applied/)).toBeInTheDocument();
    expect(screen.getByText("Refreshing")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open ISR-101/ })).toHaveAttribute(
      "href",
      "/triage?requestId=request-1",
    );
    const workControls = screen.getByText("Saved views and filters").closest("details");
    expect(workControls).not.toHaveAttribute("open");
    expect(screen.getByLabelText("Saved view")).not.toBeVisible();
    expect(screen.getByLabelText("Action type")).not.toBeVisible();
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByText("Saved views and filters"));
    expect(screen.getByText("Saved views and filters").closest("details")).toHaveAttribute("open");
    await user.selectOptions(screen.getByLabelText("Saved view"), "view-1");
    expect(screen.getByRole("heading", { name: "Due soon" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Current owner" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Update view" }));
    await waitFor(() => expect(calls.some(({ init }) => init.method === "PATCH")).toBe(true));
    await user.click(screen.getByRole("button", { name: "Delete view" }));
    await waitFor(() => expect(calls.some(({ init }) => init.method === "DELETE")).toBe(true));

    await user.type(screen.getByLabelText("Save current view"), "Fresh view");
    await user.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() => expect(calls.some(({ init }) => init.method === "POST")).toBe(true));
    await user.selectOptions(screen.getByLabelText("Action type"), "QUALITY_REVIEW");
    await user.selectOptions(screen.getByLabelText("Action type"), "");
    await user.selectOptions(screen.getByLabelText("Action type"), "QUALITY_REVIEW");
    await user.clear(screen.getByLabelText("Due before"));
    await user.type(screen.getByLabelText("Due before"), "2026-08-12");
    await waitFor(() =>
      expect(
        calls.some(
          ({ path }) =>
            path.includes("actionTypes=QUALITY_REVIEW") && path.includes("dueBefore=2026-08-12"),
        ),
      ).toBe(true),
    );
  });

  it("loads another page and supports section and column controls", async () => {
    let first = true;
    let releaseNextPage!: () => void;
    const nextPageReady = new Promise<void>((resolve) => {
      releaseNextPage = resolve;
    });
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(staffSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/me/actions")) {
          if (url.searchParams.has("cursor"))
            return nextPageReady.then(() =>
              json({
                ...workspace,
                items: [{ ...workspace.items[0], id: "action-4", reference: "ISR-104" }],
                nextCursor: null,
              }),
            );
          const response = {
            ...workspace,
            items: [workspace.items[0]],
            nextCursor: first ? "page-2" : null,
            freshness: { ...workspace.freshness, status: "STALE" as const, pendingCount: 0 },
          };
          first = false;
          return json(response);
        }
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      false,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/my-work");
    await user.click(await screen.findByRole("button", { name: "Load more" }));
    expect(screen.getByRole("button", { name: "Loading…" })).toBeDisabled();
    releaseNextPage();
    expect(await screen.findByRole("link", { name: "Open ISR-104" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Waiting 1/ }));
    await user.click(screen.getByRole("button", { name: /Waiting 1/ }));
    await user.click(screen.getByText("Saved views and filters"));
    const picker = screen.getByRole("group", { name: "Visible columns" });
    await user.click(within(picker).getByLabelText("Current owner"));
    expect(screen.queryByRole("columnheader", { name: "Current owner" })).not.toBeInTheDocument();
    await user.click(within(picker).getByLabelText("Title"));
    await user.click(within(picker).getByLabelText("Required date"));
    await user.click(within(picker).getByLabelText("Age"));
    await user.click(within(picker).getByLabelText("Last changed"));
    expect(within(picker).getByLabelText("Reference")).toBeDisabled();
    await user.click(within(picker).getByLabelText("Current owner"));
    expect(within(picker).getByLabelText("Reference")).not.toBeDisabled();
  });

  it("shows empty, denied, conflict and retryable states", async () => {
    let response = 200;
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(staffSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/saved-views") && init.method === "POST")
          return json({ detail: { message: "Saved view changed" } }, 409);
        if (url.pathname.endsWith("/me/actions")) {
          if (response === 403) return json({ detail: "Denied" }, 403);
          if (response === 409) return json({ detail: "Changed" }, 409);
          if (response === 500) return json({ detail: "Unavailable" }, 500);
          return json({
            ...workspace,
            items: [],
            savedViews: [],
            counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
            freshness: {
              ...workspace.freshness,
              status: "DEGRADED",
              projectedAt: null,
              sourceChangedAt: null,
              pendingCount: 0,
            },
          });
        }
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      true,
      false,
      true,
      false,
    );

    const user = userEvent.setup();
    const empty = renderApp("/my-work");
    expect(
      await screen.findByRole("heading", { name: "No work in this view" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Starting No action update checkpoint");
    await user.click(screen.getByText("Saved views and filters"));
    await user.type(screen.getByLabelText("Save current view"), "Unavailable view");
    await user.click(screen.getByRole("button", { name: "Save view" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Saved view changed");
    empty.unmount();
    response = 403;
    const denied = renderApp("/my-work");
    expect(
      await screen.findByRole("heading", { name: "Your access has changed" }),
    ).toBeInTheDocument();
    denied.unmount();
    response = 409;
    const conflict = renderApp("/my-work");
    expect(
      await screen.findByRole("heading", { name: "This work view changed" }),
    ).toBeInTheDocument();
    conflict.unmount();
    response = 500;
    renderApp("/my-work");
    expect(
      await screen.findByRole("heading", { name: "Your work could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
