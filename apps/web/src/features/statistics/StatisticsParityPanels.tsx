import type {
  BottleneckMeasure,
  CapacityMeasure,
  IterationMeasure,
  NotificationMeasure,
  PeriodComparison,
  ProjectionPeriod,
  ReleaseMeasure,
  StatisticsEvolution,
  StatisticsUnit,
} from "../../lib/api/statisticsEvolutionTypes";

type DisplayRow = {
  key: string;
  label: string;
  magnitude: number;
  chartValue: string | number;
  suppressed: boolean;
  values: Array<string | number>;
};

export function ComparisonPanel({ context, rows }: { context: string; rows: PeriodComparison[] }) {
  const display = rows.map((row) => ({
    key: row.key,
    label: row.label,
    magnitude: row.current ?? 0,
    chartValue: metric(row.current, row.unit, row.suppressed),
    suppressed: row.suppressed,
    values: [metric(row.current, row.unit, row.suppressed), metric(row.previous, row.unit, row.suppressed), change(row)],
  }));
  return <ParityPanel context={context} headers={["Measure", "Current", "Previous", "Change"]} rows={display} summary={comparisonSummary(rows)} title="Period comparison" />;
}

export function BottleneckPanel({ context, rows }: { context: string; rows: BottleneckMeasure[] }) {
  const display = rows.map((row) => ({
    key: row.key,
    label: row.label,
    magnitude: row.p90AgeHours ?? 0,
    chartValue: row.p90AgeHours === null ? "Not available" : `${row.p90AgeHours} h`,
    suppressed: row.suppressed,
    values: [masked(row.activeCount, row.suppressed), masked(row.medianAgeHours === null ? null : `${row.medianAgeHours} h`, row.suppressed), masked(row.p90AgeHours === null ? null : `${row.p90AgeHours} h`, row.suppressed), masked(row.overdueCount, row.suppressed)],
  }));
  return <ParityPanel context={context} headers={["Stage", "Active", "Median age", "90th percentile", "Overdue"]} rows={display} summary={bottleneckSummary(rows)} title="Stage bottlenecks" />;
}

export function CapacityTrendPanel({ context, rows }: { context: string; rows: CapacityMeasure[] }) {
  const display = rows.map((row) => ({
    key: row.date,
    label: formatDate(row.date),
    magnitude: row.projectedDemandMinutes,
    chartValue: hours(row.projectedDemandMinutes),
    suppressed: false,
    values: [hours(row.availableMinutes), hours(row.reservedMinutes), hours(row.activeWorkMinutes), hours(row.projectedDemandMinutes), row.estimate ? "Estimate" : "Observed"],
  }));
  return <ParityPanel context={context} headers={["Date", "Available", "Reserved", "Active work", "Demand", "Basis"]} rows={display} summary={capacitySummary(rows)} title="Capacity and demand" wide />;
}

export function ReleasePanel({ context, rows }: { context: string; rows: ReleaseMeasure[] }) {
  const display = rows.map((row) => ({
    key: row.key,
    label: row.label,
    magnitude: row.count ?? 0,
    chartValue: row.count ?? "Not available",
    suppressed: row.suppressed,
    values: [masked(row.count, row.suppressed), masked(row.medianHours === null ? "Not available" : `${row.medianHours} h`, row.suppressed)],
  }));
  return <ParityPanel context={context} headers={["Release measure", "Count", "Median cycle"]} rows={display} summary={highestSummary(rows, "release events")} title="Release cycle" />;
}

export function NotificationPanel({ context, rows }: { context: string; rows: NotificationMeasure[] }) {
  const display = rows.map((row) => ({
    key: row.key,
    label: row.label,
    magnitude: row.unresolvedCount ?? 0,
    chartValue: row.unresolvedCount ?? "Not available",
    suppressed: row.suppressed,
    values: [masked(row.count, row.suppressed), masked(row.medianResponseHours === null ? "Not available" : `${row.medianResponseHours} h`, row.suppressed), masked(row.unresolvedCount, row.suppressed)],
  }));
  return <ParityPanel context={context} headers={["Notification group", "Created", "Median response", "Unresolved"]} rows={display} summary={notificationSummary(rows)} title="Notification response" />;
}

export function IterationPanel({ context, rows }: { context: string; rows: IterationMeasure[] }) {
  const display = rows.map((row) => ({
    key: row.key,
    label: row.label,
    magnitude: row.completionPercentage ?? 0,
    chartValue: row.completionPercentage === null ? "Not available" : `${row.completionPercentage}%`,
    suppressed: row.suppressed,
    values: [masked(row.committedCount, row.suppressed), masked(row.completedCount, row.suppressed), masked(row.completionPercentage === null ? "Not available" : `${row.completionPercentage}%`, row.suppressed)],
  }));
  return <ParityPanel context={context} headers={["Iteration", "Committed", "Completed", "Completion"]} rows={display} summary={highestSummary(rows, "completed commitments")} title="Iteration commitments" />;
}

