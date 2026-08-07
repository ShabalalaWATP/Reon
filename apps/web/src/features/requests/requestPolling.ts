import type {
  ListResponse,
  RequestDetail,
  RequestSummary,
  WorkItem,
} from "../../lib/api/types";
import { isComplete } from "../../lib/status";

export const REQUESTER_POLL_INTERVAL_MS = 5_000;

export function requestListPollInterval(
  data: ListResponse<RequestSummary> | undefined,
) {
  return data?.items.some((request) => !isComplete(request.status))
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
