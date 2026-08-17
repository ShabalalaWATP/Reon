import type { AccountContext, PersonalProfile, PersonalProfileUpdate, Session } from "./types";
import { apiRequest } from "./transport";
import { requireCompatibleSession } from "../auth/sessionCompatibility";

export const authApi = {
  requestAccount: (input: { displayName: string; contactEmail: string; reason: string }) =>
    apiRequest<{ status: "pending" }>("/auth/account-requests", {
      body: input,
      method: "POST",
    }),
  login: (credentials: { username: string; password: string }) =>
    sessionRequest("/auth/login", { body: credentials, method: "POST" }),
  elevate: (password: string, csrfToken: string) =>
    apiRequest<{ elevatedUntil: string; csrfToken: string }>("/auth/elevate", {
      body: { password },
      csrfToken,
      method: "POST",
    }),
  session: () => sessionRequest("/auth/me"),
  switchContext: (context: AccountContext, csrfToken: string) =>
    sessionRequest("/auth/switch-context", {
      body: { context },
      csrfToken,
      method: "POST",
    }),
  activity: (csrfToken: string) =>
    apiRequest<void>("/auth/activity", { csrfToken, method: "POST" }),
  profile: () => apiRequest<PersonalProfile>("/profile"),
  updateProfile: (input: PersonalProfileUpdate, csrfToken: string) =>
    apiRequest<PersonalProfile>("/profile", {
      body: input,
      csrfToken,
      method: "PATCH",
    }),
  logout: (csrfToken: string) => apiRequest<void>("/auth/logout", { csrfToken, method: "POST" }),
};

async function sessionRequest(
  path: string,
  options?: Parameters<typeof apiRequest<unknown>>[1],
): Promise<Session> {
  return requireCompatibleSession(await apiRequest<unknown>(path, options));
}
