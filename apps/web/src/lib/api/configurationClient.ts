import { apiRequest } from "./client";
import type {
  ConfigurationDraftInput,
  ConfigurationPreview,
  ConfigurationSnapshot,
  ConfigurationVersion,
  ConfigurationVersionSummary,
  WorkflowDefinition,
} from "./configurationTypes";

const root = "/admin/configuration";
const versionPath = (versionId: string) => `${root}/versions/${encodeURIComponent(versionId)}`;
type ReviewInput = { expectedVersion: number; reason: string };

export const configurationApi = {
  versions: () => apiRequest<{ items: ConfigurationVersionSummary[] }>(`${root}/versions`),
  create: (input: ConfigurationDraftInput, csrfToken: string) =>
    apiRequest<ConfigurationVersion>(`${root}/versions`, { body: input, csrfToken, method: "POST" }),
  version: (versionId: string) => apiRequest<ConfigurationVersion>(versionPath(versionId)),
  replace: (
    versionId: string,
    input: ConfigurationDraftInput & { expectedVersion: number },
    csrfToken: string,
  ) => apiRequest<ConfigurationVersion>(versionPath(versionId), { body: input, csrfToken, method: "PUT" }),
  preview: (versionId: string) => apiRequest<ConfigurationPreview>(`${versionPath(versionId)}/preview`),
  validate: (versionId: string, input: { expectedVersion: number }, csrfToken: string) =>
    configurationAction(versionId, "validate", input, csrfToken),
  submit: (versionId: string, input: ReviewInput, csrfToken: string) =>
    configurationAction(versionId, "submit", input, csrfToken),
  approve: (versionId: string, input: ReviewInput, csrfToken: string) =>
    configurationAction(versionId, "approve", input, csrfToken),
  reject: (versionId: string, input: ReviewInput, csrfToken: string) =>
    configurationAction(versionId, "reject", input, csrfToken),
  activate: (versionId: string, input: ReviewInput, csrfToken: string) =>
    configurationAction(versionId, "activate", input, csrfToken),
  active: () => apiRequest<ConfigurationVersion>(`${root}/active`),
  organisation: (versionId: string, at?: string) => apiRequest<ConfigurationSnapshot>(
    `${versionPath(versionId)}/organisation${at ? `?at=${encodeURIComponent(at)}` : ""}`,
  ),
  workflowDefinitions: () => apiRequest<{ items: WorkflowDefinition[] }>(`${root}/workflow-definitions`),
};

function configurationAction<T extends { expectedVersion: number }>(
  versionId: string,
  action: string,
  input: T,
  csrfToken: string,
) {
  return apiRequest<ConfigurationVersion>(`${versionPath(versionId)}/${action}`, {
    body: input,
    csrfToken,
    method: "POST",
  });
}
