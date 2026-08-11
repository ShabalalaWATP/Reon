import { apiRequest } from "./transport";

export type PlatformClassification =
  | "OFFICIAL"
  | "OFFICIAL-SENSITIVE"
  | "SECRET"
  | "TOP-SECRET";

export type PlatformClassificationSetting = {
  classification: PlatformClassification;
  version: number;
  updatedAt: string;
};
export const platformSecurityApi = {
  classification: () =>
    apiRequest<PlatformClassificationSetting>("/platform/classification"),
  requestPasswordAssistance: (email: string) =>
    apiRequest<{ status: "accepted"; message: string }>("/auth/password-assistance", {
      body: { email },
      method: "POST",
    }),
  updateClassification: (
    classification: PlatformClassification,
    expectedVersion: number,
    csrfToken: string,
  ) => apiRequest<PlatformClassificationSetting>("/admin/platform/classification", {
    body: { classification, expectedVersion },
    csrfToken,
    method: "PATCH",
  }),
};
