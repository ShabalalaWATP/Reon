import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../../lib/api/client";
import type { CapacityPreview } from "../../lib/api/calendarTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";

export function CapacityPanel({ access }: { access: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  const today = new Date().toISOString().slice(0, 10);
  const later = new Date(Date.now() + 6 * 86_400_000).toISOString().slice(0, 10);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(later);
  const [timeZone, setTimeZone] = useState("Europe/London");
  const [preview, setPreview] = useState<CapacityPreview | null>(null);
  const canPlan = access.permissions.includes("CAPACITY") && Boolean(access.grantId);
  const previewMutation = useMutation({
    mutationFn: () => {
      if (!session || !access.grantId) throw new Error("Capacity authority is required.");
      return api.previewTeamCapacity(access.teamId, { grantId: access.grantId, dateFrom, dateTo, timeZone }, session.csrfToken);
    },
    onSuccess: setPreview,
  });
  const commitMutation = useMutation({
    mutationFn: () => {
      if (!session || !access.grantId || !preview) throw new Error("Create a current preview first.");
      return api.commitTeamCapacity(access.teamId, { grantId: access.grantId, token: preview.token }, session.csrfToken);
    },
    onSuccess: () => setPreview(null),
  });
  if (!canPlan) return null;
  return (
    <section className="capacity-panel">
      <header><span>Versioned availability</span><h2>Capacity snapshot</h2><p>Preview calendar-backed working minutes, then commit only if the source versions are unchanged.</p></header>
      <form onSubmit={(event) => { event.preventDefault(); previewMutation.mutate(); }}>
        <label className="form-field">From<span className="field-hint">Required</span><input onChange={(event) => setDateFrom(event.target.value)} required type="date" value={dateFrom} /></label>
        <label className="form-field">To<span className="field-hint">Required</span><input min={dateFrom} onChange={(event) => setDateTo(event.target.value)} required type="date" value={dateTo} /></label>
        <label className="form-field">Time zone<span className="field-hint">Required</span><select onChange={(event) => setTimeZone(event.target.value)} required value={timeZone}><option>Europe/London</option><option>Europe/Paris</option><option>America/New_York</option></select></label>
        {previewMutation.isError ? <p role="alert">{message(previewMutation.error)}</p> : null}
        <button className="button" disabled={previewMutation.isPending} type="submit">Preview capacity</button>
      </form>
      {preview ? <><div className="team-table-wrap"><table className="team-table"><caption>Calendar-backed capacity preview</caption><thead><tr><th scope="col">Date</th><th scope="col">People</th><th scope="col">Baseline</th><th scope="col">Unavailable</th><th scope="col">Available</th></tr></thead><tbody>{preview.days.map((day) => <tr key={day.date}><th scope="row">{day.date}</th><td>{day.memberCount}</td><td>{minutes(day.baselineMinutes)}</td><td>{minutes(day.unavailableMinutes)}</td><td>{minutes(day.availableMinutes)}</td></tr>)}</tbody></table></div>{commitMutation.isError ? <p role="alert">{message(commitMutation.error)}</p> : null}<button className="button button--primary" disabled={commitMutation.isPending} onClick={() => commitMutation.mutate()} type="button">Commit snapshot</button></> : null}
    </section>
  );
}

function minutes(value: number) { return `${Math.floor(value / 60)}h ${value % 60}m`; }
function message(error: Error) { return error instanceof ApiError ? error.message : error.message || "Capacity could not be calculated."; }
