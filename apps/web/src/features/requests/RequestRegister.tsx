import { ArrowDownToLine, ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

import { StatusPill } from "../../components/StatusPill";
import { productDownloadUrl } from "../../lib/api/client";
import type { RequestSummary } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

export function RequestRegister({ items }: { items: RequestSummary[] }) {
  return (
    <div className="request-register">
      {items.map((request) => (
        <article className="request-row" key={request.id}>
          <span className="request-row__indicator" aria-hidden="true" />
          <span className="mono-ref">{request.reference}</span>
          <strong><Link className="request-row__title" to={`/requests/${request.id}`}>{request.title}</Link></strong>
          <span className="request-row__status"><StatusPill status={request.status} /></span>
          <span className="request-row__owner">{request.currentOwner ?? "Awaiting assignment"}</span>
          <time dateTime={request.requiredBy}>Needed {formatDate(request.requiredBy)}</time>
          <span className="request-row__actions">
            {request.productAvailable ? <a className="request-row__download" href={productDownloadUrl(request.id)}><ArrowDownToLine aria-hidden="true" size={15} />Download product</a> : null}
            {request.productAvailable ? <small>{request.feedbackSubmitted ? "Feedback received" : "Feedback requested"}</small> : null}
            <Link className="request-row__open" to={`/requests/${request.id}`}>Open <ArrowUpRight aria-hidden="true" size={15} /></Link>
          </span>
        </article>
      ))}
    </div>
  );
}
