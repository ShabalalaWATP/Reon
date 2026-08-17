import type { CSSProperties } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarDays,
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
import type { StatisticsDashboard } from "../../lib/api/statisticsTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import type { NavigationItem } from "../../lib/routes";
import {
  scopedOverviewEyebrow,
  type OverviewActions,
  useQualityOverviewController,
  useScopedOverviewController,
} from "./useRoleOverviewController";

export function RoleOverviewPage() {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Your overview could not be loaded" />;
  const role = session.user.role;
  if (role === "REQUESTER") return <Navigate replace to="/requests" />;
  if (role === "QUALITY_RELEASE") return <QualityOverview session={session} />;
  return <ScopedOverview administrator={role === "PLATFORM_ADMIN"} session={session} />;
}

function ScopedOverview({
  administrator,
  session,
}: {
  administrator: boolean;
  session: import("../../lib/api/types").Session;
}) {
  const state = useScopedOverviewController(session, administrator);
  if (state.kind === "loading") return <PageState kind="loading" title="Opening your overview" />;
  if (state.kind === "error") {
    return (
      <PageState kind="error" title="Your overview could not be loaded">
        Refresh the page or ask an Administrator to review your reporting access.
      </PageState>
    );
  }
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading">
        <div>
          <span>{scopedOverviewEyebrow(session, administrator, state.organisationName)}</span>
          <h1>Welcome, {state.firstName}</h1>
          <p>
            {state.statistics
              ? `Your assigned actions and the authorised ${state.organisationName} workload are separated below.`
              : `Your assigned actions and shared ${state.organisationName} workspace are available below.`}
          </p>
        </div>
        <Link className="button" to="/my-work">
          Open my assigned actions
        </Link>
      </header>
      <OverviewWorkloads
        actions={state.actions}
        data={state.statistics}
        organisationName={state.organisationName}
      />
      <OverviewDestinations items={state.destinations} />
    </main>
  );
}

function OverviewWorkloads({
  actions,
  data,
  organisationName,
}: {
  actions?: OverviewActions;
  data?: StatisticsDashboard;
  organisationName: string;
}) {
  const organisationTitle =
    organisationName === "Platform service"
      ? "Platform service workload"
      : `${organisationName} organisation workload`;
  return (
    <div
      className={data ? "overview-workloads" : "overview-workloads overview-workloads--personal"}
    >
      <WorkloadRegion
        description="Actions assigned to you, including work waiting for somebody else to respond."
        title="Your workload"
        values={personalWorkloadValues(actions)}
      />
      {data ? (
        <WorkloadRegion
          description={`Combined demand for ${organisationName}. This is organisation workload, not your personal workload.`}
          title={organisationTitle}
          values={organisationWorkloadValues(data)}
        />
      ) : null}
    </div>
  );
}

function personalWorkloadValues(
  actions?: OverviewActions,
): ReadonlyArray<readonly [string, number]> {
  return [
    ["Needs your action", actions?.counts.needsMyAction ?? 0],
    ["Waiting on others", actions?.counts.waiting ?? 0],
    ["Due soon", actions?.counts.dueSoon ?? 0],
  ];
}

