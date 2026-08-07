import { apiRequest } from "./client";
import type {
  StatisticsEvolution,
  StatisticsEvolutionFilters,
  StatisticsExportResult,
} from "./statisticsEvolutionTypes";

export const statisticsEvolutionApi = {
  dashboard: (input: StatisticsEvolutionFilters) => {
    const query = new URLSearchParams(input);
    return apiRequest<StatisticsEvolution>(`/statistics/evolution?${query.toString()}`);
  },
  requestExport: (
    input: StatisticsEvolutionFilters & { format: "CSV" | "PDF" },
    csrfToken: string,
  ) => apiRequest<StatisticsExportResult>("/statistics/exports", {
    body: input,
    csrfToken,
    method: "POST",
  }),
};
