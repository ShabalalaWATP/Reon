const API_ROOT = "/api/v1";
export const SESSION_EXPIRED_EVENT = "istari:session-expired";

export function pagedPath(
  path: string,
  cursor?: string,
  values: Record<string, string> = {},
) {
  const parameters = cursor ? { ...values, cursor } : values;
  const query = Object.entries(parameters)
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(value)}`,
    )
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

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
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
