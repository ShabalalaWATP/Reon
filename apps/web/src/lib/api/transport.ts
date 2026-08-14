const API_ROOT = "/api/v1";
export const SESSION_EXPIRED_EVENT = "istari:session-expired";

export function pagedPath(path: string, cursor?: string, values: Record<string, string> = {}) {
  const parameters = cursor ? { ...values, cursor } : values;
  const query = Object.entries(parameters)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
  return query ? `${path}?${query}` : path;
}

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
  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: "include",
    headers: requestHeaders(options),
  });
  if (!response.ok) {
    notifyExpiredSession(path, response.status);
    throw await responseError(response);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function requestHeaders(options: RequestOptions) {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (options.csrfToken) headers.set("X-CSRF-Token", options.csrfToken);
  return headers;
}

function notifyExpiredSession(path: string, status: number) {
  if (status === 401 && !path.startsWith("/auth/")) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
}

type ErrorPayload = {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string };
};

async function responseError(response: Response) {
  const fallback = `Request failed with status ${response.status}.`;
  try {
    return apiErrorFromPayload((await response.json()) as ErrorPayload, response.status, fallback);
  } catch {
    return new ApiError(fallback, response.status);
  }
}

function apiErrorFromPayload(error: ErrorPayload, status: number, fallback: string) {
  if (typeof error.detail === "string") return new ApiError(error.detail, status);
  if (error.detail) {
    return new ApiError(error.detail.message ?? fallback, status, error.detail.code);
  }
  return new ApiError(error.message ?? fallback, status, error.code);
}
