import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { staffSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("staff work queue", () => {
  it.each([
    ["/coordination", "Incoming requests"],
    ["/allocation", "Ops routing queue"],
    ["/delivery/team", "Team queue"],
    ["/delivery/my-work", "Production queue"],
    ["/quality-release", "QC Team workspace"],
  ])("renders the shared queue at %s for its role", async (path, title) => {
    const roleByPath = {
      "/coordination": "SERVICE_COORDINATION",
      "/allocation": "OPERATIONS_ALLOCATION",
      "/delivery/team": "DELIVERY_TEAM_LEAD",
      "/delivery/my-work": "DELIVERY_SPECIALIST",
      "/quality-release": "QUALITY_RELEASE",
    } as const;
    mockFetch((url) =>
      url.pathname.endsWith("/auth/me")
        ? json({
            ...staffSession,
            user: { ...staffSession.user, role: roleByPath[path as keyof typeof roleByPath] },
          })
        : json({ items: [] }),
    );
    renderApp(path);
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
  });
});
