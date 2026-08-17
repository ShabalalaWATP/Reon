import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../lib/auth/AuthProvider";
import { json, mockFetch, TestProviders } from "../test/render";
import { requesterSession } from "../test/fixtures";

describe("authentication rotation races", () => {
  it("fails closed when a stale successful rotation cannot be reconciled", async () => {
    let sessionReads = 0;
    let resolveElevation: ((response: Response) => void) | undefined;
    const pendingElevation = new Promise<Response>((resolve) => {
      resolveElevation = resolve;
    });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/elevate")) return pendingElevation;
      if (url.pathname.endsWith("/auth/me")) {
        sessionReads += 1;
        if (sessionReads === 1) return json(requesterSession);
        if (sessionReads === 2) {
          return json({
            ...requesterSession,
            contextVersion: requesterSession.contextVersion + 1,
            csrfToken: "context-change-csrf",
          });
        }
        return json({ detail: "Unavailable" }, 503);
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderSessionProbe();
    expect(await screen.findByText(requesterSession.csrfToken)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Elevate" }));
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "context-changed:STAFF:2:123",
        }),
      ),
    );
    expect(await screen.findByText("context-change-csrf")).toBeInTheDocument();
    act(() =>
      resolveElevation?.(
        json({ csrfToken: "stale-elevation-csrf", elevatedUntil: "2099-01-01T00:05:00Z" }),
      ),
    );

    expect(await screen.findByText("Anonymous")).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
  });

  it("adopts the authoritative context when elevation completes after a context change", async () => {
    let sessionReads = 0;
    let resolveElevation: ((response: Response) => void) | undefined;
    const pendingElevation = new Promise<Response>((resolve) => {
      resolveElevation = resolve;
    });
    const changedContext = {
      ...requesterSession,
      contextVersion: requesterSession.contextVersion + 1,
      csrfToken: "changed-context-csrf",
    };
    const reconciledContext = { ...changedContext, csrfToken: "authoritative-csrf" };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/elevate")) return pendingElevation;
      if (url.pathname.endsWith("/auth/me")) {
        sessionReads += 1;
        if (sessionReads === 1) return json(requesterSession);
        if (sessionReads === 2) return json(changedContext);
        return json(reconciledContext);
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderSessionProbe();
    expect(await screen.findByText(requesterSession.csrfToken)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Elevate" }));
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "context-changed:STAFF:2:123",
        }),
      ),
    );
    expect(await screen.findByText(changedContext.csrfToken)).toBeInTheDocument();
    act(() =>
      resolveElevation?.(
        json({ csrfToken: "stale-elevation-csrf", elevatedUntil: "2099-01-01T00:05:00Z" }),
      ),
    );

    expect(await screen.findByText(reconciledContext.csrfToken)).toBeInTheDocument();
    expect(sessionReads).toBe(3);
  });

  it("does not restore a signed-out session when elevation completes late", async () => {
    let resolveElevation: ((response: Response) => void) | undefined;
    const pendingElevation = new Promise<Response>((resolve) => {
      resolveElevation = resolve;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/auth/elevate")) return pendingElevation;
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderSessionProbe();
    expect(await screen.findByText(requesterSession.csrfToken)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Elevate" }));
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-out:while-elevating",
        }),
      ),
    );
    expect(await screen.findByText("Anonymous")).toBeInTheDocument();
    act(() =>
      resolveElevation?.(
        json({ csrfToken: "late-elevation-csrf", elevatedUntil: "2099-01-01T00:05:00Z" }),
      ),
    );

    await waitFor(() => expect(screen.getByText("Anonymous")).toBeInTheDocument());
    expect(screen.queryByText("late-elevation-csrf")).not.toBeInTheDocument();
  });

  it("rejects a sign-in response that completes after cross-tab sign-out", async () => {
    let resolveLogin: ((response: Response) => void) | undefined;
    const pendingLogin = new Promise<Response>((resolve) => {
      resolveLogin = resolve;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Unauthorised" }, 401);
      if (url.pathname.endsWith("/auth/login")) return pendingLogin;
      return json({ items: [] });
    });
    const user = userEvent.setup();
    const onError = vi.fn();
    render(
      <TestProviders>
        <AuthProvider>
          <LoginProbe onError={onError} />
        </AuthProvider>
      </TestProviders>,
    );
    expect(await screen.findByText("Anonymous")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign in probe" }));
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-out:while-signing-in",
        }),
      ),
    );
    act(() => resolveLogin?.(json(requesterSession)));

    await waitFor(() =>
      expect(onError).toHaveBeenCalledWith("The sign-in attempt was interrupted."),
    );
    expect(screen.getByText("Anonymous")).toBeInTheDocument();
  });
});

function LoginProbe({ onError }: { onError: (message: string) => void }) {
  const { login, status } = useAuth();
  return (
    <>
      <span>{status === "anonymous" ? "Anonymous" : status}</span>
      <button
        type="button"
        onClick={() => {
          void login({ username: "synthetic", password: "password" }).catch((reason: unknown) =>
            onError(reason instanceof Error ? reason.message : "Failed"),
          );
        }}
      >
        Sign in probe
      </button>
    </>
  );
}

function SessionProbe() {
  const { elevate, session, status } = useAuth();
  return (
    <>
      <span>{session?.csrfToken ?? (status === "anonymous" ? "Anonymous" : "Loading")}</span>
      <button type="button" onClick={() => void elevate("admin")}>
        Elevate
      </button>
    </>
  );
}

function renderSessionProbe(
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}
