import { disabledCapabilities } from "./api/capabilityClient";
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
  INTAKE_TRIAGE: "CRIOC routing queue",
  SERVICE_COORDINATION: "Incoming requests",
  OPERATIONS_ALLOCATION: "Ops routing queue",
  DELIVERY_TEAM_LEAD: "Team work queue",
  DELIVERY_SPECIALIST: "Production queue",
  QUALITY_RELEASE: "Quality and release queue",
};

export const roleLabels: Record<UserRole, string> = {
  PLATFORM_ADMIN: "Platform Administrator",
  REQUESTER: "Customer",
  INTAKE_TRIAGE: "CRIOC Routing User",
  SERVICE_COORDINATION: "Request Coordination User",
  OPERATIONS_ALLOCATION: "Ops Routing User",
  DELIVERY_TEAM_LEAD: "Team Manager",
  DELIVERY_SPECIALIST: "Team Analyst",
  QUALITY_RELEASE: "QC Manager",
};

export type NavigationItem = { label: string; path: string };

export type NavigationContext = {
  statisticsAvailable?: boolean;
  workspace?: { id: string; name: string };
};

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

const organisationLink = { label: "Organisation directory", path: "/organisation" };
const personalCalendarLink = { label: "Personal calendar", path: "/calendar/month" };

export function homeRouteForRole(role: UserRole) {
  if (role === "REQUESTER") return roleRoutes.REQUESTER;
  return "/overview";
}

export function navigationForRole(
  role: UserRole,
  capabilities = disabledCapabilities,
  context: NavigationContext = {},
): NavigationItem[] {
  if (role === "REQUESTER") return requesterNavigation();
  if (role === "PLATFORM_ADMIN") return administratorNavigation(capabilities, context);
  return staffNavigation(role, capabilities, context);
}

function requesterNavigation(): NavigationItem[] {
  return [
    { label: "My requests", path: "/requests" },
    { label: "New request", path: "/requests/new" },
  ];
}

function administratorNavigation(
  capabilities: typeof disabledCapabilities,
  context: NavigationContext,
): NavigationItem[] {
  const navigation = [
    { label: "Home", path: "/overview" },
    ...(capabilities.myWork ? [{ label: "My assigned actions", path: "/my-work" }] : []),
    { label: "User accounts", path: "/admin/users" },
    ...(capabilities.configuration
      ? [{ label: "Configuration", path: "/admin/configuration" }]
      : []),
    ...(context.statisticsAvailable
      ? [{ label: "Operational statistics", path: "/statistics" }]
      : []),
    personalCalendarLink,
    organisationLink,
  ];
  return navigation;
}

function staffNavigation(
  role: UserRole,
  capabilities: typeof disabledCapabilities,
  context: NavigationContext,
): NavigationItem[] {
  const navigation = [
    { label: "Home", path: "/overview" },
    ...(capabilities.myWork ? [{ label: "My assigned actions", path: "/my-work" }] : []),
    ...(context.workspace
      ? [
          {
            label: `${context.workspace.name} workspace`,
            path: `/teams/${context.workspace.id}/overview`,
          },
        ]
      : [{ label: queueLabelForRole(role), path: queueRoutes[role]! }]),
  ];
  navigation.push(personalCalendarLink);
  if (role === "DELIVERY_SPECIALIST" && capabilities.products) {
    navigation.push({ label: "Product package", path: "/product-packages/new" });
  }
  if (trackingRoles.includes(role)) {
    navigation.push({ label: "Request tracking", path: "/tracking" });
  }
  if (context.statisticsAvailable) {
    navigation.push({ label: "Operational statistics", path: "/statistics" });
  }
  navigation.push(organisationLink);
  return navigation;
}