function organisationWorkloadValues(
  data: StatisticsDashboard,
): ReadonlyArray<readonly [string, number]> {
  const metrics = new Map(data.summary.map((metric) => [metric.key, metric]));
  return [
    ["Active demand", metrics.get("active")?.value ?? 0],
    ["Due within 7 days", data.dueRisk.find((row) => row.key === "due-1")?.count ?? 0],
    ["Overdue", metrics.get("overdue")?.value ?? 0],
    ["Completed in period", metrics.get("completed")?.value ?? 0],
  ];
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
      <header>
        <span>Workload scope</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className={`overview-measures overview-measures--${values.length}`}>
        {values.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function OverviewDestinations({ items }: { items: NavigationItem[] }) {
  return (
    <nav aria-label="Home destinations" className="overview-destinations">
      <header>
        <div>
          <span>Quick access</span>
          <h2>Continue working</h2>
        </div>
        <p>Open an operational area or explore the information available to your account.</p>
      </header>
      <div className="overview-destinations__grid">
        {items.map((item, index) => (
          <DestinationTile index={index} item={item} key={item.path} />
        ))}
      </div>
    </nav>
  );
}

function DestinationTile({ index, item }: { index: number; item: NavigationItem }) {
  const Icon = destinationIcon(item.path);
  return (
    <Link
      className="overview-destination"
      style={{ "--tile-order": index } as CSSProperties}
      to={item.path}
    >
      <span className="overview-destination__top">
        <Icon aria-hidden="true" size={19} strokeWidth={1.7} />
        <small aria-hidden="true">{String(index + 1).padStart(2, "0")}</small>
      </span>
      <span className="overview-destination__copy">
        <strong>{item.label}</strong>
        <span>{destinationDescription(item)}</span>
      </span>
      <ArrowUpRight aria-hidden="true" className="overview-destination__arrow" size={17} />
    </Link>
  );
}

function destinationIcon(path: string): LucideIcon {
  if (path === "/my-work") return ListChecks;
  if (path.startsWith("/teams/")) return Building2;
  if (path === "/tracking") return ClipboardList;
  if (path.startsWith("/calendar/")) return CalendarDays;
  if (path === "/statistics") return BarChart3;
  if (path === "/organisation") return Network;
  if (path === "/admin/users") return Users;
  if (path === "/admin/configuration") return Settings;
  return Workflow;
}

function destinationDescription(item: NavigationItem) {
  if (item.path === "/my-work")
    return "Review actions assigned to you, including work that is waiting or due soon.";
  if (item.path.startsWith("/teams/"))
    return "Open your unit's work queue, board, calendar, people and performance tools.";
  if (item.path === "/tracking")
    return "Follow previously routed requests through their full operational lifecycle.";
  if (item.path.startsWith("/calendar/"))
    return "Manage your own availability and events, which also appear in your current team calendar.";
  if (item.path === "/statistics")
    return "Explore authorised workload, timeliness and delivery trends for your branch.";
  if (item.path === "/organisation")
    return "Browse staffed units, reporting relationships and the wider organisation structure.";
  if (item.path === "/admin/users")
    return "Create accounts and maintain user access, status and profile information.";
  if (item.path === "/admin/configuration")
    return "Manage controlled organisation, routing and workflow configuration changes.";
  return "Claim available requests and record the next human routing or delivery decision.";
}

function QualityOverview({ session }: { session: import("../../lib/api/types").Session }) {
  const state = useQualityOverviewController(session);
  if (state.kind === "loading")
    return <PageState kind="loading" title="Opening quality overview" />;
  if (state.kind === "error")
    return <PageState kind="error" title="Quality overview could not be loaded" />;
  return (
    <main className="page-stack role-overview">
      <header className="overview-heading">
        <div>
          <span>Combined QC Team</span>
          <h1>Welcome, {state.firstName}</h1>
          <p>
            {state.isManager
              ? "A QC User or QC Manager reviews each product package. A different QC Manager then disseminates the approved package."
              : "QC Users review assigned product packages and return work that needs correction. Dissemination remains a QC Manager action."}
          </p>
        </div>
        <Link className="button" to="/quality-release">
          Open QC Team workspace
        </Link>
      </header>
      <div
        className={
          state.metrics ? "overview-workloads" : "overview-workloads overview-workloads--personal"
        }
      >
        <WorkloadRegion
          description={
            state.isManager
              ? "Reviews and release actions currently assigned to you."
              : "Product reviews currently assigned to you."
          }
          title="Your workload"
          values={[
            ["Needs your action", state.actions.counts.needsMyAction],
            ["Waiting on others", state.actions.counts.waiting],
            ["Due soon", state.actions.counts.dueSoon],
          ]}
        />
        {state.metrics ? (
          <WorkloadRegion
            description="Combined QC Team activity. This is organisation workload, not your personal workload."
            title="QC Team workload"
            values={[
              ["Products released", state.metrics.get("released") ?? 0],
              ["Rework decisions", state.metrics.get("rework") ?? 0],
              ["Feedback received", state.metrics.get("feedback") ?? 0],
            ]}
          />
        ) : null}
      </div>
      <nav aria-label="QC Team workspace links" className="overview-links overview-links--wide">
        <span>QC Team links</span>
        <h2>Continue QC Team work</h2>
        <Link to="/quality-release">
          QC Team workspace
          <ArrowUpRight size={15} />
        </Link>
        <Link to="/my-work">
          My assigned actions
          <ArrowUpRight size={15} />
        </Link>
        {state.scopeId && state.unitId ? (
          <Link
            to={`/statistics?scopeId=${encodeURIComponent(state.scopeId)}&unitId=${encodeURIComponent(state.unitId)}`}
          >
            Quality statistics
            <ArrowUpRight size={15} />
          </Link>
        ) : null}
        <Link to="/calendar/month">
          Personal calendar
          <ArrowUpRight size={15} />
        </Link>
        <Link to="/organisation">
          Organisation directory
          <ArrowUpRight size={15} />
        </Link>
      </nav>
    </main>
  );
}
