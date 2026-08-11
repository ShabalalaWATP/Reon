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
  const context = `${data.selectedUnit.name} · ${data.range.fromDate} to ${data.range.toDate} · ${freshness(data)}`;
  const visible = {
    comparison: data.comparison.filter((row) => !row.suppressed),
    bottlenecks: data.bottlenecks.filter((row) => !row.suppressed),
    releases: data.releases.filter((row) => !row.suppressed),
    notifications: data.notifications.filter((row) => !row.suppressed),
    iterations: data.iterations.filter((row) => !row.suppressed),
  };
  const suppressedCount = data.comparison.filter((row) => row.suppressed).length
    + data.bottlenecks.filter((row) => row.suppressed).length
    + data.releases.filter((row) => row.suppressed).length
    + data.notifications.filter((row) => row.suppressed).length
    + data.iterations.filter((row) => row.suppressed).length;
  const detailCount = Object.values(visible).reduce((total, rows) => total + rows.length, 0)
    + data.capacity.length
    + data.projection.periods.length;
  return (
    <section className="statistics-evolution">
      <header className="statistics-evolution__heading">
        <div><span>Scoped operational evidence</span><h2>Planning and service flow</h2><p>Aggregate comparisons use the selected grant and contain no request content or individual ranking.</p></div>
        <small>{context}</small>
      </header>
      {suppressedCount > 0 ? <p className="statistics-privacy-note">{suppressedCount} detailed measure{suppressedCount === 1 ? " is" : "s are"} hidden because the selected cohort is too small.</p> : null}
      {detailCount > 0 ? (
        <div className="statistics-evolution-grid">
          {visible.comparison.length ? <ComparisonPanel context={context} rows={visible.comparison} /> : null}
          {visible.bottlenecks.length ? <BottleneckPanel context={context} rows={visible.bottlenecks} /> : null}
          {data.capacity.length ? <CapacityTrendPanel context={context} rows={data.capacity} /> : null}
          {visible.releases.length ? <ReleasePanel context={context} rows={visible.releases} /> : null}
          {visible.notifications.length ? <NotificationPanel context={context} rows={visible.notifications} /> : null}
          {visible.iterations.length ? <IterationPanel context={context} rows={visible.iterations} /> : null}
          {data.projection.periods.length ? <ProjectionPanel context={context} projection={data.projection} /> : null}
        </div>
      ) : <p className="inline-empty">No detailed operational measures are available for this scope and period.</p>}
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
