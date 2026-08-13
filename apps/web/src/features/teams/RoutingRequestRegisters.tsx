import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

import { LoadMoreButton } from "../../components/LoadMoreButton";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api/client";
import { flattenUniquePages } from "../../lib/api/pagination";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TrackedRequest, TrackedRequestFilters } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

const terminalStatuses = new Set(["CLOSED_NOT_PROGRESSED", "CANCELLED"]);

type Props = {
  actionRequestIds: ReadonlySet<string>;
  teamId: string;
  userId: string;
};

export function RoutingRequestRegisters({ actionRequestIds, teamId, userId }: Props) {
  const filters: TrackedRequestFilters = {
    currentOwner: "",
    minimumAgeDays: "",
    routeUnitId: teamId,
    search: "",
    status: "",
  };
  const query = useInfiniteQuery({
    queryKey: protectedQueryKeys.trackedRequests(userId, JSON.stringify(filters)),
    queryFn: ({ pageParam }) => api.trackedRequests(pageParam ?? undefined, filters),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const tracked = query.data ? flattenUniquePages(query.data.pages) : [];
  const passive = tracked.filter((request) => !actionRequestIds.has(request.id));
  const completed = passive.filter(isCompletedForRouting);
  const active = passive.filter((request) => !isCompletedForRouting(request));
  return (
    <section aria-label="Requests monitored by this routing unit" className="routing-monitor">
      <header>
        <span>Route visibility</span>
        <h2>Requests after your routing decision</h2>
        <p>Read-only oversight is kept separate from work that this unit must action.</p>
      </header>
      <RequestDisclosure
        description="Still moving through production, review, release or Customer acceptance."
        hasMore={query.hasNextPage}
        items={active}
        kind="active"
        loading={query.isPending}
        loadingMore={query.isFetchingNextPage}
        onLoadMore={() => void query.fetchNextPage()}
        title="Active requests routed onwards"
      />
      <RequestDisclosure
        description="Accepted by the Customer, cancelled or closed without delivery."
        hasMore={query.hasNextPage}
        items={completed}
        kind="completed"
        loading={query.isPending}
        loadingMore={query.isFetchingNextPage}
        onLoadMore={() => void query.fetchNextPage()}
        title="Completed requests"
      />
      {query.isError ? <p className="form-banner form-banner--error" role="alert">Monitored requests could not be loaded.</p> : null}
    </section>
  );
}

function RequestDisclosure({ description, hasMore, items, kind, loading, loadingMore, onLoadMore, title }: {
  description: string;
  hasMore: boolean;
  items: TrackedRequest[];
  kind: "active" | "completed";
  loading: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  title: string;
}) {
  return (
    <details className={`routing-monitor__group routing-monitor__group--${kind}`}>
      <summary><ChevronRight aria-hidden="true" size={18} /><span><strong>{title}</strong><small>{description}</small></span><b>{loading ? "…" : items.length}</b></summary>
      <div className="routing-monitor__content">
        {items.length ? <ol>{items.map((request) => <MonitoredRequest key={request.id} request={request} />)}</ol> : <p className="inline-empty">{loading ? "Loading monitored requests…" : "No requests in this section."}</p>}
        <LoadMoreButton hasMore={hasMore} loading={loadingMore} onLoad={onLoadMore} />
      </div>
    </details>
  );
}

function MonitoredRequest({ request }: { request: TrackedRequest }) {
  const awaitingAcceptance = request.status === "COMPLETED"
    && request.customerAcceptanceRequired
    && !request.customerAcceptedAt;
  return (
    <li>
      <div><span>{request.reference}</span><Link to={`/tracking/${request.id}`}>{request.title}</Link></div>
      <StatusPill label={awaitingAcceptance ? "Awaiting Customer acceptance" : undefined} status={request.status} />
      <dl>
        <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting routing"}</dd></div>
        <div><dt>Required by</dt><dd>{formatDate(request.requiredBy)}</dd></div>
        <div><dt>Open</dt><dd>{request.ageDays} day{request.ageDays === 1 ? "" : "s"}</dd></div>
      </dl>
      <Link className="routing-monitor__open" to={`/tracking/${request.id}`}>Open read-only history</Link>
    </li>
  );
}

function isCompletedForRouting(request: TrackedRequest) {
  if (terminalStatuses.has(request.status)) return true;
  if (request.status !== "COMPLETED") return false;
  return !request.customerAcceptanceRequired || Boolean(request.customerAcceptedAt);
}
