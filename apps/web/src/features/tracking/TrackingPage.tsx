import { useInfiniteQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

import { LoadMoreButton } from "../../components/LoadMoreButton";
import { PageState } from "../../components/PageState";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api/client";
import { flattenUniquePages } from "../../lib/api/pagination";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TrackedRequest } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate, trackingStatusLabel } from "../../lib/status";
import { TrackingJourney } from "./TrackingJourney";

export function TrackingPage() {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const query = useInfiniteQuery({
    queryKey: protectedQueryKeys.trackedRequests(userId),
    queryFn: ({ pageParam }) => api.trackedRequests(pageParam ?? undefined),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: Boolean(session),
    refetchInterval: 30_000,
  });

  if (query.isPending) {
    return <PageState kind="loading" title="Loading tracked requests" />;
  }
  if (query.isError) {
    return (
      <PageState
        action={
          <button className="button" onClick={() => void query.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Tracking could not be loaded"
      >
        Check your connection and try again.
      </PageState>
    );
  }

  const requests = flattenUniquePages(query.data.pages);
  return (
    <main className="page-stack tracking-page">
      <header className="page-heading">
        <div>
          <span>Authorised route view</span>
          <h1>Request tracking</h1>
          <p>
            Follow requests your organisation has routed through delivery and
            reopen their submitted detail without entering the action queue.
          </p>
        </div>
      </header>
      {requests.length === 0 ? (
        <PageState kind="empty" title="No requests to track">
          Submitted requests will appear here as they enter CRIOC routing.
        </PageState>
      ) : (
        <section aria-label="Tracked requests" className="tracking-register">
          {requests.map((request) => (
            <TrackedRequestRow key={request.id} request={request} />
          ))}
          <LoadMoreButton
            hasMore={query.hasNextPage}
            loading={query.isFetchingNextPage}
            onLoad={() => void query.fetchNextPage()}
          />
        </section>
      )}
    </main>
  );
}

function TrackedRequestRow({ request }: { request: TrackedRequest }) {
  return (
    <article className="tracking-row">
      <header>
        <div className="tracking-row__identity">
          <Link className="mono-ref" to={`/tracking/${request.id}`}>{request.reference}</Link>
          <h2><Link to={`/tracking/${request.id}`}>{request.title}</Link></h2>
          <span>Updated {formatDate(request.updatedAt, true)}</span>
        </div>
        <StatusPill label={trackingStatusLabel(request.status)} status={request.status} />
      </header>
      <dl>
        <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting routing"}</dd></div>
        <div><dt>Required by</dt><dd>{formatDate(request.requiredBy)}</dd></div>
        <div><dt>Submitted</dt><dd>{formatDate(request.createdAt)}</dd></div>
      </dl>
      <TrackingJourney request={request} />
      {request.awaitingTeamStaffing ? (
        <p className="staffing-warning" role="status">
          Awaiting team staffing
        </p>
      ) : null}
      <Link className="tracking-open-link" to={`/tracking/${request.id}`}>Open request <ArrowUpRight aria-hidden="true" size={15} /></Link>
    </article>
  );
}
