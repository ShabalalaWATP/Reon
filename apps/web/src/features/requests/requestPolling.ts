import type { ListResponse, RequestDetail, RequestSummary, WorkItem } from "../../lib/api/types";
import { isComplete } from "../../lib/status";

const REQUESTER_POLL_INTERVAL_MS = 5_000;

export function requestListPollInterval(
  data: ListResponse<RequestSummary> | { pages: ListResponse<RequestSummary>[] } | undefined,
) {
  const pages = data && "pages" in data ? data.pages : data ? [data] : [];
  return pages.some((page) => page.items.some((request) => !isComplete(request.status)))
    ? REQUESTER_POLL_INTERVAL_MS
    : false;
}

export function requestDetailPollInterval(data: RequestDetail | undefined) {
  return data && !isComplete(data.status) ? REQUESTER_POLL_INTERVAL_MS : false;
}

export function clarificationTaskPollInterval(
  data: ListResponse<WorkItem> | undefined,
  requestId: string,
) {
  return data?.items.some((item) => item.requestId === requestId)
    ? false
    : REQUESTER_POLL_INTERVAL_MS;
}
