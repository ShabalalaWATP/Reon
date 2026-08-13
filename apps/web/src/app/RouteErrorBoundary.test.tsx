import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RouteErrorBoundary } from "./RouteErrorBoundary";

function BrokenView(): never {
  throw new Error("profile render failed");
}

describe("RouteErrorBoundary", () => {
  afterEach(() => vi.restoreAllMocks());

  it("replaces a failed route with a recoverable workspace message", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const reload = vi.fn();

    render(<RouteErrorBoundary onReload={reload}><BrokenView /></RouteErrorBoundary>);

    expect(screen.getByRole("heading", { name: "This page could not be displayed" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    expect(reload).toHaveBeenCalledOnce();
  });

  it("renders healthy routes normally", () => {
    render(<RouteErrorBoundary><p>Profile ready</p></RouteErrorBoundary>);
    expect(screen.getByText("Profile ready")).toBeVisible();
  });
});
