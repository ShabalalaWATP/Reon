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

    render(
      <RouteErrorBoundary onReload={reload}>
        <BrokenView />
      </RouteErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "This page could not be displayed" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    expect(reload).toHaveBeenCalledOnce();
  });

  it("clears the failure only once the reset key changes", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(
      <RouteErrorBoundary onReload={vi.fn()} resetKey="/profile">
        <BrokenView />
      </RouteErrorBoundary>,
    );
    const failureHeading = { name: "This page could not be displayed" };
    expect(screen.getByRole("heading", failureHeading)).toBeVisible();

    view.rerender(
      <RouteErrorBoundary onReload={vi.fn()} resetKey="/profile">
        <p>Profile ready</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByRole("heading", failureHeading)).toBeVisible();

    view.rerender(
      <RouteErrorBoundary onReload={vi.fn()} resetKey="/requests">
        <p>Requests ready</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByText("Requests ready")).toBeVisible();
  });

  it("keeps a shell failure in place when no reset key is supplied", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(
      <RouteErrorBoundary onReload={vi.fn()}>
        <BrokenView />
      </RouteErrorBoundary>,
    );
    view.rerender(
      <RouteErrorBoundary onReload={vi.fn()}>
        <p>Profile ready</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByRole("heading", { name: "This page could not be displayed" })).toBeVisible();
  });

  it("uses the caller's recovery copy when one is supplied", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <RouteErrorBoundary
        actionLabel="Try this page again"
        description="The rest of the workspace is still available."
        onReload={vi.fn()}
      >
        <BrokenView />
      </RouteErrorBoundary>,
    );
    expect(screen.getByText("The rest of the workspace is still available.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Try this page again" })).toBeVisible();
  });

  it("renders healthy routes normally", () => {
    render(
      <RouteErrorBoundary onReload={vi.fn()}>
        <p>Profile ready</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByText("Profile ready")).toBeVisible();
  });
});
