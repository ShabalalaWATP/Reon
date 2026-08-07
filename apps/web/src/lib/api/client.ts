import type {
  AdminUser,
  AdminUserStatusInput,
  AdminUserUpdateInput,
  AdminUserWriteInput,
  EligibleSpecialist,
  Feedback,
  FeedbackInput,
  ListResponse,
  OrganisationUnit,
  OrganisationUnitRenameInput,
  RequestCreateInput,
  RequestDraft,
  RequestDraftInput,
  RequestDraftSubmitInput,
  RequestDraftUpdateInput,
  RequestDetail,
  RequestSummary,
  RelatedRecordCandidate,
  RequestLinkCreateInput,
  RequestLinkWorkspace,
  Session,
  TrackedRequest,
  WorkAction,
  WorkItem,
} from "./types";
import type {
  StatisticsDashboard,
  StatisticsScopeList,
} from "./statisticsTypes";
import type {
  AddMemberInput,
  EligibleRosterAnalystList,
  EndMembershipInput,
  TeamActivityList,
  TeamPeople,
  TeamWorkspaceList,
  TeamWorkspaceOverview,
  TransferMemberInput,
} from "./teamTypes";
import type {
  CalendarEventInput,
  CalendarEventResult,
  CalendarEventUpdateInput,
  CalendarOccurrence,
  CapacityCommitInput,
  CapacityPreview,
  CapacityPreviewInput,
  CapacitySnapshot,
  CommitmentDecisionInput,
  CommitmentInput,
  FutureSplitInput,
  OccurrenceCancelInput,
  OccurrenceEditInput,
  TeamCalendarEventInput,
} from "./calendarTypes";

const API_ROOT = "/api/v1";
export const SESSION_EXPIRED_EVENT = "istari:session-expired";

