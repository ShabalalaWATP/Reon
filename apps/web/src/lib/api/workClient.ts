import type {
  EligibleSpecialist,
  CoordinationResult,
  ListResponse,
  OrganisationUnit,
  RelatedRecordSearchResult,
  RequestDetail,
  RequestLinkCreateInput,
  RequestLinkWorkspace,
  RoutingOptionsWorkspace,
  TrackedRequest,
  TrackedRequestDetail,
  TrackedRequestFilters,
  WorkAction,
  WorkItem,
} from "./types";
import { apiRequest, pagedPath } from "./transport";

export const workApi = {
  workItems: (cursor?: string, unitId?: string, requestId?: string) =>
    apiRequest<ListResponse<WorkItem>>(
      pagedPath("/work-items", cursor, {
        ...(unitId ? { unitId } : {}),
        ...(requestId ? { requestId } : {}),
      }),
    ),
  organisationUnits: () => apiRequest<ListResponse<OrganisationUnit>>("/organisation/units"),
  trackedRequests: (cursor?: string, filters?: TrackedRequestFilters) =>
    apiRequest<ListResponse<TrackedRequest>>(
      pagedPath("/tracked-requests", cursor, {
        ...(filters?.search ? { search: filters.search } : {}),
        ...(filters?.status ? { status: filters.status } : {}),
        ...(filters?.currentOwner ? { currentOwner: filters.currentOwner } : {}),
        ...(filters?.routeUnitId ? { routeUnitId: filters.routeUnitId } : {}),
        ...(filters?.minimumAgeDays ? { minimumAgeDays: filters.minimumAgeDays } : {}),
      }),
    ),
  trackedRequest: (requestId: string, eventCursor?: string) =>
    apiRequest<TrackedRequestDetail>(
      pagedPath(
        `/tracked-requests/${encodeURIComponent(requestId)}`,
        undefined,
        eventCursor ? { eventCursor } : {},
      ),
    ),
  postRequestCoordination: (
    requestId: string,
    input: {
      audience: "CUSTOMER" | "CURRENT_OWNER";
      body: string;
      clientMutationId: string;
    },
    csrfToken: string,
  ) =>
    apiRequest<CoordinationResult>(`/requests/${encodeURIComponent(requestId)}/coordination`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
  requestOwnershipReturn: (
    requestId: string,
    input: { targetUnitId: string; reason: string },
    csrfToken: string,
  ) =>
    apiRequest<CoordinationResult>(`/requests/${encodeURIComponent(requestId)}/return-requests`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
  routingOptions: (workItemId: string) =>
    apiRequest<RoutingOptionsWorkspace>(
      `/work-items/${encodeURIComponent(workItemId)}/routing-options`,
    ),
  eligibleSpecialists: (workItemId: string) =>
    apiRequest<ListResponse<EligibleSpecialist>>(
      `/work-items/${encodeURIComponent(workItemId)}/eligible-specialists`,
    ),
  relatedRecords: (workItemId: string, query?: string) => {
    const search = new URLSearchParams({ limit: query ? "20" : "10" });
    if (query) search.set("query", query);
    return apiRequest<RelatedRecordSearchResult>(
      `/work-items/${encodeURIComponent(workItemId)}/related-records?${search.toString()}`,
    );
  },
  requestLinks: (workItemId: string) =>
    apiRequest<RequestLinkWorkspace>(`/work-items/${encodeURIComponent(workItemId)}/request-links`),
  createRequestLink: (workItemId: string, input: RequestLinkCreateInput, csrfToken: string) =>
    apiRequest<RequestLinkWorkspace>(
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
