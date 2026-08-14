import type { RequestStatus } from "../lib/api/types";
import { statusLabels, statusTone } from "../lib/status";

export function StatusPill({ label, status }: { label?: string; status: RequestStatus }) {
  return (
    <span className={`status-pill status-pill--${statusTone(status)}`}>
      {label ?? statusLabels[status]}
    </span>
  );
}
