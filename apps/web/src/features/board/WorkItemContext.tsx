import type { WorkPackage } from "../../lib/api/boardTypes";
import type { RequestDetail } from "../../lib/api/types";

export function RequestContext({ value }: { value: RequestDetail }) {
  const openClarifications = value.clarifications.filter((item) => item.status === "OPEN");
  return (
    <div className="work-inspector__sections">
      {value.status === "CUSTOMER_INFORMATION_REQUIRED" ? (
        <section className="inspector-attention">
          <h3>Waiting for customer information</h3>
          <p>
            {openClarifications.length} clarification request
            {openClarifications.length === 1 ? " is" : "s are"} currently open.
          </p>
        </section>
      ) : null}
      <section>
        <h3>Customer requirement</h3>
        <dl>
          <div>
            <dt>Customer</dt>
            <dd>{value.requester.displayName}</dd>
          </div>
          <div>
            <dt>Question</dt>
            <dd>{value.questionToAnswer}</dd>
          </div>
          <div>
            <dt>Outcome</dt>
            <dd>{value.desiredOutcome}</dd>
          </div>
          <div>
            <dt>Success</dt>
            <dd>{value.successCriteria}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>Delivery context</h3>
        <dl>
          <div>
            <dt>Team</dt>
            <dd>{value.assignedDeliveryTeam ?? "Routing in progress"}</dd>
          </div>
          <div>
            <dt>Lead</dt>
            <dd>{value.assignedSpecialist?.displayName ?? "Unassigned"}</dd>
          </div>
          <div>
            <dt>Contributors</dt>
            <dd>{value.contributors.map((item) => item.displayName).join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Preferred product</dt>
            <dd>{value.preferredDeliverableType}</dd>
          </div>
        </dl>
      </section>
      {openClarifications.map((thread) => (
        <section key={thread.id}>
          <h3>Clarification {thread.sequence}</h3>
          <p>{thread.question}</p>
          <small>
            Response requested by {new Date(thread.responseDeadline).toLocaleString("en-GB")}
          </small>
        </section>
      ))}
    </div>
  );
}

export function PackageContext({
  packages,
  value,
}: {
  packages: WorkPackage[];
  value: WorkPackage;
}) {
  const activeReservations = value.reservations.filter((item) => item.status === "ACTIVE");
  return (
    <div className="work-inspector__sections">
      <section>
        <h3>Package detail</h3>
        <p>{value.description}</p>
        <dl>
          <div>
            <dt>Estimate</dt>
            <dd>{value.estimatePoints} points</dd>
          </div>
          <div>
            <dt>Remaining</dt>
            <dd>{value.remainingEffortMinutes} minutes</dd>
          </div>
          <div>
            <dt>Contributors</dt>
            <dd>{value.contributors.map((item) => item.displayName).join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Iteration</dt>
            <dd>{value.iterationId ?? "Not assigned"}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>Acceptance and blockers</h3>
        <p>
          <strong>Acceptance:</strong> {value.acceptanceCriteria}
        </p>
        <p>
          <strong>Blockers:</strong> {value.blockers}
        </p>
      </section>
      <section>
        <h3>Dependencies</h3>
        {value.dependencyIds.length ? (
          <ul>
            {value.dependencyIds.map((id) => (
              <li key={id}>{packages.find((item) => item.id === id)?.title ?? id}</li>
            ))}
          </ul>
        ) : (
          <p>No dependencies recorded.</p>
        )}
      </section>
      <section>
        <h3>Reserved capacity</h3>
        {activeReservations.length ? (
          <ul>
            {activeReservations.map((item) => (
              <li key={item.id}>
                {item.userDisplayName}: {item.minutes} minutes,{" "}
                {new Date(item.startsAt).toLocaleString("en-GB")}
              </li>
            ))}
          </ul>
        ) : (
          <p>No active reservations.</p>
        )}
      </section>
      <section>
        <h3>Recent package activity</h3>
        {value.activities.length ? (
          <ol>
            {value.activities.slice(0, 8).map((activity) => (
              <li key={activity.id}>
                {activity.summary} · {activity.actorDisplayName}
              </li>
            ))}
          </ol>
        ) : (
          <p>No activity recorded.</p>
        )}
      </section>
    </div>
  );
}
