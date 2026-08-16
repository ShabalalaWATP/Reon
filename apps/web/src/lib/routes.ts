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

type WorkspacePosition = "MANAGER" | "MEMBER" | null | undefined;

/**
 * Name a person by role, refined by workspace position where the role spans
 * two positions. QC is one authorisation role with two positions: a QC User
 * reviews, a QC Manager also releases. Delivery teams express the same split
 * as two roles, so only QC needs the position to disambiguate.
 */
export function memberLabel(role: UserRole, position: WorkspacePosition): string {
  if (role === "QUALITY_RELEASE" && position === "MEMBER") return "QC User";
  return roleLabels[role];
}

const APP_NAME = "Mist Service";

// Ordered by specificity: the first matching pattern names the page.
const routeTitles: readonly (readonly [RegExp, string])[] = [
  [/^\/login$/u, "Sign in"],
  [/^\/overview$/u, "Home"],
  [/^\/my-work$/u, "My assigned actions"],
  [/^\/profile$/u, "Profile"],
  [/^\/notifications$/u, "Notifications"],
  [/^\/organisation$/u, "Organisation directory"],
  [/^\/calendar(?:\/|$)/u, "Personal calendar"],
  [/^\/statistics$/u, "Operational statistics"],
  [/^\/teams\/[^/]+\/people(?:\/|$)/u, "Team member profile"],
  [/^\/teams(?:\/|$)/u, "Team workspace"],
  [/^\/admin\/users\/new$/u, "New user account"],
  [/^\/admin\/users(?:\/|$)/u, "User accounts"],
  [/^\/admin\/configuration(?:\/|$)/u, "Configuration"],
  [/^\/product-packages(?:\/|$)/u, "Product package"],
  [/^\/tracking\/[^/]+$/u, "Tracked request"],
  [/^\/tracking$/u, "Request tracking"],
  [/^\/triage$/u, "CRIOC routing queue"],
  [/^\/coordination$/u, "Incoming requests"],
  [/^\/allocation$/u, "Ops routing queue"],
  [/^\/delivery\/team$/u, "Team work queue"],
  [/^\/delivery\/my-work$/u, "Production queue"],
  [/^\/quality-release$/u, "Quality and release queue"],
  [/^\/requests\/new$/u, "New request"],
  [/^\/requests\/drafts(?:\/|$)/u, "Request draft"],
  [/^\/requests\/[^/]+$/u, "Request detail"],
  [/^\/requests$/u, "My requests"],
];

export function documentTitleForRoute(pathname: string) {
  const match = routeTitles.find(([pattern]) => pattern.test(pathname));
  return match ? `${match[1]} · ${APP_NAME}` : APP_NAME;
}

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
