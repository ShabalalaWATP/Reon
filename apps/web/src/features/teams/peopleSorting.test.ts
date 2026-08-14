import { describe, expect, it } from "vitest";

import type { TeamMember } from "../../lib/api/teamTypes";
import { DEFAULT_PEOPLE_SORT, sortPeople, type PeopleSortKey } from "./peopleSorting";

const people: TeamMember[] = [
  member({
    membershipId: "zed",
    displayName: "Zed Member",
    skills: ["Zulu"],
    effectiveFrom: "2026-01-01T09:00:00Z",
  }),
  member({
    membershipId: "alice",
    displayName: "Alice Manager",
    role: "DELIVERY_TEAM_LEAD",
    workspacePosition: "MANAGER",
    skills: ["Leadership"],
    effectiveFrom: "2026-02-01T09:00:00Z",
  }),
  member({
    membershipId: "beth",
    displayName: "Beth Former",
    state: "ENDED",
    skills: ["Alpha"],
    effectiveFrom: "2026-03-01T09:00:00Z",
    effectiveUntil: "2026-04-01T09:00:00Z",
  }),
  member({
    membershipId: "craig",
    displayName: "Craig Busy",
    skills: ["Beta"],
    activeWorkCount: 2,
    effectiveFrom: "2026-04-01T09:00:00Z",
  }),
];

describe("people sorting", () => {
  it("places Managers first by default with a deterministic name tie-break", () => {
    expect(sortPeople(people, DEFAULT_PEOPLE_SORT, true).map((item) => item.displayName)).toEqual([
      "Alice Manager",
      "Zed Member",
      "Craig Busy",
      "Beth Former",
    ]);
  });

  it.each<[PeopleSortKey, string, string]>([
    ["person", "Alice Manager", "Zed Member"],
    ["position", "Alice Manager", "Zed Member"],
    ["skills", "Beth Former", "Zed Member"],
    ["state", "Alice Manager", "Beth Former"],
    ["effective", "Zed Member", "Craig Busy"],
    ["activeWork", "Alice Manager", "Craig Busy"],
    ["action", "Zed Member", "Alice Manager"],
  ])("sorts %s in both directions", (key, firstAscending, firstDescending) => {
    expect(sortPeople(people, { key, direction: "ascending" }, true)[0].displayName).toBe(
      firstAscending,
    );
    expect(sortPeople(people, { key, direction: "descending" }, true)[0].displayName).toBe(
      firstDescending,
    );
  });
});

function member(overrides: Partial<TeamMember>): TeamMember {
  return {
    membershipId: "member",
    accountId: "account",
    displayName: "Member",
    role: "DELIVERY_SPECIALIST",
    workspacePosition: "MEMBER",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    skills: [],
    startReason: null,
    endReason: null,
    ...overrides,
  };
}
