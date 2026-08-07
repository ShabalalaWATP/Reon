import type { StatisticsEvolutionFilters } from "../../lib/api/statisticsEvolutionTypes";
import type { Session } from "../../lib/api/types";
import { StatisticsExportPanel } from "./StatisticsExportPanel";
import {
  BottleneckPanel,
  CapacityTrendPanel,
  ComparisonPanel,
  IterationPanel,
  NotificationPanel,
  ProjectionPanel,
  ReleasePanel,
} from "./StatisticsParityPanels";
import type { StatisticsEvolution } from "../../lib/api/statisticsEvolutionTypes";

export function StatisticsEvolutionView({
  data,
  filters,
  session,
}: {
  data: StatisticsEvolution;
  filters: StatisticsEvolutionFilters;
  session: Session;
}) {
  const context = `${data.scope.name} · ${data.range.fromDate} to ${data.range.toDate} · ${freshness(data)}`;
  return (
    <section className="statistics-evolution">
      <header className="statistics-evolution__heading">
        <div><span>Scoped operational evidence</span><h2>Planning and service flow</h2><p>Aggregate comparisons use the selected grant and contain no request content or individual ranking.</p></div>
        <small>{context}</small>
      </header>
      <div className="statistics-evolution-grid">
        <ComparisonPanel context={context} rows={data.comparison} />
        <BottleneckPanel context={context} rows={data.bottlenecks} />
        <CapacityTrendPanel context={context} rows={data.capacity} />
        <ReleasePanel context={context} rows={data.releases} />
        <NotificationPanel context={context} rows={data.notifications} />
        <IterationPanel context={context} rows={data.iterations} />
        <ProjectionPanel context={context} projection={data.projection} />
      </div>
      <StatisticsExportPanel
        filters={filters}
        policies={data.exports}
        session={session}
      />
    </section>
  );
}

function freshness(data: StatisticsEvolution) {
  if (!data.freshness.lastProjectedAt) return "not yet projected";
  const formatted = new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(data.freshness.lastProjectedAt));
  return `${data.freshness.health.toLowerCase()} as at ${formatted}`;
}
