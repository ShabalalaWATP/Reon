import { apiRequest } from "./client";
import type {
  CapacityScenarioInput,
  CapacityScenarioPreview,
  CapacityScenarioSummary,
  PackageTemplate,
  PlanningCockpit,
} from "./planningEvolutionTypes";

const planningPath = (teamId: string) =>
  `/team-workspaces/${encodeURIComponent(teamId)}/planning`;

export const planningEvolutionApi = {
  cockpit: (teamId: string) =>
    apiRequest<PlanningCockpit>(`${planningPath(teamId)}/cockpit`),
  templates: (teamId: string) =>
    apiRequest<{ items: PackageTemplate[] }>(`${planningPath(teamId)}/templates`),
  scenarios: (teamId: string) =>
    apiRequest<{ items: CapacityScenarioSummary[] }>(`${planningPath(teamId)}/scenarios`),
  previewScenario: (
    teamId: string,
    input: CapacityScenarioInput,
    csrfToken: string,
  ) => apiRequest<CapacityScenarioPreview>(`${planningPath(teamId)}/scenarios/preview`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
};
