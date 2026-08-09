import type { StatisticsDashboard, StatisticsScopeList } from "./statisticsTypes";
import { apiRequest } from "./transport";

export const statisticsApi = {
  statisticsScopes: () =>
    apiRequest<StatisticsScopeList>("/statistics/scopes"),
  statistics: (input: {
    scopeId: string;
    from: string;
    to: string;
    timeZone: string;
  }) => {
    const query = new URLSearchParams(input);
    return apiRequest<StatisticsDashboard>(`/statistics?${query.toString()}`);
  },
};
