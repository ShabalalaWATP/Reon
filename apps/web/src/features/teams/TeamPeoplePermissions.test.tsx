import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type {
  EligibleRosterAnalyst,
  TeamMember,
  TeamWorkspaceAccess,
} from "../../lib/api/teamTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const session: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "crioc-user",
    username: "admin75",
    displayName: "Willie Ormond",
    role: "INTAKE_TRIAGE",
    scope: "CRIOC",
  },
};
const baseAccess: TeamWorkspaceAccess = {
  teamId: "crioc",
  teamCode: "CRIOC",
  teamName: "CRIOC",
  unitKind: "ROOT",
  workspacePosition: "MANAGER",
  grantId: "grant-crioc",
  permissions: ["ROSTER"],
  views: ["OVERVIEW", "QUEUE", "CALENDAR", "PEOPLE", "STATISTICS", "HANDOVER", "ACTIVITY"],
};
const people: TeamMember[] = [
  member({ membershipId: "member-aaron", displayName: "Aaron Member" }),
  member({
    membershipId: "manager-zara",
    displayName: "Zara Manager",
    role: "INTAKE_TRIAGE",
    workspacePosition: "MANAGER",
  }),
];

describe("workspace People register", () => {
  it("sorts every column and puts Managers first initially", async () => {
    mockPeople(baseAccess);
    const user = userEvent.setup();
    renderApp("/teams/crioc/people");
    const table = await screen.findByRole("table", { name: "Workspace membership history" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("Zara Manager");
    const labels = ["Position", "Person", "Skills", "State", "Effective", "Active work", "Action"];
    for (const label of labels) {
      const header = within(table).getByRole("columnheader", { name: label });
      const button = within(header).getByRole("button", { name: label });
      await user.click(button);
      expect(header).toHaveAttribute(
        "aria-sort",
        label === "Position" ? "descending" : "ascending",
      );
      await user.click(button);
      expect(header).toHaveAttribute(
        "aria-sort",
        label === "Position" ? "ascending" : "descending",
      );
    }
  });

  it("keeps a Member read-only even if a stale roster grant is returned", async () => {
    mockPeople({ ...baseAccess, workspacePosition: "MEMBER" });
    renderApp("/teams/crioc/people");
    expect(await screen.findByText("Aaron Member")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Change roster" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "End membership" })).not.toBeInTheDocument();
  });

  it("explains an empty roster instead of showing a dead select on the only unit of its kind", async () => {
    // The routing root is the sole unit of its kind: every compatible Member
    // already sits here, so neither adding nor transferring has a candidate.
    const placedHere: EligibleRosterAnalyst = {
      accountId: "crioc-user",
      displayName: "Willie Ormond",
      currentTeamId: "crioc",
      currentTeamName: "CRIOC",
      currentMembershipId: "member-willie",
      currentMembershipVersion: 1,
      activeWorkCount: 0,
    };
    mockPeople(baseAccess, [placedHere]);
    const user = userEvent.setup();
    renderApp("/teams/crioc/people");
    await screen.findByRole("heading", { name: "Change roster" });

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Every compatible Member already belongs to this workspace.",
    );
    expect(screen.queryByLabelText(/^Member/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Member" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Schedule transfer" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "No compatible Member sits in another workspace of this kind, so there is nobody to transfer.",
    );
    expect(screen.getByRole("button", { name: "Confirm transfer" })).toBeDisabled();
  });
});

function mockPeople(access: TeamWorkspaceAccess, eligible: EligibleRosterAnalyst[] = []) {
  return mockFeatureFetch(
    async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
      if (url.pathname.endsWith("/people")) return json({ items: people });
      if (url.pathname.endsWith("/eligible-analysts")) return json({ items: eligible });
      throw new Error(`Unexpected ${url.pathname}`);
    },
    true,
    true,
    false,
  );
}

function member(overrides: Partial<TeamMember>): TeamMember {
  return {
    membershipId: "member",
    accountId: "account",
    displayName: "Member",
    role: "INTAKE_TRIAGE",
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
