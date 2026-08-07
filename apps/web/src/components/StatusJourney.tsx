import { Check } from "lucide-react";

import type { RequestStatus } from "../lib/api/types";

const stages = [
  "Submitted",
  "JIOC routing",
  "Command routing",
  "Ops routing",
  "Product development",
  "QC review",
  "Disseminated",
];

const statusStage: Record<RequestStatus, number> = {
  ROUTING_PENDING: 0,
  TRIAGE_REVIEW: 1,
  INFORMATION_REQUIRED: 1,
  COORDINATION_REVIEW: 2,
  ON_HOLD: 2,
  ALLOCATION_REVIEW: 3,
  DELIVERY_PLANNING: 4,
  IN_PROGRESS: 4,
  CUSTOMER_INFORMATION_REQUIRED: 4,
  LEAD_REVIEW: 4,
  REWORK_REQUIRED: 4,
  QUALITY_REVIEW: 5,
  READY_FOR_RELEASE: 5,
  COMPLETED: 6,
  CLOSED_NOT_PROGRESSED: 1,
  CANCELLED: 0,
};

export function StatusJourney({ status }: { status: RequestStatus }) {
  const current = statusStage[status];
  return (
    <ol className="status-journey" aria-label="Request progress">
      {stages.map((stage, index) => {
        const state = index < current ? "complete" : index === current ? "current" : "upcoming";
        return (
          <li aria-current={state === "current" ? "step" : undefined} className={`journey-stage journey-stage--${state}`} key={stage}>
            <span aria-hidden="true">{state === "complete" ? <Check size={13} /> : index + 1}</span>
            <small>{stage}</small>
          </li>
        );
      })}
    </ol>
  );
}
