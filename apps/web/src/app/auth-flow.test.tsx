import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { AppShell } from "../components/AppShell";
import { useAuth, AuthProvider } from "../lib/auth/AuthProvider";
import { useTheme } from "../lib/theme/ThemeProvider";
import { json, mockFetch, renderApp, TestProviders } from "../test/render";
import { adminSession, requesterSession, staffSession } from "../test/fixtures";

describe("authentication and route policy", () => {
  it("renders an accessible login, validates input and signs in", async () => {
    let rejectLogin = true;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
      if (url.pathname.endsWith("/auth/login") && init.method === "POST") {
        return rejectLogin
          ? json({ detail: { code: "AUTHENTICATION_FAILED", message: "Unable to sign in with those credentials." } }, 401)
          : json(requesterSession);
      }
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/login");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Sign in to ISTARI" }));
    expect(await screen.findByText("Enter your account ID.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Account ID/), "admin2");
    await user.type(screen.getByLabelText(/Password/), "wrong");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText(/Password/)).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "Hide password" }));
    await user.click(screen.getByRole("button", { name: "Sign in to ISTARI" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign in");
    rejectLogin = false;
    await user.click(screen.getByRole("button", { name: "Sign in to ISTARI" }));
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
  });

  it("redirects anonymous protected access and toggles the login theme", async () => {
    window.localStorage.setItem("istari-service-theme", "light");
    mockFetch(() => json({ detail: "Signed out" }, 401));
    const user = userEvent.setup();
    renderApp("/requests");
    const themeButton = await screen.findByRole("button", { name: "Use dark theme" });
    await user.click(themeButton);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "Use light theme" })).toBeInTheDocument();
  });

  it("isolates platform administration from request content", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return json({ items: [] });
      throw new Error("Request content must not be fetched");
    });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "User accounts" })).toBeInTheDocument();
    expect(screen.queryByText("My requests")).not.toBeInTheDocument();
  });

  it("redirects a role away from another role's route", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "No items waiting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "JIOC routing queue" })).toBeInTheDocument();
  });

  it("signs out from the shell and reports logout failures", async () => {
    let failLogout = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      if (url.pathname.endsWith("/auth/logout")) return failLogout ? json({ detail: "Try later" }, 500) : new Response(null, { status: 204 });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/requests");
    await user.click(await screen.findByRole("button", { name: "Use light theme" }));
    expect(screen.getByRole("button", { name: "Use dark theme" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign out failed");
    failLogout = false;
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("never renders one requester's cached data after another requester signs in", async () => {
    const secondSession = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        id: "99999999-9999-4999-8999-999999999999",
        username: "requester.2@example.test",
        displayName: "Erin Cuthbert",
        scope: "Requesting Area B",
      },
    };
    const firstRequest = {
      id: "first-request",
      reference: "ISR-2026-0101",
      title: "User A private request",
      status: "IN_PROGRESS" as const,
      currentOwner: "Delivery Team A",
      requiredBy: "2026-09-10",
      createdAt: "2026-08-06T09:00:00Z",
      updatedAt: "2026-08-06T10:00:00Z",
      needsRequesterInput: false,
    };
    const secondRequest = {
      ...firstRequest,
      id: "second-request",
      reference: "ISR-2026-0102",
      title: "User B private request",
    };
    let identity: "first" | "anonymous" | "second" = "first";
    let resolveSecondRequests!: (response: Response) => void;
    const secondRequests = new Promise<Response>((resolve) => {
      resolveSecondRequests = resolve;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/auth/logout")) {
        identity = "anonymous";
        return new Response(null, { status: 204 });
      }
      if (url.pathname.endsWith("/auth/login")) {
        identity = "second";
        return json(secondSession);
      }
      if (url.pathname.endsWith("/requests")) {
        return identity === "first"
          ? json({ items: [firstRequest] })
          : secondRequests;
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false, staleTime: Number.POSITIVE_INFINITY },
      },
    });
    const user = userEvent.setup();
    renderApp("/requests", queryClient);
    expect(await screen.findByText("User A private request")).toBeInTheDocument();
    expect(queryClient.getQueryCache().getAll()).not.toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(identity).toBe("anonymous");
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(queryClient.getMutationCache().getAll()).toHaveLength(0);
    const staleKey = [
      "protected",
      requesterSession.user.id,
      "requests",
    ] as const;
    queryClient.setQueryData(staleKey, { items: [firstRequest] });

    await user.type(
      screen.getByLabelText(/Account ID/),
      secondSession.user.username,
    );
    await user.type(screen.getByLabelText(/Password/), "admin");
    await user.click(screen.getByRole("button", { name: "Sign in to ISTARI" }));

    expect(
      await screen.findByRole("heading", { name: "Loading your requests" }),
    ).toBeInTheDocument();
    expect(queryClient.getQueryData(staleKey)).toBeUndefined();
    expect(screen.queryByText("User A private request")).not.toBeInTheDocument();
    resolveSecondRequests(json({ items: [secondRequest] }));
    expect(await screen.findByText("User B private request")).toBeInTheDocument();
    expect(screen.queryByText("User A private request")).not.toBeInTheDocument();
  });

  it("returns to sign in when a protected request reports expiry", async () => {
    mockFetch((url) => url.pathname.endsWith("/auth/me")
      ? json(requesterSession)
      : json({ detail: { code: "AUTHENTICATION_FAILED", message: "Session expired." } }, 401));
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("covers provider guardrails, anonymous shell and the production composition", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<ThemeHookProbe />)).toThrow("useTheme must be used");
    expect(() => render(<AuthHookProbe />)).toThrow("useAuth must be used");
    mockFetch(() => json({ detail: "Signed out" }, 401));
    const { container } = render(<TestProviders><AuthProvider><MemoryRouter><AppShell /></MemoryRouter></AuthProvider></TestProviders>);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    window.history.pushState({}, "", "/login");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});

function ThemeHookProbe() { useTheme(); return null; }
function AuthHookProbe() { useAuth(); return null; }
