import type { UserRole } from "./api/types";

export const roleRoutes: Record<UserRole, string> = {
  PLATFORM_ADMIN: "/admin/users",
  REQUESTER: "/requests",
  INTAKE_TRIAGE: "/triage",
  SERVICE_COORDINATION: "/coordination",
  OPERATIONS_ALLOCATION: "/allocation",
  DELIVERY_TEAM_LEAD: "/delivery/team",
  DELIVERY_SPECIALIST: "/delivery/my-work",
  QUALITY_RELEASE: "/quality-release",
};

export const roleLabels: Record<UserRole, string> = {
  PLATFORM_ADMIN: "Platform Administrator",
  REQUESTER: "Customer",
  INTAKE_TRIAGE: "JIOC Routing User",
  SERVICE_COORDINATION: "Command Routing User",
  OPERATIONS_ALLOCATION: "Ops Routing User",
  DELIVERY_TEAM_LEAD: "Team Manager",
  DELIVERY_SPECIALIST: "Team Analyst",
  QUALITY_RELEASE: "QC Manager",
};

export type NavigationItem = { label: string; path: string };
export const trackingRoles: UserRole[] = [
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
];

const organisationLink = { label: "Organisation", path: "/organisation" };

export function navigationForRole(role: UserRole): NavigationItem[] {
  if (role === "REQUESTER") {
    return [
      { label: "My requests", path: "/requests" },
      { label: "New request", path: "/requests/new" },
      organisationLink,
    ];
  }
  if (role === "PLATFORM_ADMIN") {
    return [
      { label: "User accounts", path: "/admin/users" },
      organisationLink,
    ];
  }
  const navigation = [{ label: "Work queue", path: roleRoutes[role] }];
  if (trackingRoles.includes(role)) {
    navigation.push({ label: "Tracking", path: "/tracking" });
  }
  navigation.push(organisationLink);
  return navigation;
}
