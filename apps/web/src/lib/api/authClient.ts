import type { Session } from "./types";
import { apiRequest } from "./transport";

export const authApi = {
  requestAccount: (input: { displayName: string; contactEmail: string; reason: string }) =>
    apiRequest<{ status: "pending" }>("/auth/account-requests", {
      body: input,
      method: "POST",
    }),
  login: (credentials: { username: string; password: string }) =>
    apiRequest<Session>("/auth/login", { body: credentials, method: "POST" }),
  elevate: (password: string, csrfToken: string) =>
    apiRequest<{ elevatedUntil: string }>("/auth/elevate", {
      body: { password },
      csrfToken,
      method: "POST",
    }),
  session: () => apiRequest<Session>("/auth/me"),
  logout: (csrfToken: string) =>
    apiRequest<void>("/auth/logout", { csrfToken, method: "POST" }),
};
