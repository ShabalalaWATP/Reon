import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Building2,
  ClipboardList,
  ListChecks,
  Network,
  Settings,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { Link, Navigate } from "react-router";

import { PageState } from "../../components/PageState";
import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { StatisticsDashboard } from "../../lib/api/statisticsTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { navigationForRole, roleLabels, type NavigationItem } from "../../lib/routes";

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
  const { capabilities, isPending: capabilitiesPending } = useCapabilities();
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
  const workspaces = useQuery({
    queryKey: protectedQueryKeys.teamWorkspaces(userId),
    queryFn: api.teamWorkspaces,
    enabled: !administrator,
  });
  if (capabilitiesPending || scopes.isPending || actions.isPending || (Boolean(scope?.unitId) && statistics.isPending) || (!administrator && workspaces.isPending)) {
    return <PageState kind="loading" title="Opening your overview" />;
  }
  if (scopes.isError || actions.isError || statistics.isError || !scope?.unitId || !statistics.data) {
    return <PageState kind="error" title="Your overview could not be loaded">Refresh the page or ask an Administrator to review your reporting access.</PageState>;
  }
  const firstName = session!.user.displayName.trim().split(/\s+/u)[0];
  const organisationName = administrator ? "Platform service" : scope.name;
  const workspace = workspaces.data?.items[0];
  const destinations = navigationForRole(session!.user.role, capabilities, {
    statisticsAvailable: true,
    workspace: workspace ? { id: workspace.teamId, name: workspace.teamName } : undefined,
  }).filter((item) => item.path !== "/overview");
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading">
        <div>
          <span>{administrator ? "Administration overview" : `${scope.name} · ${roleLabels[session!.user.role]}`}</span>
          <h1>Welcome, {firstName}</h1>
          <p>Your assigned actions and the authorised {organisationName} workload are separated below.</p>
        </div>
        <Link className="button" to="/my-work">Open my assigned actions</Link>
      </header>
      <OverviewWorkloads actions={actions.data} data={statistics.data} organisationName={organisationName} />
      <OverviewDestinations items={destinations} />
    </main>
  );
}

function OverviewWorkloads({
  actions,
  data,
  organisationName,
}: {
  actions: Awaited<ReturnType<typeof actionNotificationApi.actions>>;
  data: StatisticsDashboard;
  organisationName: string;
}) {
  const metrics = new Map(data.summary.map((metric) => [metric.key, metric]));
  const organisationTitle = organisationName === "Platform service"
    ? "Platform service workload"
    : `${organisationName} organisation workload`;
  return (
    <div className="overview-workloads">
      <WorkloadRegion
        description="Actions assigned to you, including work waiting for somebody else to respond."
        title="Your workload"
        values={[
          ["Needs your action", actions.counts.needsMyAction],
          ["Waiting on others", actions.counts.waiting],
          ["Due soon", actions.counts.dueSoon],
        ]}
      />
      <WorkloadRegion
        description={`Combined demand for ${organisationName}. This is organisation workload, not your personal workload.`}
        title={organisationTitle}
        values={[
          ["Active demand", metrics.get("active")?.value ?? 0],
          ["Due within 7 days", data.dueRisk.find((row) => row.key === "due-1")?.count ?? 0],
          ["Overdue", metrics.get("overdue")?.value ?? 0],
          ["Completed in period", metrics.get("completed")?.value ?? 0],
        ]}
      />
    </div>
  );
}

