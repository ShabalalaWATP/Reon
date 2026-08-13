import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { DeliveryTeamHome } from "./DeliveryTeamHome";
import { RoutingTeamHome } from "./RoutingTeamHome";
import { TeamNoticeboard } from "./TeamNoticeboard";

const overviewTo = localDateInputValue(new Date());
const overviewFrom = localDateInputValue(addLocalDays(new Date(), -29));

export function TeamOverviewPage({ access, userId }: { access: TeamWorkspaceAccess; userId: string }) {
  const query = useQuery({ queryKey: protectedQueryKeys.teamWorkspace(userId, access.teamId), queryFn: () => api.teamWorkspace(access.teamId) });
  if (query.isPending) return <PageState kind="loading" title="Loading team home" />;
  if (query.isError) return <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Team home could not be loaded">Check your connection and current workspace access.</PageState>;
  const data = query.data;
  const delivery = access.unitKind === "TEAM" || !access.unitKind;
  return (
    <>
      <section aria-label="Workspace staffing" className="team-home__identity">
        <div><span>Managers</span><strong>{data.managerCount}</strong></div>
        <div><span>{delivery ? "Analysts" : "Members"}</span><strong>{delivery ? data.analystCount : data.memberCount ?? 0}</strong></div>
        <div><span>Active work</span><strong>{data.activeWorkCount}</strong></div>
      </section>
      {delivery ? <DeliveryTeamHome access={access} overview={data} userId={userId} /> : <RoutingTeamHome access={access} overview={data} userId={userId} />}
      <TeamNoticeboard access={access} userId={userId} />
      <TeamStatisticsStrip teamId={access.teamId} userId={userId} />
    </>
  );
}

export function TeamStatisticsStrip({ teamId, userId }: { teamId: string; userId: string }) {
  const scopes = useQuery({ queryKey: protectedQueryKeys.statisticsScopes(userId), queryFn: api.statisticsScopes });
  const scope = scopes.data?.items.find((item) => item.unitId === teamId);
  const statistics = useQuery({
    queryKey: protectedQueryKeys.statistics(userId, scope?.id ?? "", teamId, overviewFrom, overviewTo, "Europe/London"),
    queryFn: () => api.statistics({ scopeId: scope!.id, unitId: teamId, from: overviewFrom, to: overviewTo, timeZone: "Europe/London" }),
    enabled: Boolean(scope),
  });
  if (!scope || !statistics.data) return null;
  const metrics = new Map(statistics.data.summary.map((metric) => [metric.key, metric.value]));
  return <section aria-label="Team service measures" className="team-service-strip"><div><span>Received in 30 days</span><strong>{metrics.get("received") ?? 0}</strong></div><div><span>Completed</span><strong>{metrics.get("completed") ?? 0}</strong></div><div><span>Products released</span><strong>{metrics.get("released") ?? 0}</strong></div><Link to={`/statistics?scopeId=${encodeURIComponent(scope.id)}&unitId=${encodeURIComponent(teamId)}`}>Full statistics</Link></section>;
}
