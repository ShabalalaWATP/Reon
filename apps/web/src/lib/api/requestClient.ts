import type {
  Feedback,
  FeedbackInput,
  ListResponse,
  RequestCreateInput,
  RequestCancelInput,
  RequestDetail,
  RequestDraft,
  RequestDraftInput,
  RequestDraftSubmitInput,
  RequestDraftUpdateInput,
  RequestSummary,
} from "./types";
import { parseRequestDetail } from "./payloadSchemas";
import { apiRequest, pagedPath } from "./transport";

export const requestApi = {
  requests: (cursor?: string) =>
    apiRequest<ListResponse<RequestSummary>>(pagedPath("/requests", cursor)),
  drafts: (cursor?: string) =>
    apiRequest<ListResponse<RequestDraft>>(pagedPath("/request-drafts", cursor)),
  draft: (id: string) => apiRequest<RequestDraft>(`/request-drafts/${encodeURIComponent(id)}`),
  createDraft: (input: RequestDraftInput, csrfToken: string) =>
    apiRequest<RequestDraft>("/request-drafts", { body: input, csrfToken, method: "POST" }),
  updateDraft: (id: string, input: RequestDraftUpdateInput, csrfToken: string) =>
    apiRequest<RequestDraft>(`/request-drafts/${encodeURIComponent(id)}`, {
      body: input,
      csrfToken,
      method: "PATCH",
    }),
  deleteDraft: (id: string, expectedVersion: number, csrfToken: string) =>
    apiRequest<void>(
      `/request-drafts/${encodeURIComponent(id)}?expectedVersion=${expectedVersion}`,
      { csrfToken, method: "DELETE" },
    ),
  submitDraft: (id: string, input: RequestDraftSubmitInput, csrfToken: string) =>
    apiRequest<RequestDetail>(`/request-drafts/${encodeURIComponent(id)}/submit`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
  request: (id: string, eventCursor?: string) =>
    apiRequest<RequestDetail>(
      pagedPath(
        `/requests/${encodeURIComponent(id)}`,
        undefined,
        eventCursor ? { eventCursor } : {},
      ),
      { parse: parseRequestDetail },
    ),
  createRequest: (input: RequestCreateInput, csrfToken: string) =>
    apiRequest<RequestDetail>("/requests", { body: input, csrfToken, method: "POST" }),
  feedback: (id: string, input: FeedbackInput, csrfToken: string) =>
    apiRequest<Feedback>(`/requests/${encodeURIComponent(id)}/feedback`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
  cancelRequest: (id: string, input: RequestCancelInput, csrfToken: string) =>
    apiRequest<RequestDetail>(`/requests/${encodeURIComponent(id)}/cancel`, {
      body: input,
      csrfToken,
      method: "POST",
    }),
};
