import type {
  CategoryCount,
  ChildUnitComparison,
  DailyThroughput,
  StageDuration,
} from "../../lib/api/statisticsTypes";

export function CategoryPanel({
  rows,
  title,
}: {
  rows: CategoryCount[];
  title: string;
}) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return (
    <section className="statistics-panel">
      <header><h2>{title}</h2><span>{total} total</span></header>
      {rows.length === 0 ? <p className="inline-empty">No records in this period.</p> : (
        <>
          <div className="category-visual">
            <div aria-hidden="true" className="donut-chart" style={{ background: donutBackground(rows, total) }}><span><strong>{total}</strong><small>requests</small></span></div>
            <ul className="donut-legend">
              {rows.map((row, index) => <li key={row.key}><i aria-hidden="true" style={{ background: sliceColour(index) }} /><span>{row.label}</span><strong>{row.count}</strong></li>)}
            </ul>
          </div>
          <DataTable
            caption={`${title} data`}
            headers={["Category", "Requests"]}
            rows={rows.map((row) => [row.label, row.count])}
          />
        </>
      )}
    </section>
  );
}

export function ThroughputPanel({
  rows,
  resolution,
}: {
  rows: DailyThroughput[];
  resolution: "DAILY" | "WEEKLY" | "MONTHLY";
}) {
  const maximum = Math.max(1, ...rows.flatMap((row) => [row.received, row.completed]));
  return (
    <section className="statistics-panel statistics-panel--wide">
      <header><h2>{resolutionLabel(resolution)} throughput</h2><span>Received and completed</span></header>
      <div aria-hidden="true" className="throughput-chart">
        {rows.map((row) => (
          <div className="throughput-chart__day" key={row.date} title={row.date}>
            <i className="throughput-chart__received" style={{ height: `${(row.received / maximum) * 100}%` }} />
            <i className="throughput-chart__completed" style={{ height: `${(row.completed / maximum) * 100}%` }} />
          </div>
        ))}
      </div>
      <p className="chart-legend"><i /> Received <i /> Completed</p>
      <DataTable
        caption="Daily throughput data"
        headers={["Date", "Received", "Completed"]}
        rows={rows.map((row) => [formatDate(row.date), row.received, row.completed])}
      />
    </section>
  );
}

export function DurationPanel({ rows }: { rows: StageDuration[] }) {
  const maximum = Math.max(1, ...rows.map((row) => row.p90Hours));
  return (
    <section className="statistics-panel statistics-panel--wide">
      <header><h2>Completed stage duration</h2><span>Median and 90th percentile</span></header>
      {rows.length === 0 ? <p className="inline-empty">No completed stages in this period.</p> : (
        <>
          <div aria-hidden="true" className="duration-range-chart">
            {rows.map((row) => <div key={row.key}><span>{row.label}</span><i><b style={{ width: `${(row.p90Hours / maximum) * 100}%` }} /><em style={{ left: `${(row.medianHours / maximum) * 100}%` }} /></i><strong>{row.medianHours} h</strong><small>{row.p90Hours} h</small></div>)}
          </div>
          <p className="duration-legend"><i /> Median <i /> 90th percentile</p>
          <DataTable
            caption="Completed stage duration data"
            headers={["Stage", "Intervals", "Median hours", "90th percentile hours"]}
            rows={rows.map((row) => [row.label, row.completedIntervals, row.medianHours, row.p90Hours])}
          />
        </>
      )}
    </section>
  );
}

export function ChildrenPanel({
  rows,
  onSelect,
}: {
  rows: ChildUnitComparison[];
  onSelect: (unitId: string) => void;
}) {
  const maximum = Math.max(1, ...rows.map((row) => row.received));
  if (rows.length === 0) return null;
  return (
    <section className="statistics-panel statistics-panel--wide">
      <header><h2>Direct child units</h2><span>Demand within this scope</span></header>
      <div className="child-comparison">
        {rows.map((row) => (
          <button
            aria-label={`View ${row.name} statistics`}
            key={row.unitId}
            onClick={() => onSelect(row.unitId)}
            type="button"
          >
            <span>{row.name}</span>
            <div><i style={{ width: `${(row.received / maximum) * 100}%` }} /></div>
            <strong>{row.received}</strong>
          </button>
        ))}
      </div>
      <DataTable
        caption="Direct child unit comparison data"
        headers={["Unit", "Received", "Active", "Completed", "Overdue", "Average rating"]}
        rows={rows.map((row) => [
          row.name,
          row.received,
          row.active,
          row.completed,
          row.overdue,
          row.ratingSuppressed ? "Suppressed" : row.averageRating ?? "No feedback",
        ])}
      />
    </section>
  );
}

function DataTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: Array<Array<string | number>>;
}) {
  return (
    <details className="statistics-data-disclosure">
      <summary>View data</summary>
      <div className="statistics-table-wrap">
        <table className="statistics-table">
          <caption>{caption}</caption>
          <thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${caption}-${rowIndex}`}>
                {row.map((cell, cellIndex) => cellIndex === 0
                  ? <th key={cellIndex} scope="row">{cell}</th>
                  : <td key={cellIndex}>{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function resolutionLabel(value: "DAILY" | "WEEKLY" | "MONTHLY") {
  return { DAILY: "Daily", WEEKLY: "Weekly", MONTHLY: "Monthly" }[value];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

const sliceColours = [
  "var(--accent)",
  "var(--teal)",
  "var(--warning)",
  "var(--critical)",
  "var(--border-strong)",
  "var(--accent-strong)",
];

function sliceColour(index: number) {
  return sliceColours[index % sliceColours.length];
}

function donutBackground(rows: CategoryCount[], total: number) {
  if (total === 0) return "var(--surface-strong)";
  let offset = 0;
  const segments = rows.map((row, index) => {
    const start = offset;
    offset += (row.count / total) * 100;
    return `${sliceColour(index)} ${start}% ${offset}%`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}
