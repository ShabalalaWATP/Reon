import { useInfiniteQuery } from "@tanstack/react-query";

import { LoadMoreButton } from "../../components/LoadMoreButton";
import { PageState } from "../../components/PageState";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api/client";
import { flattenUniquePages } from "../../lib/api/pagination";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TrackedRequest } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate, trackingStatusLabel } from "../../lib/status";

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
          <span>Progress metadata only</span>
          <h1>Request tracking</h1>
          <p>
            Monitor status, ownership and route progression without opening
            Customer content or service products.
          </p>
        </div>
      </header>
      {requests.length === 0 ? (
        <PageState kind="empty" title="No requests to track">
          Submitted requests will appear here as they enter JIOC routing.
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
        <div>
          <span>Request reference</span>
          <h2 className="mono-ref">{request.reference}</h2>
        </div>
        <StatusPill label={trackingStatusLabel(request.status)} status={request.status} />
      </header>
      <dl>
        <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting routing"}</dd></div>
        <div><dt>Required by</dt><dd>{formatDate(request.requiredBy)}</dd></div>
        <div><dt>Last updated</dt><dd>{formatDate(request.updatedAt, true)}</dd></div>
      </dl>
      <div className="tracking-route">
        <span>Route</span>
        {request.route.length > 0 ? (
          <ol>
            {request.route.map((unit) => <li key={unit.id}>{unit.name}</li>)}
          </ol>
        ) : (
          <p>Route pending</p>
        )}
      </div>
      {request.awaitingTeamStaffing ? (
        <p className="staffing-warning" role="status">
          Awaiting team staffing
        </p>
      ) : null}
    </article>
  );
}
