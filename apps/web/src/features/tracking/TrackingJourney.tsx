import type { TrackedRequest } from "../../lib/api/types";
import {
  journeyState,
  lifecycleDescription,
  lifecycleLabels,
  lifecyclePhase,
  routePosition,
} from "./trackingPresentation";

export function TrackingJourney({ request }: { request: TrackedRequest }) {
  const currentPhase = lifecyclePhase(request.status);
  const currentRoute = routePosition(request.status, request.route.length);
  const labels = lifecycleLabels(request.status);
  const currentLabel = labels[currentPhase];
  const nextLabel = labels[currentPhase + 1];
  return (
    <section aria-label={`Request lifecycle for ${request.reference}`} className="tracking-journey">
      <header className="tracking-journey__current">
        <div>
          <span>Current position</span>
          <strong>{currentLabel}</strong>
        </div>
        <dl>
          <div><dt>Current owner</dt><dd>{request.currentOwner ?? "Awaiting routing"}</dd></div>
          <div><dt>Next</dt><dd>{nextLabel ?? "Journey complete"}</dd></div>
        </dl>
      </header>
      <div className="tracking-journey__route">
        <div className="tracking-journey__label"><strong>Selected route</strong><span>Where the request has travelled</span></div>
        {request.route.length ? (
          <ol>
            {request.route.map((unit, index) => {
              const state = currentRoute >= request.route.length || index < currentRoute
                ? "complete"
                : index === currentRoute ? "current" : "upcoming";
              const stateLabel = state === "complete"
                ? "Routed"
                : state === "current" ? "Current route" : "Selected next";
              return <li data-state={state} key={unit.id}><i aria-hidden="true" /><strong>{unit.name}</strong><small>{stateLabel}</small></li>;
            })}
          </ol>
        ) : <p>Waiting for the first routing decision.</p>}
      </div>
      <div className="tracking-journey__phases">
        <div className="tracking-journey__label"><strong>Delivery progress</strong><span>What has happened and what comes next</span></div>
        <ol>
          {labels.map((label, index) => {
            const state = journeyState(index, currentPhase);
            const stateLabel = state === "current" ? "Now" : state === "complete" ? "Complete" : "Next";
            return (
              <li aria-current={state === "current" ? "step" : undefined} data-state={state} key={label}>
                <i aria-hidden="true">{state === "complete" ? "✓" : index + 1}</i>
                <div><strong>{label}</strong><small>{lifecycleDescription(request.status, index)}</small></div>
                <em>{stateLabel}</em>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
