import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

import { StatusPill } from "../../components/StatusPill";
import type { RequestSummary } from "../../lib/api/types";
import { elapsedTime, requiredDateSignal } from "../../lib/serviceTiming";
import { isComplete } from "../../lib/status";
import { CustomerProductPanel } from "../products/CustomerProductPanel";

export function RequestRegister({ items }: { items: RequestSummary[] }) {
  return (
    <div aria-label="Requests" className="request-register" role="table">
      <div className="request-register__header" role="row">
        <span role="columnheader">Reference</span>
        <span role="columnheader">Request</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">Current owner</span>
        <span role="columnheader">Required by</span>
        <span role="columnheader">Actions</span>
      </div>
      {items.map((request) => (
        <RequestRow key={request.id} request={request} />
      ))}
    </div>
  );
}

function RequestRow({ request }: { request: RequestSummary }) {
  const required = requiredDateSignal(request.requiredBy);
  const completed = isComplete(request.status);
  return (
    <div className="request-row" role="row">
      <span aria-hidden="true" className="request-row__indicator" role="presentation" />
      <span className="mono-ref" role="cell">
        {request.reference}
      </span>
      <strong role="cell">
        <Link className="request-row__title" to={`/requests/${request.id}`}>
          {request.title}
        </Link>
      </strong>
      <span className="request-row__status" role="cell">
        <StatusPill status={request.status} />
      </span>
      <span className="request-row__owner" role="cell">
        {request.currentOwner ?? "Awaiting assignment"}
        <small>
          {completed
            ? `Service span ${elapsedTime(request.createdAt, new Date(request.updatedAt))}`
            : `With owner for ${elapsedTime(request.updatedAt)}`}
        </small>
      </span>
      <time
        className={`required-signal required-signal--${required.tone}`}
        dateTime={request.requiredBy}
        role="cell"
      >
        {required.label}
        {!completed ? <small>Open for {elapsedTime(request.createdAt)}</small> : null}
      </time>
      <span className="request-row__actions" role="cell">
        {request.productAvailable ? <CustomerProductPanel compact requestId={request.id} /> : null}
        {request.productAvailable ? (
          <small>{request.feedbackSubmitted ? "Feedback received" : "Feedback requested"}</small>
        ) : null}
        <Link className="request-row__open" to={`/requests/${request.id}`}>
          Open <ArrowUpRight aria-hidden="true" size={15} />
        </Link>
      </span>
    </div>
  );
}
