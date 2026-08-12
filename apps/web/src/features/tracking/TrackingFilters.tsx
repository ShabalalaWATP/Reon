import type { OrganisationUnit, TrackedRequestFilters } from "../../lib/api/types";
import { trackingStatusLabel } from "../../lib/status";

const statuses = [
  "ROUTING_PENDING",
  "TRIAGE_REVIEW",
  "COORDINATION_REVIEW",
  "ALLOCATION_REVIEW",
  "DELIVERY_PLANNING",
  "IN_PROGRESS",
  "LEAD_REVIEW",
  "QUALITY_REVIEW",
  "READY_FOR_RELEASE",
  "COMPLETED",
  "ON_HOLD",
  "CANCELLED",
  "CLOSED_NOT_PROGRESSED",
] as const;

type Props = {
  applied: TrackedRequestFilters;
  draft: TrackedRequestFilters;
  onApply: () => void;
  onChange: (value: TrackedRequestFilters) => void;
  onClear: () => void;
  units: OrganisationUnit[];
};

export function TrackingFilters({ applied, draft, onApply, onChange, onClear, units }: Props) {
  const active = Object.values(applied).some(Boolean);
  return (
    <details className="tracking-filters">
      <summary>Filter monitored requests{active ? " · Active" : ""}</summary>
      <form onSubmit={(event) => { event.preventDefault(); onApply(); }}>
        <label className="form-field"><span>Reference or title</span><input maxLength={160} onChange={(event) => onChange({ ...draft, search: event.target.value })} value={draft.search} /></label>
        <label className="form-field"><span>Status</span><select onChange={(event) => onChange({ ...draft, status: event.target.value as TrackedRequestFilters["status"] })} value={draft.status}><option value="">All statuses</option>{statuses.map((status) => <option key={status} value={status}>{trackingStatusLabel(status)}</option>)}</select></label>
        <label className="form-field"><span>Current owner</span><input maxLength={120} onChange={(event) => onChange({ ...draft, currentOwner: event.target.value })} value={draft.currentOwner} /></label>
        <label className="form-field"><span>Route destination</span><select onChange={(event) => onChange({ ...draft, routeUnitId: event.target.value })} value={draft.routeUnitId}><option value="">Anywhere on route</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label>
        <label className="form-field"><span>Open for at least</span><select onChange={(event) => onChange({ ...draft, minimumAgeDays: event.target.value })} value={draft.minimumAgeDays}><option value="">Any age</option><option value="1">1 day</option><option value="3">3 days</option><option value="7">7 days</option><option value="14">14 days</option><option value="30">30 days</option></select></label>
        <div className="tracking-filter-actions"><button className="button button--primary" type="submit">Apply filters</button><button className="button button--quiet" disabled={!active && !Object.values(draft).some(Boolean)} onClick={onClear} type="button">Clear</button></div>
      </form>
    </details>
  );
}
