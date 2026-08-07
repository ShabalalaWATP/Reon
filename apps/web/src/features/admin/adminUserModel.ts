import type { OrganisationUnit, UserRole } from "../../lib/api/types";

export const editableRoles: UserRole[] = [
  "PLATFORM_ADMIN",
  "REQUESTER",
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
  "DELIVERY_TEAM_LEAD",
  "DELIVERY_SPECIALIST",
  "QUALITY_RELEASE",
];

const compatibleKinds: Partial<Record<UserRole, OrganisationUnit["kind"]>> = {
  INTAKE_TRIAGE: "ROOT",
  SERVICE_COORDINATION: "COMMAND",
  OPERATIONS_ALLOCATION: "OPS_GROUP",
  DELIVERY_TEAM_LEAD: "TEAM",
  DELIVERY_SPECIALIST: "TEAM",
};

export function membershipOptions(role: UserRole, units: OrganisationUnit[]) {
  const kind = compatibleKinds[role];
  return kind ? units.filter((unit) => unit.kind === kind) : [];
}

export function roleNeedsMembership(role: UserRole) {
  return Boolean(compatibleKinds[role]);
}
