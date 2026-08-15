import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { ThemeProvider } from "../lib/theme/ThemeProvider";
import { requesterSession } from "../test/fixtures";
import { json, mockFetch } from "../test/render";

let pageFails = true;

function FlakyView() {
  if (pageFails) throw new Error("Synthetic route render failure");
  return <p>Recovered page</p>;
}

function renderShell(path: string) {
  mockFetch((url) =>
    url.pathname.endsWith("/auth/me") ? json(requesterSession) : json({ items: [] }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider>
            <Routes>
              <Route element={<AppShell />}>
                <Route path="requests" element={<p>My requests page</p>} />
                <Route path="requests/new" element={<FlakyView />} />
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe("workspace shell failure isolation", () => {
  beforeEach(() => {
    pageFails = true;
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("keeps navigation available and retries only the failed page", async () => {
    const user = userEvent.setup();
    renderShell("/requests/new");

    expect(
      await screen.findByRole("heading", { name: "This page could not be displayed" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "My requests" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open account menu/ })).toBeInTheDocument();

    pageFails = false;
    await user.click(screen.getByRole("button", { name: "Try this page again" }));

    expect(screen.getByText("Recovered page")).toBeVisible();
    expect(screen.getByRole("link", { name: "My requests" })).toBeInTheDocument();
  });

  it("clears a page failure when the route changes", async () => {
    const user = userEvent.setup();
    renderShell("/requests/new");

    expect(
      await screen.findByRole("heading", { name: "This page could not be displayed" }),
    ).toBeVisible();

    await user.click(screen.getByRole("link", { name: "My requests" }));

    expect(await screen.findByText("My requests page")).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "This page could not be displayed" }),
    ).not.toBeInTheDocument();
  });
});
