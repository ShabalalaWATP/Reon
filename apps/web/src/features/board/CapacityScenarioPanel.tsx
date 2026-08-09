import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { planningEvolutionApi } from "../../lib/api/planningEvolutionClient";
import type {
  CapacityBreakdown,
  CapacityScenarioPreview,
  CapacityScenarioSummary,
} from "../../lib/api/planningEvolutionTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";

export function CapacityScenarioPanel({
  access,
  scenarios,
  session,
  sourceVersion,
}: {
  access: TeamWorkspaceAccess;
  scenarios: CapacityScenarioSummary[];
  session: Session;
  sourceVersion: number;
}) {
  const now = new Date();
  const today = localDateInputValue(now);
  const week = localDateInputValue(addLocalDays(now, 6));
  const [name, setName] = useState("");
  const [startsOn, setStartsOn] = useState(today);
  const [endsOn, setEndsOn] = useState(week);
  const [plannedHours, setPlannedHours] = useState("");
  const [preview, setPreview] = useState<CapacityScenarioPreview | null>(null);
  const grantId = access.grantId;
  const canPreview = Boolean(
    grantId
    && access.permissions.includes("BOARD")
    && access.permissions.includes("CAPACITY"),
  );
  const mutation = useMutation({
    mutationFn: () => planningEvolutionApi.previewScenario(access.teamId, {
      grantId: grantId ?? "",
      name,
      startsOn,
      endsOn,
      plannedMinutes: Math.round(Number(plannedHours) * 60),
      expectedSourceVersion: sourceVersion,
    }, session.csrfToken),
    onSuccess: setPreview,
  });
  return (
    <div className="planning-view planning-scenario-layout">
      <section className="planning-section">
        <header><h3>Capacity scenario history</h3><p>Versions preserve the assumptions a Manager reviewed.</p></header>
        {scenarios.length === 0 ? <p className="inline-empty">No scenarios have been recorded.</p> : (
          <div className="team-table-wrap"><table className="team-table"><caption>Team capacity scenarios</caption><thead><tr><th scope="col">Scenario</th><th scope="col">Window</th><th scope="col">State</th><th scope="col">Version</th></tr></thead><tbody>{scenarios.map((item) => <tr key={item.id}><th scope="row">{item.name}</th><td>{item.startsOn} to {item.endsOn}</td><td>{item.status}</td><td>{item.version}</td></tr>)}</tbody></table></div>
        )}
      </section>
      <section className="planning-section scenario-preview">
        <header><h3>Preview aggregate capacity</h3><p>Calendar availability, active request work and package reservations are combined without comparing Analysts.</p></header>
        {!canPreview ? <p className="inline-empty">A current exact-team board and capacity grant is required to preview scenarios.</p> : (
          <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
            <label className="form-field">Scenario name<span className="field-hint">Required</span><input minLength={3} onChange={(event) => setName(event.target.value)} required value={name} /></label>
            <div className="planning-form-grid">
              <label className="form-field">Starts<span className="field-hint">Required</span><input onChange={(event) => setStartsOn(event.target.value)} required type="date" value={startsOn} /></label>
              <label className="form-field">Ends<span className="field-hint">Required</span><input min={startsOn} onChange={(event) => setEndsOn(event.target.value)} required type="date" value={endsOn} /></label>
            </div>
            <label className="form-field">Planned team hours<span className="field-hint">Aggregate estimate</span><input min="0.5" onChange={(event) => setPlannedHours(event.target.value)} required step="0.5" type="number" value={plannedHours} /></label>
            <button className="button button--primary" disabled={mutation.isPending} type="submit">Preview scenario</button>
          </form>
        )}
        {mutation.isError ? <p role="alert">{errorMessage(mutation.error)}</p> : null}
        {preview ? <ScenarioResult preview={preview} /> : null}
      </section>
    </div>
  );
}

function ScenarioResult({ preview }: { preview: CapacityScenarioPreview }) {
  return (
    <div aria-live="polite" className="scenario-result">
      <p><strong>{preview.estimateLabel}</strong> · source v{preview.sourceVersion}</p>
      <div className="team-table-wrap"><table className="team-table"><caption>Capacity scenario comparison</caption><thead><tr><th scope="col">View</th><th scope="col">Available</th><th scope="col">Reserved</th><th scope="col">Request work</th><th scope="col">Package work</th><th scope="col">Net</th></tr></thead><tbody><BreakdownRow label="Baseline" value={preview.baseline} /><BreakdownRow label="Scenario" value={preview.scenario} /></tbody></table></div>
      {preview.conflicts.length === 0 ? <p className="scenario-clear">No capacity conflicts identified. A Manager must still decide any commitment.</p> : <ul className="scenario-conflicts">{preview.conflicts.map((item) => <li key={`${item.date}-${item.kind}-${item.summary}`}><strong>{item.kind}</strong><span>{item.date} · {item.summary}</span></li>)}</ul>}
    </div>
  );
}

function BreakdownRow({ label, value }: { label: string; value: CapacityBreakdown }) {
  return <tr><th scope="row">{label}</th><td>{hours(value.availableMinutes)}</td><td>{hours(value.reservedMinutes)}</td><td>{hours(value.requestWorkMinutes)}</td><td>{hours(value.packageMinutes)}</td><td>{hours(value.netMinutes)}</td></tr>;
}

function hours(value: number) { return `${(value / 60).toFixed(1)} h`; }
function errorMessage(error: Error) { return error.message; }
