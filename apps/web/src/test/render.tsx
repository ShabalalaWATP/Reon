/* eslint-disable react-refresh/only-export-components -- test-only render utilities intentionally share fixtures. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { AppRoutes } from "../app/AppRoutes";
import { ClassificationBanner } from "../components/ClassificationBanner";
import { MistReveal } from "../components/MistReveal";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { ThemeProvider } from "../lib/theme/ThemeProvider";

export type FetchHandler = (url: URL, init: RequestInit) => Response | Promise<Response>;
type MockFetchOptions = {
  disabledCapabilities?: boolean;
  emptyAccountRequests?: boolean;
  emptyActionWorkspace?: boolean;
  emptyDraftRegister?: boolean;
  emptyNotificationWorkspace?: boolean;
  emptyStatisticsScopes?: boolean;
  emptyTeamWorkspaces?: boolean;
};

type MockFeatureFetchOptions = Omit<
  MockFetchOptions,
  "disabledCapabilities" | "emptyAccountRequests"
>;

export function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function mockFetch(
  handler: FetchHandler,
  {
    disabledCapabilities = true,
    emptyAccountRequests = true,
    emptyActionWorkspace = true,
    emptyDraftRegister = true,
    emptyNotificationWorkspace = true,
    emptyStatisticsScopes = true,
    emptyTeamWorkspaces = true,
  }: MockFetchOptions = {},
) {
  const mock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const value = typeof input === "string" ? input : input.toString();
    const url = new URL(value, "http://localhost");
    if (
      url.pathname.endsWith("/platform/classification") &&
      (!init.method || init.method === "GET")
    ) {
      return Promise.resolve(
        json({ classification: "OFFICIAL", version: 1, updatedAt: "2026-08-10T00:00:00Z" }),
      );
    }
    if (disabledCapabilities && url.pathname.endsWith("/me/capabilities")) {
      return Promise.resolve(
        json({
          myWork: false,
          notifications: false,
          configuration: false,
          products: false,
          planning: false,
          statistics: false,
        }),
      );
    }
    if (
      emptyDraftRegister &&
      url.pathname.endsWith("/request-drafts") &&
      (!init.method || init.method === "GET")
    )
      return Promise.resolve(json({ items: [] }));
    if (
      emptyAccountRequests &&
      url.pathname.endsWith("/admin/account-requests") &&
      (!init.method || init.method === "GET")
    ) {
      return Promise.resolve(json({ items: [] }));
    }
    if (
      emptyTeamWorkspaces &&
      url.pathname.endsWith("/team-workspaces") &&
      (!init.method || init.method === "GET")
    )
      return Promise.resolve(json({ items: [] }));
    if (
      emptyStatisticsScopes &&
      url.pathname.endsWith("/statistics/scopes") &&
      (!init.method || init.method === "GET")
    )
      return Promise.resolve(json({ items: [] }));
    if (
      emptyActionWorkspace &&
      url.pathname.endsWith("/me/actions") &&
      (!init.method || init.method === "GET")
    )
      return Promise.resolve(
        json({
          items: [],
          counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
          savedViews: [],
          nextCursor: null,
          freshness: {
            status: "CURRENT",
            projectedAt: null,
            sourceChangedAt: null,
            lagSeconds: null,
            pendingCount: 0,
          },
        }),
      );
    if (emptyNotificationWorkspace && url.pathname.endsWith("/me/notifications/count")) {
      return Promise.resolve(json({ unreadCount: 0, projectedAt: null }));
    }
    if (emptyNotificationWorkspace && url.pathname.endsWith("/me/notifications/preferences")) {
      return Promise.resolve(json({ groups: [] }));
    }
    if (
      emptyNotificationWorkspace &&
      url.pathname.endsWith("/me/notifications") &&
      (!init.method || init.method === "GET")
    )
      return Promise.resolve(
        json({
          items: [],
          unreadCount: 0,
          nextCursor: null,
          freshness: {
            status: "CURRENT",
            projectedAt: null,
            sourceChangedAt: null,
            lagSeconds: null,
            pendingCount: 0,
          },
        }),
      );
    return Promise.resolve(handler(url, init));
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function mockFeatureFetch(handler: FetchHandler, options: MockFeatureFetchOptions = {}) {
  return mockFetch(handler, { ...options, disabledCapabilities: false });
}

export function TestProviders({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
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
  // Mirrors App.tsx: the reveal sits outside AuthProvider so the sign-in
  // re-key of that subtree cannot unmount it. Keep the two in step.
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider>
            <div className="classified-app">
              <ClassificationBanner />
              <div className="classified-app__body">
                <AppRoutes />
              </div>
            </div>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
      <MistReveal />
    </ThemeProvider>,
  );
}
