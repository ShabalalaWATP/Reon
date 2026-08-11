import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  StatisticsDashboard,
  SummaryMetric,
} from "../../lib/api/statisticsTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { StatisticsEvolutionContainer } from "./StatisticsEvolutionContainer";
import { StatisticsHierarchy } from "./StatisticsHierarchy";
import {
  CategoryPanel,
  ChildrenPanel,
  DurationPanel,
  ThroughputPanel,
} from "./StatisticsVisuals";

const defaultTo = localDateInputValue(new Date());
const defaultFrom = localDateInputValue(addLocalDays(new Date(), -29));
const datePresets = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "1 year" },
] as const;

export function StatisticsPage() {
  const { session } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const userId = session!.user.id;
  const [scopeId, setScopeId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(defaultTo);
  const [timeZone, setTimeZone] = useState("Europe/London");
  const scopes = useQuery({
    queryKey: protectedQueryKeys.statisticsScopes(userId),
    queryFn: api.statisticsScopes,
    enabled: true,
  });
  useEffect(() => {
    if (!scopeId && scopes.data?.items[0]) {
      const requestedScope = scopes.data.items.find((scope) => scope.id === searchParams.get("scopeId"));
      const initialScope = requestedScope ?? scopes.data.items[0];
      const requestedUnit = searchParams.get("unitId");
      setScopeId(initialScope.id);
      setUnitId(initialScope.units.some((unit) => unit.id === requestedUnit) ? requestedUnit! : initialScope.unitId);
    }
  }, [scopeId, scopes.data, searchParams]);
  const selectedScope = scopes.data?.items.find((scope) => scope.id === scopeId);
  const dashboard = useQuery({
    queryKey: protectedQueryKeys.statistics(userId, scopeId, unitId, from, to, timeZone),
    queryFn: () => api.statistics({ scopeId, unitId, from, to, timeZone }),
    enabled: Boolean(scopeId && unitId && from && to && from <= to),
  });
  const selectUnit = (nextUnitId: string) => {
    setUnitId(nextUnitId);
    setSearchParams({ scopeId, unitId: nextUnitId }, { replace: true });
  };

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
          <label className="form-field">Reporting root
            <select onChange={(event) => {
              const nextScope = scopes.data.items.find((scope) => scope.id === event.target.value)!;
              setScopeId(nextScope.id);
              setUnitId(nextScope.unitId);
              setSearchParams({ scopeId: nextScope.id, unitId: nextScope.unitId }, { replace: true });
            }} value={scopeId}>
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
      {selectedScope && unitId ? (
        <StatisticsHierarchy
          breadcrumb={dashboard.data?.breadcrumb ?? selectedScope.units.slice(0, 1)}
          onSelect={selectUnit}
          scope={selectedScope}
          selectedUnitId={unitId}
        />
      ) : null}
      <div aria-label="Statistics date presets" className="statistics-presets" role="group">
        {datePresets.map((preset) => (
          <button
            className={daysBetween(from, to) === preset.days ? "is-active" : ""}
            key={preset.days}
            onClick={() => setFrom(localDateInputValue(addLocalDays(new Date(`${to}T12:00:00`), 1 - preset.days)))}
            type="button"
          >{preset.label}</button>
        ))}
      </div>
      {from > to ? <p className="form-banner form-banner--error" role="alert">The start date must not be after the end date.</p> : null}
      {dashboard.isPending ? <PageState kind="loading" title="Calculating operational statistics" /> : null}
      {dashboard.isError ? <RetryState onRetry={() => void dashboard.refetch()} /> : null}
      {dashboard.data ? <Dashboard data={dashboard.data} onSelectUnit={selectUnit} /> : null}
      {dashboard.data ? (
        <StatisticsEvolutionContainer
          filters={{ scopeId, unitId, from, to, timeZone }}
          session={session!}
        />
      ) : null}
    </main>
  );
}

function Dashboard({
  data,
  onSelectUnit,
}: {
  data: StatisticsDashboard;
  onSelectUnit: (unitId: string) => void;
}) {
  return (
    <>
      <section aria-label="Projection status" className={`statistics-freshness statistics-freshness--${data.freshness.health.toLowerCase()}`}>
        <strong>{data.freshness.health === "READY" ? "Projection current" : "Projection degraded"}</strong>
        <span>As at {formatTimestamp(data.freshness.lastProjectedAt)} · {data.freshness.projectedRequestCount} projected requests</span>
      </section>
      <section aria-label="Summary measures" className="metric-band">
        {headlineMetrics(data).map((metric) => <Metric key={metric.key} metric={metric} />)}
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
        <dl>{data.definitions.map((item) => <div key={item.key}><dt>{item.label}</dt><dd>{item.description}</dd></div>)}</dl>
      </details>
    </>
  );
}

function headlineMetrics(data: StatisticsDashboard) {
  const leadership = ["received", "active", "completed", "overdue", "released", "clarifications", "feedback"];
  const delivery = ["received", "active", "overdue", "completed", "rework", "released", "feedback"];
  const keys = data.selectedUnit.kind === "TEAM" || data.selectedUnit.kind === "OPS_GROUP" ? delivery : leadership;
  return keys.flatMap((key) => data.summary.find((metric) => metric.key === key) ?? []);
}

function daysBetween(from: string, to: string) {
  return Math.round((new Date(`${to}T12:00:00`).getTime() - new Date(`${from}T12:00:00`).getTime()) / 86_400_000) + 1;
}

function Metric({ metric }: { metric: SummaryMetric }) {
  return (
    <div>
      <span>{metric.label}</span>
      <strong>{metric.value === null ? "Not available" : metric.value.toLocaleString("en-GB")}</strong>
    </div>
  );
}

function RetryState({ onRetry }: { onRetry: () => void }) {
  return <PageState action={<button className="button" onClick={onRetry}>Try again</button>} kind="error" title="Statistics could not be loaded">Check your connection and reporting access, then try again.</PageState>;
}

function formatTimestamp(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "not yet projected";
}
