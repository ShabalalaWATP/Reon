import { ApiError } from "../../lib/api/client";
import type { FeedbackInput, RequestDetail } from "../../lib/api/types";
import { formatDate } from "../../lib/status";
import { CustomerProductPanel } from "../products/CustomerProductPanel";
import { FeedbackForm } from "./FeedbackForm";
import { RequesterAction } from "./RequesterAction";

export function RequestAttention({ request }: { request: RequestDetail }) {
  const needsInformation = ["INFORMATION_REQUIRED", "CUSTOMER_INFORMATION_REQUIRED"].includes(
    request.status,
  );
  return (
    <>
      {request.workflowError ? (
        <p className="form-banner form-banner--warning" role="status">
          Progress is temporarily delayed. Staff have been notified.
        </p>
      ) : null}
      {needsInformation ? (
        <RequesterAction
          clarification={request.clarifications.find((thread) => thread.status === "OPEN")}
          requestId={request.id}
        />
      ) : null}
    </>
  );
}

export function CustomerProductSection({ request }: { request: RequestDetail }) {
  return (
    <section className="detail-section" aria-labelledby="deliverable-title">
      <div className="section-heading">
        <span>Disseminated result</span>
        <h2 id="deliverable-title">Service product</h2>
      </div>
      {request.productAvailable ? (
        <CustomerProductPanel requestId={request.id} />
      ) : (
        <p className="inline-empty">The product will appear here after dissemination.</p>
      )}
    </section>
  );
}

type FeedbackMutation = {
  error: Error | null;
  isError: boolean;
  isPending: boolean;
  mutate: (input: FeedbackInput) => void;
};

export function CustomerFeedbackSection({
  feedback,
  request,
}: {
  feedback: FeedbackMutation;
  request: RequestDetail;
}) {
  return (
    <section className="detail-section" aria-labelledby="feedback-title">
      <div className="section-heading">
        <span>After completion</span>
        <h2 id="feedback-title">Feedback</h2>
      </div>
      <CustomerFeedbackContent feedback={feedback} request={request} />
    </section>
  );
}

function CustomerFeedbackContent({
  feedback,
  request,
}: {
  feedback: FeedbackMutation;
  request: RequestDetail;
}) {
  if (request.feedback) {
    return (
      <div className="feedback-result">
        <strong>{request.feedback.rating} out of 5</strong>
        <p>{request.feedback.comments}</p>
        <small>Received {formatDate(request.feedback.createdAt)}</small>
      </div>
    );
  }
  const released = request.status === "COMPLETED" && Boolean(request.deliverable?.releasedAt);
  if (!request.productAvailable && !released) {
    return <p className="inline-empty">Feedback opens after dissemination is complete.</p>;
  }
  return (
    <>
      <p>Rate the service and tell the production team how well the product met your need.</p>
      {feedback.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          {feedback.error instanceof ApiError
            ? feedback.error.message
            : "Feedback could not be sent."}
        </p>
      ) : null}
      <FeedbackForm disabled={feedback.isPending} onSubmit={feedback.mutate} />
    </>
  );
}
