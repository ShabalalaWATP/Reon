import { useInfiniteQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { LoadMoreButton } from "../../components/LoadMoreButton";
import { api } from "../../lib/api/client";
import { flattenUniquePages } from "../../lib/api/pagination";
import type { RequestSummary } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { isComplete, requesterGroup } from "../../lib/status";
import { RequestRegister } from "./RequestRegister";
import { DraftRegister } from "./DraftRegister";
import { requestListPollInterval } from "./requestPolling";

export function RequestDashboardPage() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const query = useInfiniteQuery({
    queryKey: queryKeys.requests(),
    queryFn: ({ pageParam }) => api.requests(pageParam ?? undefined),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: Boolean(session),
    refetchInterval: (currentQuery) => requestListPollInterval(currentQuery.state.data),
  });
  const draftQuery = useInfiniteQuery({
    queryKey: queryKeys.drafts(),
    queryFn: ({ pageParam }) => api.drafts(pageParam ?? undefined),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: Boolean(session),
  });
  if (query.isPending || draftQuery.isPending)
    return <PageState kind="loading" title="Loading your requests" />;
  if (query.isError || draftQuery.isError) {
    return (
      <PageState
        action={
          <button
            className="button"
            onClick={() => void Promise.all([query.refetch(), draftQuery.refetch()])}
          >
            Try again
          </button>
        }
        kind="error"
        title="Requests could not be loaded"
      >
        Check your connection and try again.
      </PageState>
    );
  }
  const requests = flattenUniquePages(query.data.pages);
  const drafts = flattenUniquePages(draftQuery.data.pages);
  const needsInput = requests.filter(
    (item) => requesterGroup(item.status, item.needsRequesterInput) === "Needs your input",
  );
  const inProgress = requests.filter(
    (item) => requesterGroup(item.status, item.needsRequesterInput) === "In progress",
  );
  const completed = requests.filter((item) => isComplete(item.status));

  return (
    <main className="page-stack">
      <header className="page-heading">
        <div>
          <span>Customer request register</span>
          <h1>My requests</h1>
          <p>
            Track progress, respond to information requests and download released products. New
            actions also appear in notifications.
          </p>
        </div>
        <Link className="button button--primary" to="/requests/new">
          <Plus aria-hidden="true" size={17} />
          New request
        </Link>
      </header>
      <section className="status-ledger" aria-label="Request summary">
        <div className="status-ledger__attention">
          <span>Needs your input</span>
          <strong>{needsInput.length}</strong>
          <small>
            {needsInput.length > 0 ? "Open the request to respond" : "Nothing is waiting for you"}
          </small>
        </div>
        <dl>
          <div>
            <dt>In progress</dt>
            <dd>{inProgress.length}</dd>
          </div>
          <div>
            <dt>Completed</dt>
            <dd>{completed.length}</dd>
          </div>
          <div>
            <dt>Total requests</dt>
            <dd>{requests.length}</dd>
          </div>
        </dl>
      </section>
      <DraftRegister items={drafts} />
      <LoadMoreButton
        hasMore={draftQuery.hasNextPage}
        loading={draftQuery.isFetchingNextPage}
        onLoad={() => void draftQuery.fetchNextPage()}
      />
      {requests.length === 0 ? (
        <PageState
          action={
            <Link className="button button--primary" to="/requests/new">
              Create your first request
            </Link>
          }
          kind="empty"
          title="No requests yet"
        >
          Submit a structured request and its progress will appear here.
        </PageState>
      ) : (
        <>
          {needsInput.length > 0 ? (
            <RequestSection eyebrow="Action required" items={needsInput} title="Needs your input" />
          ) : null}
          <RequestSection eyebrow="Request register" items={inProgress} title="Current requests" />
          {completed.length > 0 ? <CompletedHistory items={completed} /> : null}
          <LoadMoreButton
            hasMore={query.hasNextPage}
            loading={query.isFetchingNextPage}
            onLoad={() => void query.fetchNextPage()}
          />
        </>
      )}
    </main>
  );
}

function CompletedHistory({ items }: { items: RequestSummary[] }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="request-history" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        <span>
          <strong>Completed history</strong>
          <small>Disseminated, closed and cancelled requests</small>
        </span>
        <b>{items.length}</b>
      </summary>
      {open ? <RequestRegister items={items} /> : null}
    </details>
  );
}

function RequestSection({
  eyebrow,
  items,
  title,
}: {
  eyebrow: string;
  items: RequestSummary[];
  title: string;
}) {
  if (items.length === 0) {
    return (
      <section className="register-section">
        <header>
          <span>{eyebrow}</span>
          <h2>{title}</h2>
        </header>
        <p className="inline-empty">No requests in this group.</p>
      </section>
    );
  }
  return (
    <section className="register-section">
      <header>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </header>
      <RequestRegister items={items} />
    </section>
  );
}
