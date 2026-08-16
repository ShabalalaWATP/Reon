import { describe, expect, it } from "vitest";

import type { EligibleRosterAnalyst } from "../../lib/api/teamTypes";
import { rosterEmptyReason } from "./rosterEmptyReason";

const here = (id: string): EligibleRosterAnalyst => ({
  accountId: id,
  displayName: id,
  currentTeamId: "team-a",
  currentTeamName: "Team A",
  currentMembershipId: `m-${id}`,
  currentMembershipVersion: 1,
  activeWorkCount: 0,
});
const elsewhere = (id: string): EligibleRosterAnalyst => ({
  ...here(id),
  currentTeamId: "team-b",
  currentTeamName: "Team B",
});
const unassigned = (id: string): EligibleRosterAnalyst => ({
  ...here(id),
  currentTeamId: null,
  currentTeamName: null,
  currentMembershipId: null,
  currentMembershipVersion: null,
});

describe("roster empty reasons", () => {
  it("is silent whenever a candidate exists", () => {
    expect(rosterEmptyReason([unassigned("u")], "add", "team-a")).toBeNull();
    expect(rosterEmptyReason([elsewhere("e")], "transfer", "team-a")).toBeNull();
  });

  it("explains that nobody compatible exists yet", () => {
    expect(rosterEmptyReason([], "add", "team-a")).toMatch(
      /A Platform Administrator creates them/u,
    );
  });

  it("points to transfer only when someone can actually be transferred", () => {
    expect(rosterEmptyReason([elsewhere("e")], "add", "team-a")).toMatch(/Use Schedule transfer/u);
    expect(rosterEmptyReason([here("h")], "add", "team-a")).toBe(
      "Every compatible Member already belongs to this workspace.",
    );
  });

  it("explains that a sole unit of its kind has nobody to transfer", () => {
    expect(rosterEmptyReason([here("h")], "transfer", "team-a")).toMatch(/nobody to transfer/u);
  });
});
