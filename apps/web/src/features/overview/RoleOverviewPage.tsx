import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { Link, Navigate } from "react-router";

import { PageState } from "../../components/PageState";
import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { StatisticsDashboard } from "../../lib/api/statisticsTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { roleLabels } from "../../lib/routes";

const today = localDateInputValue(new Date());
const monthStart = localDateInputValue(addLocalDays(new Date(), -29));
const emptyFilters = { sections: [], actionTypes: [], dueBefore: null, limit: 6 };

export function RoleOverviewPage() {
  const { session } = useAuth();
  const role = session!.user.role;
  if (role === "REQUESTER") return <Navigate replace to="/requests" />;
  if (role === "DELIVERY_SPECIALIST") return <Navigate replace to="/my-work" />;
  if (role === "DELIVERY_TEAM_LEAD") return <TeamOverviewRedirect />;
  if (role === "QUALITY_RELEASE") return <QualityOverview />;
  return <ScopedOverview administrator={role === "PLATFORM_ADMIN"} />;
}

function ScopedOverview({ administrator }: { administrator: boolean }) {
  const { session } = useAuth();
  const userId = session!.user.id;
  const scopes = useQuery({
    queryKey: protectedQueryKeys.statisticsScopes(userId),
    queryFn: api.statisticsScopes,
  });
  const actions = useQuery({
    queryKey: protectedQueryKeys.actions(userId, "overview"),
    queryFn: () => actionNotificationApi.actions(emptyFilters),
  });
  const scope = scopes.data?.items[0];
  const statistics = useQuery({
    queryKey: protectedQueryKeys.statistics(
      userId,
      scope?.id ?? "",
      scope?.unitId ?? "",
      monthStart,
      today,
      "Europe/London",
    ),
    queryFn: () => api.statistics({
      scopeId: scope!.id,
      unitId: scope!.unitId!,
      from: monthStart,
      to: today,
      timeZone: "Europe/London",
    }),
    enabled: Boolean(scope?.unitId),
  });
  if (scopes.isPending || actions.isPending || (Boolean(scope?.unitId) && statistics.isPending)) {
    return <PageState kind="loading" title="Opening your overview" />;
  }
  if (scopes.isError || actions.isError || statistics.isError || !scope?.unitId || !statistics.data) {
    return <PageState kind="error" title="Your overview could not be loaded">Refresh the page or ask an Administrator to review your reporting access.</PageState>;
  }
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading">
        <div><span>{administrator ? "Platform control" : roleLabels[session!.user.role]}</span><h1>{administrator ? "Administration overview" : `${scope.name} overview`}</h1><p>{administrator ? "Service health, access and aggregate demand in one operational view." : "Current demand, immediate actions and authorised organisation performance."}</p></div>
        <Link className="button" to="/my-work">Open My actions</Link>
      </header>
      <OverviewMeasures actions={actions.data} data={statistics.data} />
      <div className="overview-columns">
        <ChildRegister data={statistics.data} scopeId={scope.id} />
        <OverviewLinks administrator={administrator} />
      </div>
    </main>
  );
}

