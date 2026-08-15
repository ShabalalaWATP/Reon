import { QueryClient } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { SESSION_EXPIRED_EVENT } from "../lib/api/client";
import { protectedQueryKeys } from "../lib/api/queryKeys";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { json, mockFetch, renderApp, TestProviders } from "../test/render";
import { requesterSession, staffSession } from "../test/fixtures";
import { AnonymousElevateProbe } from "./authFlowTestProbes";

describe("authentication and route policy", () => {
  it("renders an accessible login, validates input and signs in", async () => {
    let rejectLogin = true;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
      if (url.pathname.endsWith("/auth/login") && init.method === "POST") {
        return rejectLogin
          ? json(
              {
                detail: {
                  code: "AUTHENTICATION_FAILED",
                  message: "Unable to sign in with those credentials.",
                },
              },
              401,
            )
          : json(requesterSession);
      }
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/login");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));
    expect(await screen.findByText("Enter your account ID.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Account ID/), "admin2");
    await user.type(screen.getByLabelText(/Password/), "wrong");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText(/Password/)).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "Hide password" }));
    await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign in");
    expect(screen.getByLabelText(/Password/)).toHaveValue("");
    expect(screen.getByLabelText(/Password/)).toHaveAttribute("type", "password");
    rejectLogin = false;
    await user.type(screen.getByLabelText(/Password/), "synthetic-password");
    await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
  });

  it.each([
    ["staff", staffSession, "/tracking", "Home"],
    ["Customer", requesterSession, "/requests/new", "My requests"],
  ])(
    "sends %s to their fixed landing page after protected-page sign-in",
    async (_label, session, path, destination) => {
      mockFetch((url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
        if (url.pathname.endsWith("/auth/login") && init.method === "POST") return json(session);
        if (url.pathname.endsWith("/requests")) return json({ items: [] });
        throw new Error(`Unexpected ${url.pathname}`);
      });
      const user = userEvent.setup();
      renderApp(path);
      await user.type(await screen.findByLabelText(/Account ID/), session.user.username);
      await user.type(screen.getByLabelText(/Password/), "synthetic-password");
      await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));
      expect(await screen.findByRole("link", { name: destination })).toHaveAttribute(
        "aria-current",
        "page",
      );
    },
  );

  it("redirects anonymous protected access and toggles the login theme", async () => {
    window.localStorage.setItem("mist-service-theme", "light");
    mockFetch(() => json({ detail: "Signed out" }, 401));
    const user = userEvent.setup();
    renderApp("/requests");
    const themeButton = await screen.findByRole("button", { name: "Use dark theme" });
    await user.click(themeButton);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "Use light theme" })).toBeInTheDocument();
  });

  it("submits a complete account request from the login panel", async () => {
    let submitted: Record<string, string> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
      if (url.pathname.endsWith("/auth/account-requests") && init.method === "POST") {
        submitted = JSON.parse(String(init.body));
        return json({ status: "pending" }, 202);
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/login");
    await user.type(await screen.findByLabelText(/Password/), "must-clear");
    await user.click(await screen.findByRole("button", { name: "Request account" }));
    const submit = screen.getByRole("button", { name: "Submit account request" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/^Name/), "Synthetic Customer");
    await user.type(screen.getByLabelText(/Work email/), "customer@example.test");
    await user.type(
      screen.getByLabelText(/Reason for access/),
      "I need access for a fictional request.",
    );
    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(await screen.findByRole("status")).toHaveTextContent("Request submitted");
    expect(submitted).toEqual({
      contactEmail: "customer@example.test",
      displayName: "Synthetic Customer",
      reason: "I need access for a fictional request.",
    });
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByLabelText(/Password/)).toHaveValue("");
  });

  it("clears the protected shell even when remote logout fails", async () => {
    let failLogout = true;
    const sessionWithWorkspace = {
      ...requesterSession,
      user: { ...requesterSession.user, organisationUnitIds: ["synthetic-unit"] },
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(sessionWithWorkspace);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      if (url.pathname.endsWith("/auth/logout"))
        return failLogout
          ? json({ detail: "Try later" }, 500)
          : new Response(null, { status: 204 });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/requests");
    await user.click(await screen.findByRole("button", { name: "Use light theme" }));
    expect(screen.getByRole("button", { name: "Use dark theme" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My requests" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    expect(screen.getByRole("dialog", { name: "Account details" })).toHaveFocus();
    expect(screen.getByRole("dialog", { name: "Account details" })).toHaveTextContent(
      requesterSession.user.username,
    );
    expect(screen.getByRole("dialog", { name: "Account details" })).toHaveTextContent("Customer");
    expect(screen.getByRole("dialog", { name: "Account details" })).toHaveTextContent(
      "Workspace position",
    );
    expect(screen.getByRole("dialog", { name: "Account details" })).toHaveTextContent(
      "Own requests and released products",
    );
    expect(screen.getByRole("link", { name: "View profile" })).toHaveAttribute("href", "/profile");
    await user.click(screen.getByRole("dialog", { name: "Account details" }));
    await user.keyboard("a");
    expect(screen.getByRole("dialog", { name: "Account details" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Account details" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open account menu/ })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(document.body);
    expect(screen.queryByRole("dialog", { name: "Account details" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My requests" })).not.toBeInTheDocument();
    failLogout = false;
  });

  it("provides a keyboard bypass for repeated authenticated navigation", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const view = renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    const target = view.container.querySelector("#main-content");
    expect(target).toHaveAttribute("tabindex", "-1");
    expect(await axe(view.container)).toHaveNoViolations();
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
        return identity === "first" ? json({ items: [firstRequest] }) : secondRequests;
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
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(identity).toBe("anonymous");
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(queryClient.getMutationCache().getAll()).toHaveLength(0);
    const staleKey = protectedQueryKeys(requesterSession).requests();
    queryClient.setQueryData(staleKey, { items: [firstRequest] });

    await user.type(screen.getByLabelText(/Account ID/), secondSession.user.username);
    await user.type(screen.getByLabelText(/Password/), "admin");
    await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));

    expect(
      await screen.findByRole("heading", { name: "Loading your requests" }),
    ).toBeInTheDocument();
    // The previous client is detached; late data there cannot back the new identity tree.
    expect(queryClient.getQueryData(staleKey)).toEqual({ items: [firstRequest] });
    expect(screen.queryByText("User A private request")).not.toBeInTheDocument();
    resolveSecondRequests(json({ items: [secondRequest] }));
    expect(await screen.findByText("User B private request")).toBeInTheDocument();
    expect(screen.queryByText("User A private request")).not.toBeInTheDocument();
  });

  it("returns to sign in when a protected request reports expiry", async () => {
    mockFetch((url) =>
      url.pathname.endsWith("/auth/me")
        ? json(requesterSession)
        : json({ detail: { code: "AUTHENTICATION_FAILED", message: "Session expired." } }, 401),
    );
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("refuses step-up when no authenticated session exists", async () => {
    mockFetch(() => json({ detail: "Signed out" }, 401));
    const user = userEvent.setup();
    render(
      <TestProviders>
        <AuthProvider>
          <AnonymousElevateProbe />
        </AuthProvider>
      </TestProviders>,
    );
    await user.click(await screen.findByRole("button", { name: "Attempt step-up" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in is required.");
  });

  it("reports an unexpected session bootstrap failure before showing sign in", async () => {
    const report = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch(() => {
      throw new Error("Synthetic session dependency failure");
    });
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(report).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Synthetic session dependency failure" }),
    );
  });

  it("keeps an expired session anonymous when a captured step-up timer fires", async () => {
    const elevated = {
      ...requesterSession,
      elevatedUntil: new Date(Date.now() + 5_000).toISOString(),
    };
    const nativeSetTimeout = window.setTimeout.bind(window);
    let expire: (() => void) | undefined;
    vi.spyOn(window, "setTimeout").mockImplementation(
      (handler, timeout, ...arguments_): ReturnType<typeof setTimeout> => {
        if (typeof handler === "function" && Number(timeout) >= 4_000 && Number(timeout) <= 6_000)
          expire = () => handler();
        return nativeSetTimeout(handler, timeout, ...arguments_) as unknown as ReturnType<
          typeof setTimeout
        >;
      },
    );
    mockFetch((url) => (url.pathname.endsWith("/auth/me") ? json(elevated) : json({ items: [] })));
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(expire).toBeTypeOf("function");
    act(() => window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    act(() => expire?.());
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
