import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../lib/auth/AuthProvider";
import { json, mockFetch, renderApp, TestProviders } from "../test/render";
import { requesterSession } from "../test/fixtures";

describe("authentication session lifecycle", () => {
  it("adopts rotated step-up credentials and broadcasts no credential material", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/auth/elevate")) {
        return json({
          csrfToken: "post-step-csrf",
          elevatedUntil: "2099-01-01T00:05:00Z",
        });
      }
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderSessionProbe();

    expect(await screen.findByText(requesterSession.csrfToken)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Elevate" }));

    expect(await screen.findByText("post-step-csrf")).toBeInTheDocument();
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(setItem).toHaveBeenCalledWith(
      "mist:auth-state",
      expect.stringMatching(/^session-rotated:\d+$/),
    );
    expect(localStorage.getItem("mist:auth-state")).not.toContain("post-step-csrf");
  });

  it("keeps rotated credentials when an earlier elevation expires in flight", async () => {
    const elevated = {
      ...requesterSession,
      elevatedUntil: new Date(Date.now() + 60_000).toISOString(),
    };
    const nativeSetTimeout = window.setTimeout.bind(window);
    let expire: (() => void) | undefined;
    let resolveElevation: ((response: Response) => void) | undefined;
    const pendingElevation = new Promise<Response>((resolve) => {
      resolveElevation = resolve;
    });
    vi.spyOn(window, "setTimeout").mockImplementation((handler, timeout, ...arguments_) => {
      if (typeof handler === "function" && Number(timeout) >= 50_000 && Number(timeout) <= 60_000)
        expire = () => handler();
      return nativeSetTimeout(handler, timeout, ...arguments_) as unknown as ReturnType<
        typeof setTimeout
      >;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(elevated);
      if (url.pathname.endsWith("/auth/elevate")) return pendingElevation;
      return json({ items: [] });
    });
    const user = userEvent.setup();
    renderSessionProbe();
    expect(await screen.findByText(elevated.csrfToken)).toBeInTheDocument();
    await waitFor(() => expect(expire).toEqual(expect.any(Function)));

    await user.click(screen.getByRole("button", { name: "Elevate" }));
    act(() => expire?.());
    act(() =>
      resolveElevation?.(
        json({ csrfToken: "race-safe-csrf", elevatedUntil: "2099-01-01T00:05:00Z" }),
      ),
    );

    expect(await screen.findByText("race-safe-csrf")).toBeInTheDocument();
  });

  it("reconciles a sibling rotation without clearing same-context query data", async () => {
    let authoritative = requesterSession;
    let sessionReads = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionReads += 1;
        return json(authoritative);
      }
      return json({ items: [] });
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderSessionProbe(client);
    expect(await screen.findByText(requesterSession.csrfToken)).toBeInTheDocument();
    client.setQueryData(["protected", "retained"], "safe cached data");
    authoritative = { ...requesterSession, csrfToken: "sibling-rotated-csrf" };

    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "session-rotated:123",
        }),
      ),
    );

    expect(await screen.findByText("sibling-rotated-csrf")).toBeInTheDocument();
    expect(sessionReads).toBe(2);
    expect(client.getQueryData(["protected", "retained"])).toBe("safe cached data");
  });

  it("does not promote an anonymous tab on a rotation message", async () => {
    let sessionReads = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        sessionReads += 1;
        return sessionReads === 1 ? json({ detail: "Unauthorised" }, 401) : json(requesterSession);
      }
      return json({ items: [] });
    });
    renderSessionProbe();
    expect(await screen.findByText("Anonymous")).toBeInTheDocument();

    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "session-rotated:123",
        }),
      ),
    );

    expect(screen.getByText("Anonymous")).toBeInTheDocument();
    expect(sessionReads).toBe(1);
  });

  it("propagates only valid cross-tab sign-out events", async () => {
    mockFetch((url) =>
      url.pathname.endsWith("/auth/me") ? json(requesterSession) : json({ items: [] }),
    );
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", { key: "mist:auth-state", newValue: "signed-in:123" }),
      ),
    );
    expect(screen.getByRole("heading", { name: "My requests" })).toBeInTheDocument();
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", { key: "mist:auth-state", newValue: "signed-out:124" }),
      ),
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("enforces absolute expiry locally even when logout fails", async () => {
    const expired = { ...requesterSession, expiresAt: "2000-01-01T00:00:00Z" };
    mockFetch((url) =>
      url.pathname.endsWith("/auth/me") ? json(expired) : Promise.reject(new Error("offline")),
    );
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("records only visible, unthrottled activity and clears on a 401", async () => {
    let activityCalls = 0;
    let activityStatus = 500;
    vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    const legacySession = { ...requesterSession };
    delete legacySession.idleExpiresAt;
    delete legacySession.idleTimeoutSeconds;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(legacySession);
      if (url.pathname.endsWith("/auth/activity")) {
        activityCalls += 1;
        return json({ detail: "failed" }, activityStatus);
      }
      return json({ items: [] });
    });
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    act(() => window.dispatchEvent(new KeyboardEvent("keydown")));
    expect(activityCalls).toBe(0);
    visibility.mockReturnValue("visible");
    act(() => window.dispatchEvent(new KeyboardEvent("keydown")));
    await waitFor(() => expect(activityCalls).toBe(1));
    act(() => window.dispatchEvent(new PointerEvent("pointerdown")));
    expect(activityCalls).toBe(1);
    activityStatus = 401;
    vi.mocked(Date.now).mockReturnValue(1_031_000);
    act(() => window.dispatchEvent(new TouchEvent("touchstart")));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("removes elevation when its timer fires", async () => {
    const elevated = {
      ...requesterSession,
      elevatedUntil: new Date(Date.now() + 60_000).toISOString(),
    };
    const nativeSetTimeout = window.setTimeout.bind(window);
    let expire: (() => void) | undefined;
    vi.spyOn(window, "setTimeout").mockImplementation((handler, timeout, ...arguments_) => {
      if (typeof handler === "function" && Number(timeout) >= 50_000 && Number(timeout) <= 60_000)
        expire = () => handler();
      return nativeSetTimeout(handler, timeout, ...arguments_) as unknown as ReturnType<
        typeof setTimeout
      >;
    });
    mockFetch((url) => (url.pathname.endsWith("/auth/me") ? json(elevated) : json({ items: [] })));
    render(
      <TestProviders>
        <AuthProvider>
          <ElevationProbe />
        </AuthProvider>
      </TestProviders>,
    );
    expect(await screen.findByText("Elevated")).toBeInTheDocument();
    await waitFor(() => expect(expire).toEqual(expect.any(Function)));
    act(() => expire?.());
    expect(await screen.findByText("Not elevated")).toBeInTheDocument();
    act(() =>
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-out:after-elevation",
        }),
      ),
    );
    act(() => expire?.());
    expect(await screen.findByText("Not elevated")).toBeInTheDocument();
  });

  it("keeps an already anonymous session private when logout is requested", async () => {
    mockFetch((url) =>
      url.pathname.endsWith("/auth/me")
        ? json({ detail: "Unauthorised" }, 401)
        : Promise.reject(new Error(`Unexpected ${url.pathname}`)),
    );
    render(
      <TestProviders>
        <AuthProvider>
          <AnonymousLogoutProbe />
        </AuthProvider>
      </TestProviders>,
    );
    expect(await screen.findByText("Anonymous")).toBeInTheDocument();
    screen.getByRole("button", { name: "Clear local session" }).click();
    expect(screen.getByText("Anonymous")).toBeInTheDocument();
  });
});

function ElevationProbe() {
  const { session } = useAuth();
  return <span>{session?.elevatedUntil ? "Elevated" : "Not elevated"}</span>;
}

function AnonymousLogoutProbe() {
  const { logout, status } = useAuth();
  return (
    <>
      <span>{status === "anonymous" ? "Anonymous" : "Loading"}</span>
      <button type="button" onClick={() => void logout()}>
        Clear local session
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