function OverviewMeasures({
  actions,
  data,
}: {
  actions: Awaited<ReturnType<typeof actionNotificationApi.actions>>;
  data: StatisticsDashboard;
}) {
  const metrics = new Map(data.summary.map((metric) => [metric.key, metric]));
  const values = [
    ["Needs your action", actions.counts.needsMyAction],
    ["Active demand", metrics.get("active")?.value ?? 0],
    ["Due within 7 days", data.dueRisk.find((row) => row.key === "due-1")?.count ?? 0],
    ["Overdue", metrics.get("overdue")?.value ?? 0],
    ["Completed in period", metrics.get("completed")?.value ?? 0],
  ] as const;
  return <section aria-label="Operational overview measures" className="overview-measures">{values.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>;
}

function ChildRegister({ data, scopeId }: { data: StatisticsDashboard; scopeId: string }) {
  return (
    <section className="overview-register">
      <header><span>Organisation view</span><h2>{data.children.length ? "Direct organisations" : "Selected scope"}</h2></header>
      {data.children.length ? data.children.map((child) => (
        <Link key={child.unitId} to={`/statistics?scopeId=${encodeURIComponent(scopeId)}&unitId=${encodeURIComponent(child.unitId)}`}>
          <span><strong>{child.name}</strong><small>{child.active} active · {child.overdue} overdue</small></span><b>{child.received}</b><ArrowUpRight aria-hidden="true" size={16} />
        </Link>
      )) : <p className="inline-empty">This is the lowest organisation level in your reporting scope.</p>}
      <Link className="overview-text-link" to={`/statistics?scopeId=${encodeURIComponent(scopeId)}&unitId=${encodeURIComponent(data.selectedUnit.id)}`}>Open full statistics <ArrowUpRight aria-hidden="true" size={14} /></Link>
    </section>
  );
}

function OverviewLinks({ administrator }: { administrator: boolean }) {
  const links = administrator
    ? [["User accounts", "/admin/users"], ["Configuration", "/admin/configuration"], ["Organisation", "/organisation"], ["Statistics", "/statistics"]]
    : [["My actions", "/my-work"], ["Tracking", "/tracking"], ["Organisation", "/organisation"], ["Statistics", "/statistics"]];
  return <nav aria-label="Overview destinations" className="overview-links"><span>Workspace links</span><h2>Continue working</h2>{links.map(([label, path]) => <Link key={path} to={path}>{label}<ArrowUpRight aria-hidden="true" size={15} /></Link>)}</nav>;
}

function QualityOverview() {
  const { session } = useAuth();
  const userId = session!.user.id;
  const actions = useQuery({ queryKey: protectedQueryKeys.actions(session!.user.id, "quality-overview"), queryFn: () => actionNotificationApi.actions(emptyFilters) });
  const scopes = useQuery({ queryKey: protectedQueryKeys.statisticsScopes(userId), queryFn: api.statisticsScopes });
  const scope = scopes.data?.items[0];
  const statistics = useQuery({
    queryKey: protectedQueryKeys.statistics(userId, scope?.id ?? "", scope?.unitId ?? "", monthStart, today, "Europe/London"),
    queryFn: () => api.statistics({ scopeId: scope!.id, unitId: scope!.unitId!, from: monthStart, to: today, timeZone: "Europe/London" }),
    enabled: Boolean(scope?.unitId),
  });
  if (actions.isPending || scopes.isPending || (Boolean(scope?.unitId) && statistics.isPending)) return <PageState kind="loading" title="Opening quality overview" />;
  if (actions.isError || scopes.isError || statistics.isError || !scope?.unitId || !statistics.data) return <PageState kind="error" title="Quality overview could not be loaded" />;
  const metrics = new Map(statistics.data.summary.map((metric) => [metric.key, metric.value]));
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading"><div><span>Quality and release</span><h1>Quality overview</h1><p>Products awaiting review, recent decisions and release actions.</p></div><Link className="button" to="/quality-release">Open QC queue</Link></header>
      <section aria-label="Quality work measures" className="overview-measures">
        <div><span>Needs your action</span><strong>{actions.data.counts.needsMyAction}</strong></div>
        <div><span>Due soon</span><strong>{actions.data.counts.dueSoon}</strong></div>
        <div><span>Products released</span><strong>{metrics.get("released") ?? 0}</strong></div>
        <div><span>Rework decisions</span><strong>{metrics.get("rework") ?? 0}</strong></div>
        <div><span>Feedback received</span><strong>{metrics.get("feedback") ?? 0}</strong></div>
      </section>
      <nav aria-label="Quality workspace links" className="overview-links overview-links--wide"><span>Workspace links</span><h2>Continue working</h2><Link to="/quality-release">QC queue<ArrowUpRight size={15} /></Link><Link to="/my-work">My actions<ArrowUpRight size={15} /></Link><Link to={`/statistics?scopeId=${encodeURIComponent(scope.id)}&unitId=${encodeURIComponent(scope.unitId)}`}>Quality statistics<ArrowUpRight size={15} /></Link><Link to="/organisation">Organisation<ArrowUpRight size={15} /></Link></nav>
    </main>
  );
}

function TeamOverviewRedirect() {
  const { session } = useAuth();
  const workspaces = useQuery({ queryKey: protectedQueryKeys.teamWorkspaces(session!.user.id), queryFn: api.teamWorkspaces });
  if (workspaces.isPending) return <PageState kind="loading" title="Opening team overview" />;
  const team = workspaces.data?.items[0];
  return team ? <Navigate replace to={`/teams/${team.teamId}/overview`} /> : <PageState kind="empty" title="No team overview assigned" />;
}
