import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { requesterSession } from "../test/fixtures";
import { json, mockFetch, renderApp } from "../test/render";

describe("authentication session compatibility", () => {
  it("fails closed when a successful endpoint returns a legacy session shape", async () => {
    const report = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const legacy: Record<string, unknown> = { ...requesterSession };
    delete legacy.activeContext;
    delete legacy.availableContexts;
    delete legacy.contextVersion;
    const fetchMock = mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(legacy);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp("/requests");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(report).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "The server returned an incompatible session.",
      }),
    );
    expect(
      fetchMock.mock.calls
        .map(([input]) => String(input))
        .some((path) => path.endsWith("/requests")),
    ).toBe(false);
  });
});
