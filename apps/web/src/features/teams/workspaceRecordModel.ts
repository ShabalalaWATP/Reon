import { ApiError } from "../../lib/api/client";

export function workspaceRecordErrorText(error: Error | null) {
  if (error instanceof ApiError) return error.message;
  return "The noticeboard change could not be saved. Refresh and try again.";
}
