import type { TrackedRequest } from "../../lib/api/types";
import {
  journeyState,
  lifecycleLabels,
  lifecyclePhase,
  routePosition,
} from "./trackingPresentation";

export function TrackingJourney({ request }: { request: TrackedRequest }) {
  const currentPhase = lifecyclePhase(request.status);
  const currentRoute = routePosition(request.status, request.route.length);
  return (
    <section aria-label={`Request lifecycle for ${request.reference}`} className="tracking-journey">
      <div className="tracking-journey__route">
        <span>Organisational route</span>
        {request.route.length ? (
          <ol>
            {request.route.map((unit, index) => {
              const state = currentRoute >= request.route.length || index < currentRoute
                ? "complete"
                : index === currentRoute ? "current" : "upcoming";
              const stateLabel = state === "complete"
                ? "Routed"
                : state === "current" ? "Current route" : "Selected next";
              return <li data-state={state} key={unit.id}><i /><strong>{unit.name}</strong><small>{stateLabel}</small></li>;
            })}
          </ol>
        ) : <p>Waiting for the first routing decision.</p>}
      </div>
      <div className="tracking-journey__phases">
        <span>Delivery lifecycle</span>
        <ol>
          {lifecycleLabels(request.status).map((label, index) => {
            const state = journeyState(index, currentPhase);
            return <li data-state={state} key={label}><i /><strong>{label}</strong><small>{state === "current" ? "Now" : state === "complete" ? "Complete" : "Next"}</small></li>;
          })}
        </ol>
      </div>
    </section>
  );
}