function WorkloadRegion({
  description,
  title,
  values,
}: {
  description: string;
  title: string;
  values: ReadonlyArray<readonly [string, number]>;
}) {
  return (
    <section aria-label={title} className="overview-workload">
      <header><span>Workload scope</span><h2>{title}</h2><p>{description}</p></header>
      <div className={`overview-measures overview-measures--${values.length}`}>
        {values.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
    </section>
  );
}

function OverviewDestinations({ items }: { items: NavigationItem[] }) {
  return (
    <nav aria-label="Home destinations" className="overview-destinations">
      <header><div><span>Quick access</span><h2>Continue working</h2></div><p>Open an operational area or explore the information available to your account.</p></header>
      <div className="overview-destinations__grid">
        {items.map((item, index) => <DestinationTile index={index} item={item} key={item.path} />)}
      </div>
    </nav>
  );
}

function DestinationTile({ index, item }: { index: number; item: NavigationItem }) {
  const Icon = destinationIcon(item.path);
  return (
    <Link className="overview-destination" style={{ "--tile-order": index } as CSSProperties} to={item.path}>
      <span className="overview-destination__top"><Icon aria-hidden="true" size={19} strokeWidth={1.7} /><small aria-hidden="true">{String(index + 1).padStart(2, "0")}</small></span>
      <span className="overview-destination__copy"><strong>{item.label}</strong><span>{destinationDescription(item)}</span></span>
      <ArrowUpRight aria-hidden="true" className="overview-destination__arrow" size={17} />
    </Link>
  );
}

function destinationIcon(path: string): LucideIcon {
  if (path === "/my-work") return ListChecks;
  if (path.startsWith("/teams/")) return Building2;
  if (path === "/tracking") return ClipboardList;
  if (path === "/statistics") return BarChart3;
  if (path === "/organisation") return Network;
  if (path === "/admin/users") return Users;
  if (path === "/admin/configuration") return Settings;
  return Workflow;
}

function destinationDescription(item: NavigationItem) {
  if (item.path === "/my-work") return "Review actions assigned to you, including work that is waiting or due soon.";
  if (item.path.startsWith("/teams/")) return "Use the shared queue, calendar, people, statistics and handover tools.";
  if (item.path === "/tracking") return "Follow previously routed requests through their full operational lifecycle.";
  if (item.path === "/statistics") return "Explore authorised workload, timeliness and delivery trends for your branch.";
  if (item.path === "/organisation") return "Browse staffed units, reporting relationships and the wider organisation structure.";
  if (item.path === "/admin/users") return "Create accounts and maintain user access, status and profile information.";
  if (item.path === "/admin/configuration") return "Manage controlled organisation, routing and workflow configuration changes.";
  return "Claim available requests and record the next human routing or delivery decision.";
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
  const firstName = session!.user.displayName.trim().split(/\s+/u)[0];
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading"><div><span>Quality and release overview</span><h1>Welcome, {firstName}</h1><p>Your assigned review actions and the wider quality and release workload are separated below.</p></div><Link className="button" to="/quality-release">Open quality and release queue</Link></header>
      <div className="overview-workloads">
        <WorkloadRegion
          description="Reviews and release actions currently assigned to you."
          title="Your workload"
          values={[["Needs your action", actions.data.counts.needsMyAction], ["Waiting on others", actions.data.counts.waiting], ["Due soon", actions.data.counts.dueSoon]]}
        />
        <WorkloadRegion
          description="Combined quality and release activity. This is organisation workload, not your personal workload."
          title="Quality and release workload"
          values={[["Products released", metrics.get("released") ?? 0], ["Rework decisions", metrics.get("rework") ?? 0], ["Feedback received", metrics.get("feedback") ?? 0]]}
        />
      </div>
      <nav aria-label="Quality workspace links" className="overview-links overview-links--wide"><span>Quality links</span><h2>Continue quality work</h2><Link to="/quality-release">Quality and release queue<ArrowUpRight size={15} /></Link><Link to="/my-work">My assigned actions<ArrowUpRight size={15} /></Link><Link to={`/statistics?scopeId=${encodeURIComponent(scope.id)}&unitId=${encodeURIComponent(scope.unitId)}`}>Quality statistics<ArrowUpRight size={15} /></Link><Link to="/organisation">Organisation directory<ArrowUpRight size={15} /></Link></nav>
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
