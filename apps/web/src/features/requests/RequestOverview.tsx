import type { RequestDetail } from "../../lib/api/types";
import { elapsedTime, requiredDateSignal } from "../../lib/serviceTiming";
import { formatDate, isComplete } from "../../lib/status";
import { ClarificationHistory } from "./ClarificationHistory";

export function RequestOverview({ request }: { request: RequestDetail }) {
  const required = requiredDateSignal(request.requiredBy);
  const completed = isComplete(request.status);
  return (
    <section className="detail-section" aria-labelledby="overview-title">
      <div className="section-heading">
        <span>Submitted request</span>
        <h2 id="overview-title">Request details</h2>
      </div>
      <dl className="overview-grid">
        <div>
          <dt>Required by</dt>
          <dd>
            {formatDate(request.requiredBy)}
            <small className={`required-signal required-signal--${required.tone}`}>
              {required.label}
            </small>
          </dd>
        </div>
        <div>
          <dt>Customer urgency</dt>
          <dd>{request.customerUrgency.replace("_", " ").toLowerCase()}</dd>
        </div>
        <div>
          <dt>Relevant period</dt>
          <dd>
            {request.coverageStart} to {request.coverageEnd}
          </dd>
        </div>
        <div>
          <dt>Product format</dt>
          <dd>{request.preferredDeliverableType}</dd>
        </div>
        <div>
          <dt>Current owner</dt>
          <dd>{request.currentOwner ?? "Awaiting assignment"}</dd>
        </div>
        <div>
          <dt>Assigned team</dt>
          <dd>{request.assignedDeliveryTeam ?? "Not allocated"}</dd>
        </div>
        <div>
          <dt>Lead Analyst</dt>
          <dd>
            {request.assignedSpecialist?.displayName ?? "Not assigned"}
            <small>Same working controls as every assigned Analyst</small>
          </dd>
        </div>
        <div>
          <dt>Assigned Analysts</dt>
          <dd>
            {request.contributors.length
              ? request.contributors.map((item) => item.displayName).join(", ")
              : "No additional Analysts"}
          </dd>
        </div>
        <div>
          <dt>Sensitivity</dt>
          <dd>{request.sensitivity.toLowerCase()}</dd>
        </div>
        <div>
          <dt>Service age</dt>
          <dd>
            {completed
              ? elapsedTime(request.createdAt, new Date(request.updatedAt))
              : elapsedTime(request.createdAt)}
          </dd>
        </div>
        <div>
          <dt>{completed ? "Service completed" : "With current owner"}</dt>
          <dd>
            {completed ? formatDate(request.updatedAt, true) : elapsedTime(request.updatedAt)}
          </dd>
        </div>
      </dl>
      <div className="narrative-list">
        <article>
          <h3>Description of the need</h3>
          <p>{request.description}</p>
        </article>
        <article>
          <h3>Desired outcome</h3>
          <p>{request.desiredOutcome}</p>
        </article>
        <article>
          <h3>Background and known context</h3>
          <p>{request.backgroundContext}</p>
        </article>
        <article>
          <h3>Question to answer</h3>
          <p>{request.questionToAnswer}</p>
        </article>
        <article>
          <h3>Subject area or location</h3>
          <p>{request.subjectAreaOrLocation}</p>
        </article>
        <article>
          <h3>Activity or decision supported</h3>
          <p>{request.supportedActivityOrDecision}</p>
        </article>
        <article>
          <h3>Why the date matters</h3>
          <p>{request.requiredByReason}</p>
        </article>
        <article>
          <h3>Success criteria</h3>
          <p>{request.successCriteria}</p>
        </article>
        <article>
          <h3>Constraints or caveats</h3>
          <p>{request.constraintsOrCaveats}</p>
        </article>
        <article>
          <h3>Supporting information</h3>
          <p>{request.supportingInformation}</p>
        </article>
        <article>
          <h3>Handling instructions</h3>
          <p>{request.handlingInstructions}</p>
        </article>
      </div>
      <ClarificationHistory threads={request.clarifications} />
    </section>
  );
}