export function ProjectionPanel({ context, projection }: { context: string; projection: StatisticsEvolution["projection"] }) {
  const display = projection.periods.map((row) => ({
    key: row.date,
    label: formatDate(row.date),
    magnitude: row.demandCount,
    chartValue: row.demandCount,
    suppressed: false,
    values: [row.demandCount, row.capacityCount, row.demandCount - row.capacityCount],
  }));
  return <ParityPanel context={context} headers={["Period", "Estimated demand", "Estimated capacity", "Gap"]} rows={display} summary={projectionSummary(projection.periods, projection.label)} title="Demand projection" wide />;
}

function ParityPanel({
  context,
  headers,
  rows,
  summary,
  title,
  wide = false,
}: {
  context: string;
  headers: string[];
  rows: DisplayRow[];
  summary: string;
  title: string;
  wide?: boolean;
}) {
  const maximum = Math.max(1, ...rows.filter((row) => !row.suppressed).map((row) => row.magnitude));
  return (
    <section className={wide ? "statistics-parity statistics-parity--wide" : "statistics-parity"}>
      <header><h3>{title}</h3><small>{context}</small></header>
      <p className="statistics-text-summary">{summary}</p>
      {rows.length === 0 ? <p className="inline-empty">No aggregate records in this period.</p> : (
        <>
          <div aria-hidden="true" className="statistics-parity-chart">{rows.map((row) => <div key={row.key}><span>{row.label}</span><i><b style={{ width: `${row.suppressed ? 0 : (row.magnitude / maximum) * 100}%` }} /></i><strong>{row.suppressed ? "Suppressed" : row.chartValue}</strong></div>)}</div>
          <div className="statistics-table-wrap"><table className="statistics-table"><caption>{title} data</caption><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.key}><th scope="row">{row.label}</th>{row.values.map((value, index) => <td key={`${row.key}-${index}`}>{row.suppressed ? "Suppressed" : value}</td>)}</tr>)}</tbody></table></div>
        </>
      )}
    </section>
  );
}

function comparisonSummary(rows: PeriodComparison[]) {
  const usable = rows.filter((row) => !row.suppressed && row.change !== null);
  if (usable.length === 0) return "No unsuppressed period comparison is available.";
  const largest = usable.reduce((left, right) => Math.abs(right.change as number) > Math.abs(left.change as number) ? right : left);
  return `${largest.label} has the largest absolute change at ${change(largest)} versus the previous period.`;
}

function bottleneckSummary(rows: BottleneckMeasure[]) {
  const usable = rows.filter(
    (row): row is BottleneckMeasure & { p90AgeHours: number } =>
      !row.suppressed && row.p90AgeHours !== null,
  );
  if (usable.length === 0) return "No unsuppressed bottleneck measure is available.";
  const slowest = usable.reduce((left, right) => right.p90AgeHours > left.p90AgeHours ? right : left);
  return `${slowest.label} has the longest 90th-percentile active age at ${slowest.p90AgeHours} hours.`;
}

function capacitySummary(rows: CapacityMeasure[]) {
  if (rows.length === 0) return "No capacity trend is available.";
  const totalDemand = rows.reduce((sum, row) => sum + row.projectedDemandMinutes, 0);
  const totalAvailable = rows.reduce((sum, row) => sum + row.availableMinutes, 0);
  return `The selected period shows ${hours(totalDemand)} estimated demand against ${hours(totalAvailable)} available capacity.`;
}

function notificationSummary(rows: NotificationMeasure[]) {
  const usable = rows.filter((row) => !row.suppressed);
  if (usable.length === 0) return "No unsuppressed notification response measure is available.";
  const unresolved = usable.reduce((sum, row) => sum + (row.unresolvedCount ?? 0), 0);
  return `${unresolved} unresolved actions remain across the visible notification groups.`;
}

function highestSummary(rows: Array<ReleaseMeasure | IterationMeasure>, noun: string) {
  const usable = rows.filter((row) => !row.suppressed);
  if (usable.length === 0) return `No unsuppressed ${noun} are available.`;
  return `${usable.length} aggregate ${noun} groups are visible for the selected scope.`;
}

function projectionSummary(rows: ProjectionPeriod[], label: string) {
  if (rows.length === 0) return `${label}. No projection periods are available.`;
  const gap = rows.reduce((sum, row) => sum + row.demandCount - row.capacityCount, 0);
  return `${label}. The aggregate estimated demand-to-capacity gap is ${gap}.`;
}

function metric(value: number | null, unit: StatisticsUnit, suppressed: boolean) {
  if (suppressed) return "Suppressed";
  if (value === null) return "Not available";
  if (unit === "percentage") return `${value}%`;
  if (unit === "hours") return `${value} h`;
  return value;
}

function change(row: PeriodComparison) {
  if (row.suppressed) return "Suppressed";
  if (row.change === null) return "Not available";
  const prefix = row.change > 0 ? "+" : "";
  return `${prefix}${metric(row.change, row.unit, false)}`;
}

function masked(value: string | number | null, suppressed: boolean) { return suppressed ? "Suppressed" : value ?? "Not available"; }
function hours(value: number) { return `${(value / 60).toFixed(1)} h`; }
function formatDate(value: string) { return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`)); }
