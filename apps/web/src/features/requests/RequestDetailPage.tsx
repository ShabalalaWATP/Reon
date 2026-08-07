import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { StatusJourney } from "../../components/StatusJourney";
import { StatusPill } from "../../components/StatusPill";
import { api, ApiError, productDownloadUrl } from "../../lib/api/client";
import type { FeedbackInput } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { FeedbackForm } from "./FeedbackForm";
import { RequesterAction } from "./RequesterAction";
import { RequestOverview } from "./RequestOverview";
import { requestDetailPollInterval } from "./requestPolling";

export function RequestDetailPage() {
  const { requestId = "" } = useParams();
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: protectedQueryKeys.request(userId, requestId),
    queryFn: () => api.request(requestId),
    enabled: Boolean(session && requestId),
    refetchInterval: (currentQuery) =>
      requestDetailPollInterval(currentQuery.state.data),
  });
  const feedback = useMutation({
    mutationFn: (input: FeedbackInput) => api.feedback(requestId, input, session?.csrfToken ?? ""),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: protectedQueryKeys.request(userId, requestId),
      }),
  });
  if (query.isPending) return <PageState kind="loading" title="Loading request" />;
  if (query.isError) return <PageState action={<Link className="button" to="/requests">Back to my requests</Link>} kind="error" title="Request not available">It may no longer exist or you may not have access.</PageState>;
  const request = query.data;
  const releasedProduct =
    request.status === "COMPLETED" && request.deliverable?.releasedAt
      ? request.deliverable
      : null;

  return (
    <main className="page-stack request-workspace">
      <Link className="back-link" to="/requests"><ArrowLeft aria-hidden="true" size={16} />My requests</Link>
      <header className="detail-heading">
        <div><span className="mono-ref">{request.reference}</span><h1>{request.title}</h1><p>Submitted by Customer {request.requester.displayName} on {formatDate(request.createdAt)}.</p></div>
        <StatusPill status={request.status} />
      </header>
      <StatusJourney status={request.status} />
      {request.workflowError ? <p className="form-banner form-banner--warning" role="status">Progress is temporarily delayed. Staff have been notified.</p> : null}
      {["INFORMATION_REQUIRED", "CUSTOMER_INFORMATION_REQUIRED"].includes(request.status) ? (
        <RequesterAction
          clarification={request.clarifications.find((thread) => thread.status === "OPEN")}
          requestId={request.id}
        />
      ) : null}
      <div className="detail-layout">
        <RequestOverview request={request} />
        <aside aria-label="Activity, released product and feedback" className="detail-aside">
          <section className="detail-section" aria-labelledby="activity-title">
            <div className="section-heading"><span>Immutable history</span><h2 id="activity-title">Activity</h2></div>
            {request.events.length === 0 ? <p className="inline-empty">No activity has been recorded yet.</p> : <ol className="activity-list">{request.events.map((event) => <li key={event.id}><span aria-hidden="true" /><div><strong>{event.message}</strong><small>{event.actorDisplayName ?? "ISTARI service"} · <time dateTime={event.createdAt}>{formatDate(event.createdAt, true)}</time></small></div></li>)}</ol>}
          </section>
          <section className="detail-section" aria-labelledby="deliverable-title">
            <div className="section-heading"><span>Disseminated result</span><h2 id="deliverable-title">Service product</h2></div>
            {releasedProduct ? <article className="deliverable"><h3>{releasedProduct.title}</h3><p>{releasedProduct.text}</p><small>Disseminated {formatDate(releasedProduct.releasedAt!, true)}</small><a className="button product-download" href={productDownloadUrl(request.id)}>Download product</a></article> : <p className="inline-empty">The product will appear here after dissemination.</p>}
          </section>
          <section className="detail-section" aria-labelledby="feedback-title">
            <div className="section-heading"><span>After completion</span><h2 id="feedback-title">Feedback</h2></div>
            {request.feedback ? <div className="feedback-result"><strong>{request.feedback.rating} out of 5</strong><p>{request.feedback.comments}</p><small>Received {formatDate(request.feedback.createdAt)}</small></div> : releasedProduct ? <><p>Rate the service and tell the production team how well the product met your need.</p>{feedback.isError ? <p className="form-banner form-banner--error" role="alert">{feedback.error instanceof ApiError ? feedback.error.message : "Feedback could not be sent."}</p> : null}<FeedbackForm disabled={feedback.isPending} onSubmit={(input) => feedback.mutate(input)} /></> : <p className="inline-empty">Feedback opens after dissemination is complete.</p>}
          </section>
        </aside>
      </div>
    </main>
  );
}
