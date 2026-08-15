import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../lib/api/types";
import { protectedQueryKeys } from "../lib/api/queryKeys";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { json, renderApp } from "../test/render";
import {
  ContextBoundaryProbe,
  dualStaffSession,
  LateMutationProbe,
  mockContextFetch,
  switchedCustomerSession,
} from "./contextSwitchTestSupport";

describe("Customer and staff context switching", () => {
  it("rejects a context that the account is not authorised to use", async () => {
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        return json({ ...dualStaffSession, availableContexts: ["STAFF"] });
      }
      return json({ items: [] });
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <ContextBoundaryProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );
    const button = await screen.findByRole("button", { name: "Try unavailable context" });
    await waitFor(() => expect(button).toBeEnabled());

    await user.click(button);

    expect(await screen.findByText("That account context is not available.")).toBeInTheDocument();
  });

  it("clears protected state, uses the rotated session and opens My requests", async () => {
    let resolveSwitch!: (response: Response) => void;
    const switchResponse = new Promise<Response>((resolve) => {
      resolveSwitch = resolve;
    });
    let switchRequest: { body: unknown; csrf: string | null } | undefined;
    mockContextFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(dualStaffSession);
      if (url.pathname.endsWith("/auth/switch-context")) {
        switchRequest = {
          body: JSON.parse(String(init.body)),
          csrf: new Headers(init.headers).get("X-CSRF-Token"),
        };
        return switchResponse;
      }
      return json({ items: [] });
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const user = userEvent.setup();
    const view = renderApp("/tracking", client);
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    const syntheticStaffKey = [
      ...protectedQueryKeys(dualStaffSession).root(),
      "synthetic-private-state",
    ] as const;
    client.setQueryData(syntheticStaffKey, "staff only");

    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    const menu = screen.getByRole("dialog", { name: "Account details" });
    expect(menu).toHaveTextContent("StaffActive context");
    expect(menu).toHaveTextContent("CustomerOpen My requests");
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Switch to Customer context" }));

    expect(await screen.findByRole("heading", { name: "Switching workspace" })).toBeInTheDocument();
    expect(client.getQueryData(syntheticStaffKey)).toBeUndefined();
    expect(switchRequest).toEqual({
      body: { context: "CUSTOMER" },
      csrf: dualStaffSession.csrfToken,
    });
    await act(async () => {
      resolveSwitch(json(switchedCustomerSession));
    });

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.getByText("Customer context")).toBeInTheDocument();
    expect(screen.queryByText("staff only")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("mist:auth-state")).toMatch(/^context-changed:CUSTOMER:5:/);
  });

  it("detaches an old query client before a context switch completes", async () => {
    let resolveOperation!: (value: string) => void;
    const operation = new Promise<string>((resolve) => {
      resolveOperation = resolve;
    });
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(dualStaffSession);
      if (url.pathname.endsWith("/auth/switch-context")) return json(switchedCustomerSession);
      return json({ items: [] });
    });
    const initialClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    const clients: QueryClient[] = [];
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={initialClient}>
        <AuthProvider>
          <LateMutationProbe clients={clients} operation={operation} />
        </AuthProvider>
      </QueryClientProvider>,
    );
    await screen.findByText("STAFF");
    await user.click(screen.getByRole("button", { name: "Start staff request" }));
    await user.click(screen.getByRole("button", { name: "Switch context" }));

    expect(await screen.findByText("CUSTOMER")).toBeInTheDocument();
    await waitFor(() => expect(clients).toHaveLength(2));
    expect(clients[1]).not.toBe(clients[0]);
    await act(async () => {
      resolveOperation("late staff result");
    });

    const staffKey = protectedQueryKeys(dualStaffSession).requests();
    const customerKey = protectedQueryKeys(switchedCustomerSession).requests();
    const activeClient = clients.at(-1)!;
    expect(initialClient.getQueryData(staffKey)).toBe("late staff result");
    expect(activeClient).not.toBe(initialClient);
    expect(activeClient.getQueryData(staffKey)).toBeUndefined();
    expect(activeClient.getQueryData(customerKey)).toBeUndefined();
  });

  it("does not resurrect a switched session after another tab signs out", async () => {
    let resolveSwitch!: (response: Response) => void;
    const switchResponse = new Promise<Response>((resolve) => {
      resolveSwitch = resolve;
    });
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(dualStaffSession);
      if (url.pathname.endsWith("/auth/switch-context")) return switchResponse;
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Switch to Customer context" }));

    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-out:123",
        }),
      ),
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await act(async () => {
      resolveSwitch(json(switchedCustomerSession));
    });

    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Customer context")).not.toBeInTheDocument();
  });

  it("refreshes the authoritative session and reports a failed switch", async () => {
    let sessionCalls = 0;
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionCalls += 1;
        return json(dualStaffSession);
      }
      if (url.pathname.endsWith("/auth/switch-context"))
        return json({ detail: "Unavailable" }, 503);
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Switch to Customer context" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("workspace could not be switched");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    expect(sessionCalls).toBe(2);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("adopts a server-side context change when the switch response is lost", async () => {
    let sessionCalls = 0;
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionCalls += 1;
        return json(sessionCalls === 1 ? dualStaffSession : switchedCustomerSession);
      }
      if (url.pathname.endsWith("/auth/switch-context")) {
        return json({ detail: "Connection interrupted" }, 503);
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Switch to Customer context" }));

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("workspace could not be switched");
    expect(window.localStorage.getItem("mist:auth-state")).toMatch(/^context-changed:CUSTOMER:5:/);
  });

  it("fails closed when a failed switch cannot reconcile the session", async () => {
    let sessionCalls = 0;
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionCalls += 1;
        return sessionCalls === 1
          ? json(dualStaffSession)
          : json({ detail: "Session unavailable" }, 503);
      }
      if (url.pathname.endsWith("/auth/switch-context")) {
        return json({ detail: "Connection interrupted" }, 503);
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Switch to Customer context" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("reconciles a context switch made in another browser tab", async () => {
    let authoritativeSession = dualStaffSession;
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(authoritativeSession);
      return json({ items: [] });
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderApp("/tracking", client);
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    client.setQueryData(["protected", "old-context"], "staff data");
    authoritativeSession = switchedCustomerSession;
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "context-changed:CUSTOMER:5:123",
        }),
      ),
    );

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    await waitFor(() => expect(client.getQueryData(["protected", "old-context"])).toBeUndefined());
  });

  it("fails closed when another tab changes context but the new session is unavailable", async () => {
    let sessionCalls = 0;
    mockContextFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionCalls += 1;
        return sessionCalls === 1
          ? json(dualStaffSession)
          : json({ detail: "Session expired" }, 401);
      }
      return json({ items: [] });
    });
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();

    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "context-changed:CUSTOMER:5:123",
        }),
      ),
    );

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("returns a dual-context Customer to the staff Home", async () => {
    const returnedStaff: Session = {
      ...dualStaffSession,
      contextVersion: 6,
      csrfToken: "rotated-staff-csrf",
    };
    let requestedContext: unknown;
    mockContextFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(switchedCustomerSession);
      if (url.pathname.endsWith("/auth/switch-context")) {
        requestedContext = JSON.parse(String(init.body));
        return json(returnedStaff);
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open account menu/ }));
    await user.click(screen.getByRole("button", { name: "Switch to Staff context" }));

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page"),
    );
    expect(screen.getByText("Staff context")).toBeInTheDocument();
    expect(requestedContext).toEqual({ context: "STAFF" });
  });
});
