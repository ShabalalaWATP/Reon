export const protectedQueryKeys = {
  actions: (userId: string, filtersKey: string) =>
    ["protected", userId, "my-actions", filtersKey] as const,
  capabilities: (userId: string) =>
    ["protected", userId, "capabilities"] as const,
  adminUser: (userId: string, managedUserId: string | undefined) =>
    ["protected", userId, "admin-user", managedUserId] as const,
  adminUsers: (userId: string, query: string) =>
    ["protected", userId, "admin-users", query] as const,
  accountRequests: (userId: string) =>
    ["protected", userId, "account-requests"] as const,
  draft: (userId: string, draftId: string | undefined) =>
    ["protected", userId, "request-draft", draftId] as const,
  drafts: (userId: string) => ["protected", userId, "request-drafts"] as const,
  eligibleSpecialists: (userId: string, workItemId: string | undefined) =>
    ["protected", userId, "eligible-specialists", workItemId] as const,
  organisationUnits: (userId: string) =>
    ["protected", userId, "organisation-units"] as const,
  notificationCount: (userId: string) =>
    ["protected", userId, "notification-count"] as const,
  notificationPreferences: (userId: string) =>
    ["protected", userId, "notification-preferences"] as const,
  notifications: (userId: string, filtersKey: string) =>
    ["protected", userId, "notifications", filtersKey] as const,
  personalCalendar: (userId: string, start: string, end: string) =>
    ["protected", userId, "personal-calendar", start, end] as const,
  profile: (userId: string) => ["protected", userId, "profile"] as const,
  request: (userId: string, requestId: string | undefined) =>
    ["protected", userId, "request", requestId] as const,
  relatedRecords: (userId: string, workItemId: string, query: string) =>
    ["protected", userId, "related-records", workItemId, query] as const,
  requestLinks: (userId: string, workItemId: string) =>
    ["protected", userId, "request-links", workItemId] as const,
  requests: (userId: string) => ["protected", userId, "requests"] as const,
  routingOptions: (userId: string, workItemId: string | undefined) =>
    ["protected", userId, "routing-options", workItemId] as const,
  statistics: (
    userId: string,
    scopeId: string,
    unitId: string,
    from: string,
    to: string,
    timeZone: string,
  ) => [
    "protected",
    userId,
    "statistics",
    scopeId,
    unitId,
    from,
    to,
    timeZone,
  ] as const,
  statisticsScopes: (userId: string) =>
    ["protected", userId, "statistics-scopes"] as const,
  statisticsEvolution: (
    userId: string,
    scopeId: string,
    unitId: string,
    from: string,
    to: string,
    timeZone: string,
  ) => [
    "protected",
    userId,
    "statistics-evolution",
    scopeId,
    unitId,
    from,
    to,
    timeZone,
  ] as const,
  teamActivity: (userId: string, teamId: string | undefined) =>
    ["protected", userId, "team-activity", teamId] as const,
  teamBoard: (userId: string, teamId: string, filtersKey: string) =>
    ["protected", userId, "team-board", teamId, filtersKey] as const,
  teamCalendar: (userId: string, teamId: string | undefined, start: string, end: string) =>
    ["protected", userId, "team-calendar", teamId, start, end] as const,
  teamEligibleAnalysts: (userId: string, teamId: string | undefined) =>
    ["protected", userId, "team-eligible-analysts", teamId] as const,
  teamPeople: (userId: string, teamId: string | undefined) =>
    ["protected", userId, "team-people", teamId] as const,
  teamPackages: (userId: string, teamId: string) =>
    ["protected", userId, "team-packages", teamId] as const,
  teamIterations: (userId: string, teamId: string) =>
    ["protected", userId, "team-iterations", teamId] as const,
  teamPlanningCockpit: (userId: string, teamId: string) =>
    ["protected", userId, "team-planning-cockpit", teamId] as const,
  teamPlanningScenarios: (userId: string, teamId: string) =>
    ["protected", userId, "team-planning-scenarios", teamId] as const,
  teamPlanningTemplates: (userId: string, teamId: string) =>
    ["protected", userId, "team-planning-templates", teamId] as const,
  teamWorkspace: (userId: string, teamId: string | undefined) =>
    ["protected", userId, "team-workspace", teamId] as const,
  teamWorkspaces: (userId: string) =>
    ["protected", userId, "team-workspaces"] as const,
  workspaceRecords: (userId: string, unitId: string) =>
    ["protected", userId, "workspace-records", unitId] as const,
  trackedRequests: (userId: string) =>
    ["protected", userId, "tracked-requests"] as const,
  workItems: (userId: string, unitId?: string, requestId?: string) => requestId
    ? ["protected", userId, "work-items", "request", requestId] as const
    : unitId
      ? ["protected", userId, "work-items", "unit", unitId] as const
      : ["protected", userId, "work-items"] as const,
};
