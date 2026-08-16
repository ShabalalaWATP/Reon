import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { organisationUnit, organisationUnits, staffSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { locateViewer } from "./organisationTree";

describe("viewer placement in the organisation", () => {
  it("lights the path from the root down to the viewer's unit", () => {
    const team = organisationUnit("SSG_TEAM");
    const placement = locateViewer(organisationUnits, [team.id]);
    expect([...placement.own]).toEqual([team.id]);
    expect(placement.trail.map((unit) => unit.code)).toEqual([
      "CRIOC",
      "JOCK",
      "ACSA_B_OPS",
      "SSG_TEAM",
    ]);
    // Every ancestor is on the path; a sibling command is not.
    for (const unit of placement.trail) expect(placement.path.has(unit.id)).toBe(true);
    expect(placement.path.has(organisationUnit("SYGOC").id)).toBe(false);
  });

  it("gives a viewer with no unit, such as a Customer, an empty placement", () => {
    const placement = locateViewer(organisationUnits, []);
    expect(placement.own.size).toBe(0);
    expect(placement.path.size).toBe(0);
    expect(placement.trail).toEqual([]);
  });

  it("marks every unit a multi-unit viewer belongs to and ignores unknown ids", () => {
    const first = organisationUnit("JOCK");
    const second = organisationUnit("SYGOC");
    const placement = locateViewer(organisationUnits, [first.id, "not-a-unit", second.id]);
    expect(placement.own).toEqual(new Set([first.id, second.id]));
    expect(placement.trail.map((unit) => unit.code)).toEqual(["CRIOC", "JOCK"]);
  });
});

describe("organisation page placement", () => {
  it("shows a staff member where they sit and marks their unit in the tree", async () => {
    const team = organisationUnit("SSG_TEAM");
    const session = {
      ...staffSession,
      user: { ...staffSession.user, organisationUnitIds: [team.id] },
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/organisation");

    const place = await screen.findByRole("region", { name: team.name });
    expect(within(place).getByText("Your place")).toBeInTheDocument();
    const trail = within(place).getByRole("list", { name: "Path from the root to your unit" });
    expect(
      within(trail)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["CRIOC", "JOCK", "ACSA-B Ops", "SSG Team"]);

    const hierarchy = screen.getByRole("list", { name: "Organisation hierarchy" });
    const here = within(hierarchy).getByText("You are here").closest("article")!;
    expect(here).toHaveAttribute("aria-current", "location");
    expect(within(here).getByText(team.name)).toBeInTheDocument();
    expect(within(hierarchy).getAllByText("You are here")).toHaveLength(1);
  });

  it("shows the hierarchy without a place card when the viewer holds no unit", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/organisation");
    expect(
      await screen.findByRole("heading", { name: "JIOC routing hierarchy" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Your place")).not.toBeInTheDocument();
    expect(screen.queryByText("You are here")).not.toBeInTheDocument();
  });
});
