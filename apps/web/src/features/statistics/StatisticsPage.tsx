import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  StatisticsDashboard,
  SummaryMetric,
} from "../../lib/api/statisticsTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import {
  CategoryPanel,
  ChildrenPanel,
  DurationPanel,
  ThroughputPanel,
} from "./StatisticsVisuals";

const defaultTo = isoDate(new Date());
const startDate = new Date();
startDate.setUTCDate(startDate.getUTCDate() - 89);
const defaultFrom = isoDate(startDate);

export function StatisticsPage() {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const [scopeId, setScopeId] = useState("");
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(defaultTo);
  const [timeZone, setTimeZone] = useState("Europe/London");
  const scopes = useQuery({
    queryKey: protectedQueryKeys.statisticsScopes(userId),
    queryFn: api.statisticsScopes,
    enabled: Boolean(session),
  });
  useEffect(() => {
    if (!scopeId && scopes.data?.items[0]) setScopeId(scopes.data.items[0].id);
  }, [scopeId, scopes.data]);
  const dashboard = useQuery({
    queryKey: protectedQueryKeys.statistics(userId, scopeId, from, to, timeZone),
    queryFn: () => api.statistics({ scopeId, from, to, timeZone }),
    enabled: Boolean(session && scopeId && from && to && from <= to),
  });

  if (scopes.isPending) return <PageState kind="loading" title="Loading statistics access" />;
  if (scopes.isError) return <RetryState onRetry={() => void scopes.refetch()} />;
  if (scopes.data.items.length === 0) {
    return <PageState kind="empty" title="No statistics scope assigned">Ask an Administrator to grant an operational reporting scope.</PageState>;
  }

  return (
    <main className="page-stack statistics-page">
      <header className="statistics-heading">
        <div>
          <span>Operational performance</span>
          <h1>Statistics</h1>
          <p>Content-free measures for the organisation units you are authorised to oversee.</p>
        </div>
        <div className="statistics-filters" aria-label="Statistics filters">
          <label className="form-field">Scope
            <select onChange={(event) => setScopeId(event.target.value)} value={scopeId}>
              {scopes.data.items.map((scope) => <option key={scope.id} value={scope.id}>{scope.name}</option>)}
            </select>
          </label>
          <label className="form-field">From
            <input max={to} onChange={(event) => setFrom(event.target.value)} required type="date" value={from} />
          </label>
          <label className="form-field">To
            <input min={from} onChange={(event) => setTo(event.target.value)} required type="date" value={to} />
          </label>
          <label className="form-field">Time zone
            <select onChange={(event) => setTimeZone(event.target.value)} value={timeZone}>
              <option value="Europe/London">Europe/London</option>
              <option value="UTC">UTC</option>
            </select>
          </label>
        </div>
      </header>
      {from > to ? <p className="form-banner form-banner--error" role="alert">The start date must not be after the end date.</p> : null}
      {dashboard.isPending ? <PageState kind="loading" title="Calculating operational statistics" /> : null}
      {dashboard.isError ? <RetryState onRetry={() => void dashboard.refetch()} /> : null}
      {dashboard.data ? <Dashboard data={dashboard.data} /> : null}
    </main>
  );
}

function Dashboard({ data }: { data: StatisticsDashboard }) {
  return (
    <>
      <section aria-label="Projection status" className={`statistics-freshness statistics-freshness--${data.freshness.health.toLowerCase()}`}>
        <strong>{data.freshness.health === "READY" ? "Projection current" : "Projection degraded"}</strong>
        <span>As at {formatTimestamp(data.freshness.lastProjectedAt)} · {data.freshness.projectedRequestCount} projected requests</span>
      </section>
      <section aria-label="Summary measures" className="metric-band">
        {data.summary.map((metric) => <Metric key={metric.key} metric={metric} />)}
      </section>
      <div className="statistics-grid">
        <CategoryPanel rows={data.status} title="Current status" />
        <CategoryPanel rows={data.dueRisk} title="Due-date risk" />
        <CategoryPanel rows={data.age} title="Active request age" />
        <ChildrenPanel rows={data.children} />
        <ThroughputPanel rows={data.throughput} />
        <DurationPanel rows={data.stageDurations} />
      </div>
      <details className="statistics-definitions">
        <summary>Measure definitions</summary>
        <dl>{data.definitions.map((item) => <div key={item.key}><dt>{item.label}</dt><dd>{item.description}</dd></div>)}</dl>
      </details>
    </>
  );
}

function Metric({ metric }: { metric: SummaryMetric }) {
  return (
    <div>
      <span>{metric.label}</span>
      <strong>{metric.suppressed ? "Suppressed" : formatMetric(metric)}</strong>
    </div>
  );
}

function formatMetric(metric: SummaryMetric) {
  if (metric.value === null) return "Not available";
  if (metric.unit === "percentage") return `${metric.value}%`;
  if (metric.unit === "rating") return `${metric.value} / 5`;
  if (metric.unit === "hours") return `${metric.value} h`;
  return metric.value.toLocaleString("en-GB");
}

function RetryState({ onRetry }: { onRetry: () => void }) {
  return <PageState action={<button className="button" onClick={onRetry}>Try again</button>} kind="error" title="Statistics could not be loaded">Check your connection and reporting access, then try again.</PageState>;
}

function isoDate(value: Date) { return value.toISOString().slice(0, 10); }
function formatTimestamp(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "not yet projected";
}
