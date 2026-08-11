import type { MembershipState, TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";

export type PeopleSortKey = "person" | "position" | "skills" | "state" | "effective" | "activeWork" | "action";
export type PeopleSort = { key: PeopleSortKey; direction: "ascending" | "descending" };

export const DEFAULT_PEOPLE_SORT: PeopleSort = { key: "position", direction: "ascending" };

const names = new Intl.Collator("en-GB", { numeric: true, sensitivity: "base" });
const stateRank: Record<MembershipState, number> = { CURRENT: 0, SCHEDULED: 1, ENDED: 2 };

export function canManageRoster(access: TeamWorkspaceAccess) {
  return access.workspacePosition === "MANAGER"
    && Boolean(access.grantId)
    && access.permissions.includes("ROSTER");
}

export function memberPosition(member: TeamMember) {
  return member.workspacePosition
    ?? (member.role === "DELIVERY_TEAM_LEAD" ? "MANAGER" : "MEMBER");
}

export function canEndMembership(access: TeamWorkspaceAccess, member: TeamMember) {
  return canManageRoster(access)
    && memberPosition(member) === "MEMBER"
    && member.state === "CURRENT";
}

export function sortPeople(items: TeamMember[], sort: PeopleSort, canManage: boolean) {
  const originalPosition = new Map(items.map((item, index) => [item.membershipId, index]));
  return [...items].sort((left, right) => {
    const primary = compare(left, right, sort.key, canManage);
    if (primary !== 0) return sort.direction === "ascending" ? primary : -primary;
    if (sort.key === "position") {
      const state = stateRank[left.state] - stateRank[right.state];
      if (state !== 0) return state;
      return (originalPosition.get(left.membershipId) ?? 0)
        - (originalPosition.get(right.membershipId) ?? 0);
    }
    return names.compare(left.displayName, right.displayName)
      || names.compare(left.membershipId, right.membershipId);
  });
}

function compare(left: TeamMember, right: TeamMember, key: PeopleSortKey, canManage: boolean) {
  switch (key) {
    case "person": return names.compare(left.displayName, right.displayName);
    case "position": return positionRank(left) - positionRank(right);
    case "skills": return names.compare(left.skills.join(" "), right.skills.join(" "));
    case "state": return stateRank[left.state] - stateRank[right.state];
    case "effective": return Date.parse(left.effectiveFrom) - Date.parse(right.effectiveFrom);
    case "activeWork": return left.activeWorkCount - right.activeWorkCount;
    case "action": return actionRank(left, canManage) - actionRank(right, canManage);
  }
}

function positionRank(member: TeamMember) {
  return memberPosition(member) === "MANAGER" ? 0 : 1;
}

function actionRank(member: TeamMember, canManage: boolean) {
  if (!canManage || memberPosition(member) === "MANAGER" || member.state !== "CURRENT") return 2;
  return member.activeWorkCount === 0 ? 0 : 1;
}
