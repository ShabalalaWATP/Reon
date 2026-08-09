import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

import { StatusPill } from "../../components/StatusPill";
import type { RequestSummary } from "../../lib/api/types";
import { elapsedTime, requiredDateSignal } from "../../lib/serviceTiming";
import { isComplete } from "../../lib/status";
import { CustomerProductPanel } from "../products/CustomerProductPanel";

export function RequestRegister({ items }: { items: RequestSummary[] }) {
  return (
    <div className="request-register">
      {items.map((request) => <RequestRow key={request.id} request={request} />)}
    </div>
  );
}

function RequestRow({ request }: { request: RequestSummary }) {
  const required = requiredDateSignal(request.requiredBy);
  const completed = isComplete(request.status);
  return (
    <article className="request-row">
          <span className="request-row__indicator" aria-hidden="true" />
          <span className="mono-ref">{request.reference}</span>
          <strong><Link className="request-row__title" to={`/requests/${request.id}`}>{request.title}</Link></strong>
          <span className="request-row__status"><StatusPill status={request.status} /></span>
          <span className="request-row__owner">
            {request.currentOwner ?? "Awaiting assignment"}
            <small>{completed ? `Service span ${elapsedTime(request.createdAt, new Date(request.updatedAt))}` : `With owner for ${elapsedTime(request.updatedAt)}`}</small>
          </span>
          <time className={`required-signal required-signal--${required.tone}`} dateTime={request.requiredBy}>
            {required.label}
            {!completed ? <small>Open for {elapsedTime(request.createdAt)}</small> : null}
          </time>
          <span className="request-row__actions">
            {request.productAvailable ? <CustomerProductPanel compact requestId={request.id} /> : null}
            {request.productAvailable ? <small>{request.feedbackSubmitted ? "Feedback received" : "Feedback requested"}</small> : null}
            <Link className="request-row__open" to={`/requests/${request.id}`}>Open <ArrowUpRight aria-hidden="true" size={15} /></Link>
          </span>
    </article>
  );
}
