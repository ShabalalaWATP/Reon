import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import type { RequestSummary } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { isComplete, requesterGroup } from "../../lib/status";
import { RequestRegister } from "./RequestRegister";
import { DraftRegister } from "./DraftRegister";
import { requestListPollInterval } from "./requestPolling";

export function RequestDashboardPage() {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const query = useQuery({
    queryKey: protectedQueryKeys.requests(userId),
    queryFn: api.requests,
    enabled: Boolean(session),
    refetchInterval: (currentQuery) =>
      requestListPollInterval(currentQuery.state.data),
  });
  const draftQuery = useQuery({
    queryKey: protectedQueryKeys.drafts(userId),
    queryFn: api.drafts,
    enabled: Boolean(session),
  });
  if (query.isPending || draftQuery.isPending) return <PageState kind="loading" title="Loading your requests" />;
  if (query.isError || draftQuery.isError) {
    return (
      <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Requests could not be loaded">
        Check your connection and try again.
      </PageState>
    );
  }
  const requests = query.data.items;
  const needsInput = requests.filter((item) => requesterGroup(item.status, item.needsRequesterInput) === "Needs your input");
  const inProgress = requests.filter((item) => requesterGroup(item.status, item.needsRequesterInput) === "In progress");
  const completed = requests.filter((item) => isComplete(item.status));

  return (
    <main className="page-stack">
      <header className="page-heading">
        <div><span>Customer request register</span><h1>My requests</h1><p>Follow current work, respond when needed and download released products.</p></div>
        <Link className="button button--primary" to="/requests/new"><Plus aria-hidden="true" size={17} />New request</Link>
      </header>
      <section className="status-ledger" aria-label="Request summary">
        <div className="status-ledger__attention"><span>Needs your input</span><strong>{needsInput.length}</strong><small>Waiting for a response from you</small></div>
        <dl><div><dt>In progress</dt><dd>{inProgress.length}</dd></div><div><dt>Completed</dt><dd>{completed.length}</dd></div><div><dt>Total requests</dt><dd>{requests.length}</dd></div></dl>
      </section>
      <DraftRegister items={draftQuery.data.items} />
      {requests.length === 0 ? (
        <PageState action={<Link className="button button--primary" to="/requests/new">Create your first request</Link>} kind="empty" title="No requests yet">
          Submit a structured request and its progress will appear here.
        </PageState>
      ) : (
        <>
          {needsInput.length > 0 ? <RequestSection eyebrow="Action required" items={needsInput} title="Needs your input" /> : null}
          <RequestSection eyebrow="Current work" items={inProgress} title="In progress" />
          {completed.length > 0 ? (
            <details className="request-history">
              <summary><span><strong>Completed history</strong><small>Disseminated, closed and cancelled requests</small></span><b>{completed.length}</b></summary>
              <RequestRegister items={completed} />
            </details>
          ) : null}
        </>
      )}
    </main>
  );
}

function RequestSection({ eyebrow, items, title }: { eyebrow: string; items: RequestSummary[]; title: string }) {
  if (items.length === 0) {
    return <section className="register-section"><header><span>{eyebrow}</span><h2>{title}</h2></header><p className="inline-empty">No requests in this group.</p></section>;
  }
  return <section className="register-section"><header><span>{eyebrow}</span><h2>{title}</h2></header><RequestRegister items={items} /></section>;
}
