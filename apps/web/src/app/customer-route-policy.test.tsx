import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { requesterSession } from "../test/fixtures";
import { json, mockFetch, renderApp } from "../test/render";

describe("Customer route policy", () => {
  it.each([
    "/calendar/month",
    "/organisation",
    "/teams/team-ssg/overview",
    "/teams/team-ssg/people/member-1",
  ])("keeps Customer navigation focused when opening %s directly", async (path) => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Customer must not load staff destination ${url.pathname}`);
    });
    renderApp(path);

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Personal calendar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Organisation directory" })).not.toBeInTheDocument();
  });
});
