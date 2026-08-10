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

const queueRoutes: Partial<Record<UserRole, string>> = {
  INTAKE_TRIAGE: "/triage",
  SERVICE_COORDINATION: "/coordination",
  OPERATIONS_ALLOCATION: "/allocation",
  DELIVERY_TEAM_LEAD: "/delivery/team",
  DELIVERY_SPECIALIST: "/delivery/my-work",
  QUALITY_RELEASE: "/quality-release",
};

const queueLabels: Partial<Record<UserRole, string>> = {
  INTAKE_TRIAGE: "JIOC queue",
  SERVICE_COORDINATION: "Command queue",
  OPERATIONS_ALLOCATION: "Ops queue",
  DELIVERY_TEAM_LEAD: "Team queue",
  DELIVERY_SPECIALIST: "Production queue",
  QUALITY_RELEASE: "QC queue",
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

export function queueLabelForRole(role: UserRole) {
  return queueLabels[role] ?? "Work queue";
}

export function isNavigationItemActive(pathname: string, path: string) {
  if (path === "/requests") {
    return pathname === path || /^\/requests\/(?!new(?:\/|$))/u.test(pathname);
  }
  return pathname === path || pathname.startsWith(`${path}/`);
}
export const trackingRoles: UserRole[] = [
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
];

const organisationLink = { label: "Organisation", path: "/organisation" };

export function homeRouteForRole(role: UserRole, capabilities: ServerCapabilities) {
  if (role === "REQUESTER") return roleRoutes.REQUESTER;
  if (
    capabilities.statistics
    && ["PLATFORM_ADMIN", "INTAKE_TRIAGE", "SERVICE_COORDINATION", "OPERATIONS_ALLOCATION", "DELIVERY_TEAM_LEAD", "QUALITY_RELEASE"].includes(role)
  ) return "/overview";
  return capabilities.myWork ? "/my-work" : roleRoutes[role];
}

export function navigationForRole(role: UserRole, capabilities = disabledCapabilities): NavigationItem[] {
  if (role === "REQUESTER") {
    return [
      { label: "My requests", path: "/requests" },
      { label: "New request", path: "/requests/new" },
      organisationLink,
    ];
  }
  if (role === "PLATFORM_ADMIN") {
    return [
      ...(capabilities.statistics ? [{ label: "Overview", path: "/overview" }] : []),
      ...(capabilities.myWork ? [{ label: "My actions", path: "/my-work" }] : []),
      { label: "User accounts", path: "/admin/users" },
      ...(capabilities.configuration ? [{ label: "Configuration", path: "/admin/configuration" }] : []),
      organisationLink,
    ];
  }
  const navigation = [
    ...(role !== "DELIVERY_SPECIALIST" && capabilities.statistics ? [{ label: "Overview", path: "/overview" }] : []),
    ...(capabilities.myWork ? [{ label: "My actions", path: "/my-work" }] : []),
    { label: queueLabelForRole(role), path: queueRoutes[role]! },
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
