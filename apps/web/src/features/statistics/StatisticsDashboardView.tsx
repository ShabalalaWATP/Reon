import type { StatisticsDashboard, SummaryMetric } from "../../lib/api/statisticsTypes";
import { CategoryPanel, ChildrenPanel, DurationPanel, ThroughputPanel } from "./StatisticsVisuals";

export function StatisticsDashboardView({
  data,
  onSelectUnit,
}: {
  data: StatisticsDashboard;
  onSelectUnit: (unitId: string) => void;
}) {
  return (
    <>
      <section
        aria-label="Projection status"
        className={`statistics-freshness statistics-freshness--${data.freshness.health.toLowerCase()}`}
      >
        <strong>
          {data.freshness.health === "READY" ? "Projection current" : "Projection degraded"}
        </strong>
        <span>
          As at {formatTimestamp(data.freshness.lastProjectedAt)} ·{" "}
          {data.freshness.projectedRequestCount} projected requests
        </span>
      </section>
      <section aria-label="Summary measures" className="metric-band">
        {headlineMetrics(data).map((metric) => (
          <Metric key={metric.key} metric={metric} />
        ))}
      </section>
      <div className="statistics-grid">
        <CategoryPanel rows={data.status} title="Current status" />
        <CategoryPanel rows={data.dueRisk} title="Due-date risk" />
        <CategoryPanel rows={data.age} title="Active request age" />
        <ChildrenPanel onSelect={onSelectUnit} rows={data.children} />
        <ThroughputPanel resolution={data.throughputResolution} rows={data.throughput} />
        <DurationPanel rows={data.stageDurations} />
      </div>
      <details className="statistics-definitions">
        <summary>Measure definitions</summary>
        <dl>
          {data.definitions.map((item) => (
            <div key={item.key}>
              <dt>{item.label}</dt>
              <dd>{item.description}</dd>
            </div>
          ))}
        </dl>
      </details>
    </>
  );
}

function headlineMetrics(data: StatisticsDashboard) {
  const leadership = [
    "received",
    "active",
    "completed",
    "overdue",
    "released",
    "clarifications",
    "feedback",
  ];
  const delivery = ["received", "active", "overdue", "completed", "rework", "released", "feedback"];
  const keys =
    data.selectedUnit.kind === "TEAM" || data.selectedUnit.kind === "OPS_GROUP"
      ? delivery
      : leadership;
  return keys.flatMap((key) => data.summary.find((metric) => metric.key === key) ?? []);
}

function Metric({ metric }: { metric: SummaryMetric }) {
  return (
    <div>
      <span>{metric.label}</span>
      <strong>
        {metric.value === null ? "Not available" : metric.value.toLocaleString("en-GB")}
      </strong>
    </div>
  );
}

function formatTimestamp(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(value),
      )
    : "not yet projected";
}
