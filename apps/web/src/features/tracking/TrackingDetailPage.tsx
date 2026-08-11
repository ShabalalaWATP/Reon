import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TrackedRequestDetail } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { TrackingJourney } from "./TrackingJourney";

export function TrackingDetailPage() {
  const { requestId = "" } = useParams();
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const query = useQuery({
    queryKey: protectedQueryKeys.trackedRequest(userId, requestId),
    queryFn: () => api.trackedRequest(requestId),
    enabled: Boolean(session && requestId),
    refetchInterval: 30_000,
  });
  if (query.isPending) return <PageState kind="loading" title="Loading tracked request" />;
  if (query.isError) return <PageState action={<Link className="button" to="/tracking">Back to tracking</Link>} kind="error" title="Tracked request not available">It may no longer exist or sit within your authorised route.</PageState>;
  const request = query.data;
  return (
    <main className="page-stack tracking-detail">
      <Link className="back-link" to="/tracking"><ArrowLeft aria-hidden="true" size={16} />Back to tracking</Link>
      <header className="detail-heading">
        <div><span className="mono-ref">{request.reference}</span><h1>{request.title}</h1><p>Submitted by {request.requesterDisplayName} on {formatDate(request.createdAt)}.</p></div>
        <StatusPill status={request.status} />
      </header>
      <div className="tracking-read-only"><strong>Read-only lifecycle view</strong><span>Return to the role queue to take an action.</span></div>
      <TrackingJourney request={request} />
      <TrackingRequestOverview request={request} />
    </main>
  );
}

function TrackingRequestOverview({ request }: { request: TrackedRequestDetail }) {
  const narratives = [
    ["Description of the need", request.description],
    ["Desired outcome", request.desiredOutcome],
    ["Background and known context", request.backgroundContext],
    ["Question to answer", request.questionToAnswer],
    ["Subject area or location", request.subjectAreaOrLocation],
    ["Activity or decision supported", request.supportedActivityOrDecision],
    ["Why the date matters", request.requiredByReason],
    ["Success criteria", request.successCriteria],
    ["Constraints or caveats", request.constraintsOrCaveats],
    ["Supporting information", request.supportingInformation],
    ["Handling instructions", request.handlingInstructions],
  ] as const;
  return (
    <section aria-labelledby="tracking-overview-title" className="detail-section">
      <div className="section-heading"><span>Submitted request</span><h2 id="tracking-overview-title">Request details</h2></div>
      <dl className="overview-grid">
        <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting routing"}</dd></div>
        <div><dt>Required by</dt><dd>{formatDate(request.requiredBy)}</dd></div>
        <div><dt>Relevant period</dt><dd>{request.coverageStart} to {request.coverageEnd}</dd></div>
        <div><dt>Customer urgency</dt><dd>{request.customerUrgency.replace("_", " ").toLowerCase()}</dd></div>
        <div><dt>Product format</dt><dd>{request.preferredDeliverableType}</dd></div>
        <div><dt>Sensitivity</dt><dd>{request.sensitivity.toLowerCase()}</dd></div>
      </dl>
      <div className="narrative-list">{narratives.map(([title, value]) => <article key={title}><h3>{title}</h3><p>{value}</p></article>)}</div>
    </section>
  );
}
