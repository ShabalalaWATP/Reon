import type { EligibleRosterAnalyst } from "../../lib/api/teamTypes";

export type RosterMode = "add" | "transfer";

export function rosterOptions(items: EligibleRosterAnalyst[], mode: RosterMode, teamId: string) {
  if (mode === "add") return items.filter((item) => item.currentTeamId === null);
  return items.filter((item) => item.currentTeamId !== null && item.currentTeamId !== teamId);
}

/**
 * Explain an empty roster list rather than presenting a dead select. Every
 * compatible Member already placed is a normal state; a routing workspace that
 * is the only unit of its kind can never receive a transfer.
 */
export function rosterEmptyReason(
  items: EligibleRosterAnalyst[],
  mode: RosterMode,
  teamId: string,
): string | null {
  if (rosterOptions(items, mode, teamId).length > 0) return null;
  const elsewhere = items.some(
    (item) => item.currentTeamId !== null && item.currentTeamId !== teamId,
  );
  if (mode === "add") {
    if (items.length === 0) {
      return "No compatible Members exist yet. A Platform Administrator creates them.";
    }
    return elsewhere
      ? "Every compatible Member already has a home workspace. Use Schedule transfer to move one here."
      : "Every compatible Member already belongs to this workspace.";
  }
  return "No compatible Member sits in another workspace of this kind, so there is nobody to transfer.";
}
