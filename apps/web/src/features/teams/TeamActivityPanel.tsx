import { useQuery } from "@tanstack/react-query";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";

export function TeamActivityPanel({ teamId, userId }: { teamId: string; userId: string }) {
  const query = useQuery({ queryKey: protectedQueryKeys.teamActivity(userId, teamId), queryFn: () => api.teamActivity(teamId) });
  if (query.isPending) return <PageState kind="loading" title="Loading team activity" />;
  if (query.isError) return <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Team activity could not be loaded" />;
  if (query.data.items.length === 0) return <PageState kind="empty" title="No team activity recorded">Roster and planning changes will appear here as immutable metadata events.</PageState>;
  return (
    <section aria-labelledby="team-activity-title" className="team-register">
      <header><span>Immutable history</span><h2 id="team-activity-title">Team activity</h2></header>
      <ol className="team-activity-list">
        {query.data.items.map((event) => <li key={event.id}><time dateTime={event.createdAt}>{formatDate(event.createdAt)}</time><div><strong>{event.subjectDisplayName}</strong><p>{event.summary}</p><small>{event.actorDisplayName ? `Recorded by ${event.actorDisplayName}` : "Applied by the scheduled membership service"}</small></div></li>)}
      </ol>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
