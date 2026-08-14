import type { TrackedRequest, User } from "../../lib/api/types";
import {
  journeyState,
  lifecycleDescription,
  lifecycleLabels,
  lifecyclePhase,
  routePosition,
} from "./trackingPresentation";

type JourneyViewer = Pick<User, "displayName" | "organisationUnitIds">;

export function TrackingJourney({
  request,
  viewer,
}: {
  request: TrackedRequest;
  viewer?: JourneyViewer;
}) {
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
          <div>
            <dt>Current owner</dt>
            <dd>{request.currentOwner ?? "Awaiting routing"}</dd>
          </div>
          <div>
            <dt>Next</dt>
            <dd>{nextLabel ?? "Journey complete"}</dd>
          </div>
        </dl>
      </header>
      <div className="tracking-journey__route">
        <div className="tracking-journey__label">
          <strong>Selected route</strong>
          <span>Where the request has travelled</span>
          {viewer ? <em>Viewing as {viewer.displayName}</em> : null}
        </div>
        <ol>
          <li className="tracking-route-origin" data-state="complete">
            <i aria-hidden="true" />
            <strong>Customer</strong>
            <small>Submitted request</small>
          </li>
          {request.route.length ? (
            request.route.map((unit, index) => {
              const state =
                currentRoute >= request.route.length || index < currentRoute
                  ? "complete"
                  : index === currentRoute
                    ? "current"
                    : "upcoming";
              const viewerUnit = viewer?.organisationUnitIds.includes(unit.id) ?? false;
              const stateLabel =
                state === "complete"
                  ? "Routed"
                  : state === "current"
                    ? "Current route"
                    : "Selected next";
              return (
                <li data-state={state} data-viewer={viewerUnit || undefined} key={unit.id}>
                  <i aria-hidden="true" />
                  <strong>{unit.name}</strong>
                  <small>{stateLabel}</small>
                  {viewerUnit ? <em>Your unit</em> : null}
                </li>
              );
            })
          ) : (
            <li className="tracking-route-pending">
              <strong>Routing decision</strong>
              <small>Waiting for the first routing decision.</small>
            </li>
          )}
          <li aria-current="location" className="tracking-route-now">
            <i aria-hidden="true" />
            <strong>{request.currentOwner ?? "Awaiting routing"}</strong>
            <small>Now · Current owner</small>
          </li>
        </ol>
      </div>
      <div className="tracking-journey__phases">
        <div className="tracking-journey__label">
          <strong>Delivery progress</strong>
          <span>What has happened and what comes next</span>
        </div>
        <ol>
          {labels.map((label, index) => {
            const state = journeyState(index, currentPhase);
            const stateLabel =
              state === "current" ? "Now" : state === "complete" ? "Complete" : "Next";
            return (
              <li
                aria-current={state === "current" ? "step" : undefined}
                data-state={state}
                key={label}
              >
                <i aria-hidden="true">{state === "complete" ? "✓" : index + 1}</i>
                <div>
                  <strong>{label}</strong>
                  <small>{lifecycleDescription(request.status, index)}</small>
                </div>
                <em>{stateLabel}</em>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
