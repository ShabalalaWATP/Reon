/* eslint-disable react-refresh/only-export-components -- test-only render utilities intentionally share fixtures. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { AppRoutes } from "../app/AppRoutes";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { ThemeProvider } from "../lib/theme/ThemeProvider";

export type FetchHandler = (url: URL, init: RequestInit) => Response | Promise<Response>;

export function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function mockFetch(
  handler: FetchHandler,
  useEmptyDraftRegister = true,
  useEmptyStatisticsScopes = true,
  useEmptyTeamWorkspaces = true,
  useEmptyActionWorkspace = true,
  useEmptyNotificationWorkspace = true,
  useDisabledCapabilities = true,
  useEmptyAccountRequests = true,
) {
  const mock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const value = typeof input === "string" ? input : input.toString();
    const url = new URL(value, "http://localhost");
    if (useDisabledCapabilities && url.pathname.endsWith("/me/capabilities")) {
      return Promise.resolve(json({ myWork: false, notifications: false, configuration: false, products: false, planning: false, statistics: false }));
    }
    if (
      useEmptyDraftRegister
      && url.pathname.endsWith("/request-drafts")
      && (!init.method || init.method === "GET")
    ) return Promise.resolve(json({ items: [] }));
    if (useEmptyAccountRequests && url.pathname.endsWith("/admin/account-requests") && (!init.method || init.method === "GET")) {
      return Promise.resolve(json({ items: [] }));
    }
    if (
      useEmptyTeamWorkspaces
      && url.pathname.endsWith("/team-workspaces")
      && (!init.method || init.method === "GET")
    ) return Promise.resolve(json({ items: [] }));
    if (
      useEmptyStatisticsScopes
      && url.pathname.endsWith("/statistics/scopes")
      && (!init.method || init.method === "GET")
    ) return Promise.resolve(json({ items: [] }));
    if (
      useEmptyActionWorkspace
      && url.pathname.endsWith("/me/actions")
      && (!init.method || init.method === "GET")
    ) return Promise.resolve(json({
      items: [],
      counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
      savedViews: [],
      nextCursor: null,
      freshness: { status: "CURRENT", projectedAt: null, sourceChangedAt: null, lagSeconds: null, pendingCount: 0 },
    }));
    if (useEmptyNotificationWorkspace && url.pathname.endsWith("/me/notifications/count")) {
      return Promise.resolve(json({ unreadCount: 0, projectedAt: null }));
    }
    if (useEmptyNotificationWorkspace && url.pathname.endsWith("/me/notifications/preferences")) {
      return Promise.resolve(json({ groups: [] }));
    }
    if (
      useEmptyNotificationWorkspace
      && url.pathname.endsWith("/me/notifications")
      && (!init.method || init.method === "GET")
    ) return Promise.resolve(json({
      items: [], unreadCount: 0, nextCursor: null,
      freshness: { status: "CURRENT", projectedAt: null, sourceChangedAt: null, lagSeconds: null, pendingCount: 0 },
    }));
    return Promise.resolve(handler(url, init));
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function mockFeatureFetch(
  handler: FetchHandler,
  useEmptyDraftRegister = true,
  useEmptyStatisticsScopes = true,
  useEmptyTeamWorkspaces = true,
  useEmptyActionWorkspace = true,
  useEmptyNotificationWorkspace = true,
) {
  return mockFetch(
    handler,
    useEmptyDraftRegister,
    useEmptyStatisticsScopes,
    useEmptyTeamWorkspaces,
    useEmptyActionWorkspace,
    useEmptyNotificationWorkspace,
    false,
  );
}

export function TestProviders({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <ThemeProvider><QueryClientProvider client={client}>{children}</QueryClientProvider></ThemeProvider>;
}

export function renderApp(
  path: string,
  client = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  }),
) {
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <AuthProvider><MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter></AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}
