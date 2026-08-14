import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

import { AppShell } from "../components/AppShell";
import { AuthProvider } from "../lib/auth/AuthProvider";
import { json, mockFetch, TestProviders } from "../test/render";
import { App } from "./App";
import { AuthHookProbe, ThemeHookProbe } from "./authFlowTestProbes";

it("covers provider guardrails, anonymous shell and the production composition", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  expect(() => render(<ThemeHookProbe />)).toThrow("useTheme must be used");
  expect(() => render(<AuthHookProbe />)).toThrow("useAuth must be used");
  mockFetch(() => json({ detail: "Signed out" }, 401));
  const { container } = render(
    <TestProviders>
      <AuthProvider>
        <MemoryRouter>
          <AppShell />
        </MemoryRouter>
      </AuthProvider>
    </TestProviders>,
  );
  await waitFor(() => expect(container).toBeEmptyDOMElement());
  window.history.pushState({}, "", "/login");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});