export function productDownloadUrl(requestId: string) {
  return `${API_ROOT}/requests/${encodeURIComponent(requestId)}/product`;
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  csrfToken?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (options.csrfToken) headers.set("X-CSRF-Token", options.csrfToken);
  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const fallback = `Request failed with status ${response.status}.`;
    let message = fallback;
    let code: string | undefined;
    try {
      const error = (await response.json()) as {
        code?: string;
        message?: string;
        detail?: string | { code?: string; message?: string };
      };
      if (typeof error.detail === "string") message = error.detail;
      else if (error.detail) {
        message = error.detail.message ?? fallback;
        code = error.detail.code;
      } else {
        message = error.message ?? fallback;
        code = error.code;
      }
    } catch {
      // The HTTP status remains useful when an upstream response is not JSON.
    }
    throw new ApiError(message, response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  adminUsers: (query = "") =>
    apiRequest<ListResponse<AdminUser>>(
      `/admin/users${query ? `?query=${encodeURIComponent(query)}` : ""}`,
    ),
  adminUser: (id: string) =>
    apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}`),
  createAdminUser: (input: AdminUserWriteInput, csrfToken: string) =>
    apiRequest<AdminUser>("/admin/users", {
      body: input,
      csrfToken,
      method: "POST",
    }),
  updateAdminUser: (
    id: string,
    input: AdminUserUpdateInput,
    csrfToken: string,
  ) => apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}`, {
    body: input,
    csrfToken,
    method: "PATCH",
  }),
  updateAdminUserStatus: (
    id: string,
    input: AdminUserStatusInput,
    csrfToken: string,
  ) => apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}/status`, {
    body: input,
    csrfToken,
    method: "PATCH",
  }),
  renameOrganisationUnit: (
    id: string,
    input: OrganisationUnitRenameInput,
    csrfToken: string,
  ) => apiRequest<OrganisationUnit>(
    `/admin/organisation/units/${encodeURIComponent(id)}`,
    { body: input, csrfToken, method: "PATCH" },
  ),
  login: (credentials: { username: string; password: string }) =>
    apiRequest<Session>("/auth/login", { body: credentials, method: "POST" }),
  elevate: (password: string, csrfToken: string) =>
    apiRequest<{ elevatedUntil: string }>("/auth/elevate", {
      body: { password },
      csrfToken,
      method: "POST",
    }),
  session: () => apiRequest<Session>("/auth/me"),
  statisticsScopes: () =>
    apiRequest<StatisticsScopeList>("/statistics/scopes"),
  statistics: (input: {
    scopeId: string;
    from: string;
    to: string;
    timeZone: string;
  }) => {
    const query = new URLSearchParams(input);
    return apiRequest<StatisticsDashboard>(`/statistics?${query.toString()}`);
  },
  teamWorkspaces: () => apiRequest<TeamWorkspaceList>("/team-workspaces"),
  teamWorkspace: (teamId: string) =>
    apiRequest<TeamWorkspaceOverview>(
      `/team-workspaces/${encodeURIComponent(teamId)}`,
    ),
  teamPeople: (teamId: string) =>
    apiRequest<TeamPeople>(
      `/team-workspaces/${encodeURIComponent(teamId)}/people`,
    ),
  eligibleRosterAnalysts: (teamId: string, grantId: string) =>
    apiRequest<EligibleRosterAnalystList>(
      `/team-workspaces/${encodeURIComponent(teamId)}/eligible-analysts?grantId=${encodeURIComponent(grantId)}`,
    ),
  teamActivity: (teamId: string) =>
    apiRequest<TeamActivityList>(
      `/team-workspaces/${encodeURIComponent(teamId)}/activity`,
    ),
  personalCalendar: (from: string, to: string) => {
    const query = new URLSearchParams({ from, to });
    return apiRequest<{ items: CalendarOccurrence[] }>(`/calendar/personal?${query.toString()}`);
  },
  teamCalendar: (teamId: string, from: string, to: string) => {
    const query = new URLSearchParams({ from, to });
    return apiRequest<{ items: CalendarOccurrence[] }>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar?${query.toString()}`);
  },
  createPersonalCalendarEvent: (input: CalendarEventInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>("/calendar/events", { body: input, csrfToken, method: "POST" }),
  createTeamCalendarEvent: (teamId: string, input: TeamCalendarEventInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar/events`, { body: input, csrfToken, method: "POST" }),
  createCalendarCommitment: (teamId: string, input: CommitmentInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar/commitments`, { body: input, csrfToken, method: "POST" }),
  updateCalendarEvent: (eventId: string, input: CalendarEventUpdateInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}`, { body: input, csrfToken, method: "PUT" }),
  cancelCalendarEvent: (eventId: string, input: OccurrenceCancelInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/cancel`, { body: input, csrfToken, method: "POST" }),
  cancelCalendarOccurrence: (eventId: string, input: OccurrenceCancelInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/occurrences/cancel`, { body: input, csrfToken, method: "POST" }),
  editCalendarOccurrence: (eventId: string, input: OccurrenceEditInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/occurrences/edit`, { body: input, csrfToken, method: "POST" }),
  splitCalendarSeries: (eventId: string, input: FutureSplitInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/split`, { body: input, csrfToken, method: "POST" }),
  decideCalendarCommitment: (eventId: string, input: CommitmentDecisionInput, acknowledge: boolean, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/${acknowledge ? "acknowledge" : "dispute"}`, { body: input, csrfToken, method: "POST" }),
  previewTeamCapacity: (teamId: string, input: CapacityPreviewInput, csrfToken: string) =>
    apiRequest<CapacityPreview>(`/team-workspaces/${encodeURIComponent(teamId)}/capacity/previews`, { body: input, csrfToken, method: "POST" }),
  commitTeamCapacity: (teamId: string, input: CapacityCommitInput, csrfToken: string) =>
    apiRequest<CapacitySnapshot>(`/team-workspaces/${encodeURIComponent(teamId)}/capacity/commits`, { body: input, csrfToken, method: "POST" }),
  addTeamMember: (teamId: string, input: AddMemberInput, csrfToken: string) =>
    apiRequest<TeamPeople>(
      `/team-workspaces/${encodeURIComponent(teamId)}/memberships`,
      { body: input, csrfToken, method: "POST" },
    ),
  transferTeamMember: (
    teamId: string,
    input: TransferMemberInput,
    csrfToken: string,
  ) => apiRequest<TeamPeople>(
    `/team-workspaces/${encodeURIComponent(teamId)}/transfers`,
    { body: input, csrfToken, method: "POST" },
  ),
  endTeamMembership: (
    teamId: string,
    membershipId: string,
    input: EndMembershipInput,
    csrfToken: string,
  ) => apiRequest<TeamPeople>(
    `/team-workspaces/${encodeURIComponent(teamId)}/memberships/${encodeURIComponent(membershipId)}/end`,
    { body: input, csrfToken, method: "POST" },
  ),
  logout: (csrfToken: string) =>
    apiRequest<void>("/auth/logout", { csrfToken, method: "POST" }),
  requests: () => apiRequest<ListResponse<RequestSummary>>("/requests"),
  drafts: () => apiRequest<ListResponse<RequestDraft>>("/request-drafts"),
  draft: (id: string) =>
    apiRequest<RequestDraft>(`/request-drafts/${encodeURIComponent(id)}`),
  createDraft: (input: RequestDraftInput, csrfToken: string) =>
    apiRequest<RequestDraft>("/request-drafts", {
      body: input,
      csrfToken,
      method: "POST",
    }),
  updateDraft: (
    id: string,
    input: RequestDraftUpdateInput,
    csrfToken: string,
  ) => apiRequest<RequestDraft>(`/request-drafts/${encodeURIComponent(id)}`, {
    body: input,
    csrfToken,
    method: "PATCH",
  }),
  deleteDraft: (id: string, expectedVersion: number, csrfToken: string) =>
    apiRequest<void>(
      `/request-drafts/${encodeURIComponent(id)}?expectedVersion=${expectedVersion}`,
      { csrfToken, method: "DELETE" },
    ),
  submitDraft: (
    id: string,
    input: RequestDraftSubmitInput,
    csrfToken: string,
  ) => apiRequest<RequestDetail>(`/request-drafts/${encodeURIComponent(id)}/submit`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  request: (id: string) => apiRequest<RequestDetail>(`/requests/${encodeURIComponent(id)}`),
  createRequest: (input: RequestCreateInput, csrfToken: string) =>
    apiRequest<RequestDetail>("/requests", { body: input, csrfToken, method: "POST" }),
  feedback: (id: string, input: FeedbackInput, csrfToken: string) =>
    apiRequest<Feedback>(`/requests/${encodeURIComponent(id)}/feedback`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
  workItems: () => apiRequest<ListResponse<WorkItem>>("/work-items"),
  organisationUnits: () =>
    apiRequest<ListResponse<OrganisationUnit>>("/organisation/units"),
  trackedRequests: () =>
    apiRequest<ListResponse<TrackedRequest>>("/tracked-requests"),
  routingOptions: (workItemId: string) =>
    apiRequest<ListResponse<OrganisationUnit>>(
      `/work-items/${encodeURIComponent(workItemId)}/routing-options`,
    ),
  eligibleSpecialists: (workItemId: string) =>
    apiRequest<ListResponse<EligibleSpecialist>>(
      `/work-items/${encodeURIComponent(workItemId)}/eligible-specialists`,
    ),
  relatedRecords: (workItemId: string, query: string) => {
    const search = new URLSearchParams({ query, limit: "20" });
    return apiRequest<ListResponse<RelatedRecordCandidate>>(
      `/work-items/${encodeURIComponent(workItemId)}/related-records?${search.toString()}`,
    );
  },
  requestLinks: (workItemId: string) =>
    apiRequest<RequestLinkWorkspace>(
      `/work-items/${encodeURIComponent(workItemId)}/request-links`,
    ),
  createRequestLink: (
    workItemId: string,
    input: RequestLinkCreateInput,
    csrfToken: string,
  ) => apiRequest<RequestLinkWorkspace>(
    `/work-items/${encodeURIComponent(workItemId)}/request-links`,
    { body: input, csrfToken, method: "POST" },
  ),
  claimWorkItem: (id: string, csrfToken: string) =>
    apiRequest<WorkItem>(`/work-items/${encodeURIComponent(id)}/claim`, {
      csrfToken,
      method: "POST",
    }),
  completeWorkItem: (id: string, action: WorkAction, csrfToken: string) =>
    apiRequest<RequestDetail>(`/work-items/${encodeURIComponent(id)}/complete`, {
      body: action,
      csrfToken,
      method: "POST",
    }),
};
