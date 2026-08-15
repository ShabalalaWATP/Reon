import type { AccountContext, Session } from "./coreTypes";

export type ProtectedQueryScope = {
  activeContext: AccountContext;
  contextVersion: number;
  userId: string;
};

type QueryScopeInput = ProtectedQueryScope | Session | null;
type NormalisedQueryScope = Omit<ProtectedQueryScope, "activeContext"> & {
  activeContext: AccountContext | "ANONYMOUS";
};

function protectedQueryScope(session: Session): ProtectedQueryScope {
  return {
    activeContext: session.activeContext,
    contextVersion: session.contextVersion,
    userId: session.user.id,
  };
}

export function protectedQueryKeys(input: QueryScopeInput) {
  const scope = normaliseScope(input);
  const root = ["protected", scope.userId, scope.activeContext, scope.contextVersion] as const;
  return {
    root: () => root,
    actions: (filtersKey: string) => [...root, "my-actions", filtersKey] as const,
    actionPages: (filtersKey: string) => [...root, "my-actions", filtersKey, "pages"] as const,
    actionsRoot: () => [...root, "my-actions"] as const,
    capabilities: () => [...root, "capabilities"] as const,
    configurationVersions: () => [...root, "configuration-versions"] as const,
    configurationVersion: (versionId: string | undefined) =>
      [...root, "configuration-version", versionId] as const,
    configurationPreview: (versionId: string | undefined, version: number | undefined) =>
      [...root, "configuration-preview", versionId, version] as const,
    conversations: (requestId: string) => [...root, "request-conversations", requestId] as const,
    adminUser: (managedUserId: string | undefined) =>
      [...root, "admin-user", managedUserId] as const,
    adminUsers: (query: string) => [...root, "admin-users", query] as const,
    adminUsersRoot: () => [...root, "admin-users"] as const,
    accountRequests: () => [...root, "account-requests"] as const,
    draft: (draftId: string | undefined) => [...root, "request-draft", draftId] as const,
    drafts: () => [...root, "request-drafts"] as const,
    eligibleSpecialists: (workItemId: string | undefined) =>
      [...root, "eligible-specialists", workItemId] as const,
    organisationUnits: () => [...root, "organisation-units"] as const,
    notificationCount: () => [...root, "notification-count"] as const,
    notificationPreferences: () => [...root, "notification-preferences"] as const,
    notifications: (filtersKey: string) => [...root, "notifications", filtersKey] as const,
    notificationsRoot: () => [...root, "notifications"] as const,
    personalCalendar: (start: string, end: string) =>
      [...root, "personal-calendar", start, end] as const,
    profile: () => [...root, "profile"] as const,
    productPackage: (packageId: string) => [...root, "product-package", packageId] as const,
    request: (requestId: string | undefined) => [...root, "request", requestId] as const,
    requestProductPackage: (requestId: string) =>
      [...root, "request-product-package", requestId] as const,
    requestRelease: (requestId: string) => [...root, "request-release", requestId] as const,
    relatedRecords: (workItemId: string, query: string) =>
      [...root, "related-records", workItemId, query] as const,
    requestLinks: (workItemId: string) => [...root, "request-links", workItemId] as const,
    requests: () => [...root, "requests"] as const,
    routingOptions: (workItemId: string | undefined) =>
      [...root, "routing-options", workItemId] as const,
    statistics: (scopeId: string, unitId: string, from: string, to: string, timeZone: string) =>
      [...root, "statistics", scopeId, unitId, from, to, timeZone] as const,
    statisticsScopes: () => [...root, "statistics-scopes"] as const,
    statisticsEvolution: (
      scopeId: string,
      unitId: string,
      from: string,
      to: string,
      timeZone: string,
    ) => [...root, "statistics-evolution", scopeId, unitId, from, to, timeZone] as const,
    teamActivity: (teamId: string | undefined) => [...root, "team-activity", teamId] as const,
    teamBoard: (teamId: string, filtersKey: string) =>
      [...root, "team-board", teamId, filtersKey] as const,
    teamBoardRoot: (teamId: string) => [...root, "team-board", teamId] as const,
    teamBoardRequest: (teamId: string, requestId: string | null) =>
      [...root, "team-board-request", teamId, requestId] as const,
    teamCalendar: (teamId: string | undefined, start: string, end: string) =>
      [...root, "team-calendar", teamId, start, end] as const,
    teamEligibleAnalysts: (teamId: string | undefined) =>
      [...root, "team-eligible-analysts", teamId] as const,
    teamPeople: (teamId: string | undefined) => [...root, "team-people", teamId] as const,
    teamRecords: (teamId: string) => [...root, "team-records", teamId] as const,
    teamMemberProfile: (teamId: string | undefined, memberId: string | undefined) =>
      [...root, "team-member-profile", teamId, memberId] as const,
    teamPackages: (teamId: string) => [...root, "team-packages", teamId] as const,
    teamIterations: (teamId: string) => [...root, "team-iterations", teamId] as const,
    teamWorkspace: (teamId: string | undefined) => [...root, "team-workspace", teamId] as const,
    teamWorkspaces: () => [...root, "team-workspaces"] as const,
    trackedRequests: (filters = "") => [...root, "tracked-requests", filters] as const,
    trackedRequest: (requestId: string) => [...root, "tracked-requests", requestId] as const,
    workItems: (unitId?: string, requestId?: string) =>
      requestId
        ? ([...root, "work-items", "request", requestId] as const)
        : unitId
          ? ([...root, "work-items", "unit", unitId] as const)
          : ([...root, "work-items"] as const),
    workItemPages: (unitId?: string, requestId?: string) =>
      requestId
        ? ([...root, "work-items", "request", requestId, "pages"] as const)
        : unitId
          ? ([...root, "work-items", "unit", unitId, "pages"] as const)
          : ([...root, "work-items", "pages"] as const),
    workflowDefinitions: () => [...root, "workflow-definitions"] as const,
  };
}

function normaliseScope(input: QueryScopeInput): NormalisedQueryScope {
  if (!input) {
    return { activeContext: "ANONYMOUS", contextVersion: 0, userId: "anonymous" };
  }
  if ("user" in input) return protectedQueryScope(input);
  return input;
}
