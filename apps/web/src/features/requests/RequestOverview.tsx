import type { RequestDetail } from "../../lib/api/types";
import { formatDate } from "../../lib/status";
import { ClarificationHistory } from "./ClarificationHistory";

export function RequestOverview({ request }: { request: RequestDetail }) {
  return (
    <section className="detail-section" aria-labelledby="overview-title">
      <div className="section-heading"><span>Submitted revision</span><h2 id="overview-title">Overview</h2></div>
      <dl className="overview-grid">
        <div><dt>Service category</dt><dd>{request.serviceCategory}</dd></div>
        <div><dt>Required by</dt><dd>{formatDate(request.requiredBy)}</dd></div>
        <div><dt>Business area</dt><dd>{request.requestingBusinessArea}</dd></div>
        <div><dt>Product format</dt><dd>{request.preferredDeliverableType}</dd></div>
        <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting assignment"}</dd></div>
        <div><dt>Assigned team</dt><dd>{request.assignedDeliveryTeam ?? "Not allocated"}</dd></div>
        <div><dt>Analyst</dt><dd>{request.assignedSpecialist?.displayName ?? "Not assigned"}</dd></div>
        <div><dt>Sensitivity</dt><dd>{request.sensitivity.toLowerCase()}</dd></div>
      </dl>
      <div className="narrative-list">
        <article><h3>Description of the need</h3><p>{request.description}</p></article>
        <article><h3>Desired outcome</h3><p>{request.desiredOutcome}</p></article>
        <article><h3>Background and known context</h3><p>{request.backgroundContext}</p></article>
        <article><h3>Why the date matters</h3><p>{request.requiredByReason}</p></article>
        <article><h3>Success criteria</h3><p>{request.successCriteria}</p></article>
        <article><h3>Intended recipients</h3><p>{request.intendedRecipients.join(", ")}</p></article>
        <article><h3>Handling instructions</h3><p>{request.handlingInstructions}</p></article>
      </div>
      <ClarificationHistory threads={request.clarifications} />
    </section>
  );
}
