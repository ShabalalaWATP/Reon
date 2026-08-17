import type { User } from "../../lib/api/types";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";

const accessLabels: Record<Exclude<User["role"], "QUALITY_RELEASE">, string> = {
  PLATFORM_ADMIN: "Platform administration",
  REQUESTER: "Own requests and released products",
  INTAKE_TRIAGE: "JIOC routing",
  SERVICE_COORDINATION: "Request coordination",
  OPERATIONS_ALLOCATION: "Ops routing",
  DELIVERY_TEAM_LEAD: "Team management",
  DELIVERY_SPECIALIST: "Assigned product work",
};

const roleDescriptions: Record<Exclude<User["role"], "QUALITY_RELEASE">, string> = {
  PLATFORM_ADMIN: "Maintains accounts and governed platform configuration.",
  REQUESTER:
    "Submits requests, tracks progress, responds when needed and receives released products.",
  INTAKE_TRIAGE: "Routes new requests from JIOC to the appropriate command.",
  SERVICE_COORDINATION: "Coordinates requests within the selected command.",
  OPERATIONS_ALLOCATION: "Routes requests from an Ops group to a delivery team.",
  DELIVERY_TEAM_LEAD: "Plans team work, assigns Analysts and reviews products.",
  DELIVERY_SPECIALIST: "Produces assigned products and requests Customer information when needed.",
};

export function profileAccessLabel(user: User, workspaces: TeamWorkspaceAccess[] = []) {
  const managed = workspaces
    .filter((item) => item.workspacePosition === "MANAGER")
    .map((item) => item.teamName);
  const access =
    user.role === "QUALITY_RELEASE"
      ? qualityAccessLabel(soleWorkspacePosition(workspaces))
      : accessLabels[user.role];
  return managed.length > 0 ? `${access}; Manager controls for ${managed.join(", ")}` : access;
}

export function profileRoleDescription(user: User, workspaces: TeamWorkspaceAccess[] = []) {
  if (user.role !== "QUALITY_RELEASE") return roleDescriptions[user.role];
  const position = soleWorkspacePosition(workspaces);
  if (position === "MEMBER") return "Completes quality checks on product packages.";
  if (position === "MANAGER")
    return "Completes quality checks and disseminates approved products to Customers.";
  return "Works within the combined quality control team.";
}

export function profileScopeLabel(user: User) {
  return user.role === "REQUESTER" ? "Personal Customer workspace" : user.scope;
}

export function profileInitials(displayName: string) {
  return displayName
    .split(/\s+/u)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase("en-GB"))
    .join("");
}

export function profileMembershipText(expected: number, names: string[], failed: boolean) {
  if (failed) return "Organisation assignments unavailable";
  if (expected === 0) return "No organisation unit assignment required";
  if (names.length === 0) return "Loading organisation assignments…";
  return names.join(", ");
}

/** The one workspace position a person holds, or undefined when none or mixed. */
export function soleWorkspacePosition(workspaces: TeamWorkspaceAccess[]) {
  const positions = new Set(workspaces.map((item) => item.workspacePosition).filter(Boolean));
  return positions.size === 1 ? [...positions][0] : undefined;
}

function qualityAccessLabel(position: ReturnType<typeof soleWorkspacePosition>) {
  if (position === "MEMBER") return "Quality control";
  if (position === "MANAGER") return "Quality control and dissemination";
  return "Combined quality control";
}

export function profilePositionLabel(workspaces: TeamWorkspaceAccess[]) {
  const positions = new Set(workspaces.map((item) => item.workspacePosition).filter(Boolean));
  if (positions.size !== 1) return positions.size > 1 ? "Mixed positions" : null;
  return sentenceCase([...positions][0]!);
}

export function profileWorkspacePositionText(
  expected: number,
  workspaces: TeamWorkspaceAccess[],
  failed: boolean,
) {
  if (failed) return "Workspace positions unavailable";
  if (expected === 0) return "No workspace position required";
  if (workspaces.length === 0) return "Loading workspace positions…";
  return workspaces
    .map((item) => `${sentenceCase(item.workspacePosition ?? "MEMBER")} in ${item.teamName}`)
    .join("; ");
}

function sentenceCase(value: string) {
  return `${value.slice(0, 1)}${value.slice(1).toLocaleLowerCase("en-GB")}`;
}
