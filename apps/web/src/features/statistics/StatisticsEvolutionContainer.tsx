import { useQuery } from "@tanstack/react-query";

import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { statisticsEvolutionApi } from "../../lib/api/statisticsEvolutionClient";
import type { StatisticsEvolutionFilters } from "../../lib/api/statisticsEvolutionTypes";
import type { Session } from "../../lib/api/types";
import { StatisticsEvolutionView } from "./StatisticsEvolutionView";

export function StatisticsEvolutionContainer({
  filters,
  session,
}: {
  filters: StatisticsEvolutionFilters;
  session: Session;
}) {
  const query = useQuery({
    queryKey: protectedQueryKeys.statisticsEvolution(
      session.user.id,
      filters.scopeId,
      filters.from,
      filters.to,
      filters.timeZone,
    ),
    queryFn: () => statisticsEvolutionApi.dashboard(filters),
  });
  if (query.isPending) {
    return (
      <section aria-busy="true" className="statistics-evolution-state">
        <strong>Calculating enhanced measures</strong>
        <span>Comparisons, capacity and release facts are being reconciled.</span>
      </section>
    );
  }
  if (query.isError) {
    return (
      <section className="statistics-evolution-state" role="status">
        <strong>Enhanced measures unavailable</strong>
        <span>The established scoped statistics above remain current.</span>
        <button className="button" onClick={() => void query.refetch()} type="button">Try enhanced measures again</button>
      </section>
    );
  }
  return <StatisticsEvolutionView data={query.data} filters={filters} session={session} />;
}
