import { disabledCapabilities } from "./api/capabilityClient";
import type { ServerCapabilities } from "./api/capabilityClient";
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

export const queueRoutes: Partial<Record<UserRole, string>> = {
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

export function homeRouteForRole(role: UserRole, capabilities: ServerCapabilities) {
  return capabilities.myWork ? "/my-work" : roleRoutes[role];
}

export function navigationForRole(role: UserRole, capabilities = disabledCapabilities): NavigationItem[] {
  if (role === "REQUESTER") {
    return [
      ...(capabilities.myWork ? [{ label: "My work", path: "/my-work" }] : []),
      { label: "My requests", path: "/requests" },
      { label: "New request", path: "/requests/new" },
      organisationLink,
    ];
  }
  if (role === "PLATFORM_ADMIN") {
    return [
      ...(capabilities.myWork ? [{ label: "My work", path: "/my-work" }] : []),
      { label: "User accounts", path: "/admin/users" },
      ...(capabilities.configuration ? [{ label: "Configuration", path: "/admin/configuration" }] : []),
      organisationLink,
    ];
  }
  const navigation = [
    ...(capabilities.myWork ? [{ label: "My work", path: "/my-work" }] : []),
    { label: role === "DELIVERY_SPECIALIST" ? "Production queue" : "Work queue", path: queueRoutes[role]! },
  ];
  if (role === "DELIVERY_SPECIALIST" && capabilities.products) {
    navigation.push({ label: "Product package", path: "/product-packages/new" });
  }
  if (trackingRoles.includes(role)) {
    navigation.push({ label: "Tracking", path: "/tracking" });
  }
  navigation.push(organisationLink);
  return navigation;
}
