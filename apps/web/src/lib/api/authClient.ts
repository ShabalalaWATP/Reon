import type { PersonalProfile, PersonalProfileUpdate, Session } from "./types";
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
  profile: () => apiRequest<PersonalProfile>("/profile"),
  updateProfile: (input: PersonalProfileUpdate, csrfToken: string) =>
    apiRequest<PersonalProfile>("/profile", {
      body: input,
      csrfToken,
      method: "PATCH",
    }),
  logout: (csrfToken: string) =>
    apiRequest<void>("/auth/logout", { csrfToken, method: "POST" }),
};
