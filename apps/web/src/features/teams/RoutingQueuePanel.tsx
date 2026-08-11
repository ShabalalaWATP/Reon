import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { UserRole } from "../../lib/api/types";
import { roleRoutes } from "../../lib/routes";
import { elapsedTime } from "../../lib/serviceTiming";
import { statusLabels } from "../../lib/status";

export function RoutingQueuePanel({ role, teamId, userId }: { role: UserRole; teamId: string; userId: string }) {
  const query = useQuery({ queryKey: protectedQueryKeys.workItems(userId, teamId), queryFn: () => api.workItems(undefined, teamId) });
  if (query.isPending) return <PageState kind="loading" title="Loading routing queue" />;
  if (query.isError) return <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Routing queue could not be loaded" />;
  return <section className="routing-queue" aria-labelledby="routing-queue-title">
    <header><span>Claim-based routing</span><h2 id="routing-queue-title">Current queue</h2><p>Managers and Members use the same human-led routing action. Manager status does not add an approval stage or allocate the decision to somebody else.</p></header>
    {query.data.items.length ? <div className="team-table-wrap"><table className="team-table"><caption>Current routing work visible to you</caption><thead><tr><th scope="col">Reference</th><th scope="col">Request</th><th scope="col">Stage</th><th scope="col">Ownership</th><th scope="col">Waiting</th></tr></thead><tbody>{query.data.items.map((item) => <tr key={item.id}><th className="mono-ref" scope="row">{item.requestReference}</th><td>{item.title}</td><td>{statusLabels[item.stage]}</td><td>{item.assigneeId ? item.assigneeDisplayName ?? "Claimed" : "Available to claim"}</td><td>{elapsedTime(item.createdAt)}</td></tr>)}</tbody></table></div> : <PageState kind="empty" title="No routing work is waiting">New items will appear here when they reach this unit and your role is eligible.</PageState>}
    <Link className="button button--primary" to={roleRoutes[role]}>Open routing actions</Link>
  </section>;
}
