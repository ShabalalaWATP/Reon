import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../../lib/api/client";
import type { CalendarCategory, CalendarEventInput, CalendarVisibility, RecurrenceFrequency } from "../../lib/api/calendarTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { localInput } from "./calendarDates";

type Mode = "personal" | "team" | "commitment";

export function CalendarEventForm({ access, members, range }: {
  access?: TeamWorkspaceAccess;
  members?: TeamMember[];
  range: { from: string; to: string };
}) {
  const { session } = useAuth();
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>(access ? "team" : "personal");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [startsAt, setStartsAt] = useState(() => localInput(new Date(Date.now() + 86_400_000)));
  const [endsAt, setEndsAt] = useState(() => localInput(new Date(Date.now() + 90_000_000)));
  const [timeZone, setTimeZone] = useState("Europe/London");
  const [allDay, setAllDay] = useState(false);
  const [category, setCategory] = useState<CalendarCategory>("OTHER");
  const [visibility, setVisibility] = useState<CalendarVisibility>(access ? "TEAM_DETAIL" : "PRIVATE");
  const [recurrence, setRecurrence] = useState<RecurrenceFrequency>("NONE");
  const [interval, setInterval] = useState(1);
  const [until, setUntil] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const canManage = Boolean(access?.grantId && access.permissions.includes("CALENDAR"));
  const mutation = useMutation({
    mutationFn: async () => {
      if (!session) throw new Error("Sign in is required.");
      const input: CalendarEventInput = {
        title,
        notes,
        startsAt: new Date(startsAt).toISOString(),
        endsAt: new Date(endsAt).toISOString(),
        timeZone,
        allDay,
        category,
        visibility,
        recurrence,
        recurrenceInterval: interval,
        recurrenceUntil: recurrence === "NONE" ? null : new Date(until).toISOString(),
      };
      if (!access) return api.createPersonalCalendarEvent(input, session.csrfToken);
      if (!access.grantId) throw new Error("Calendar management authority is required.");
      if (mode === "commitment") {
        if (!subjectId) throw new Error("Select an Analyst.");
        return api.createCalendarCommitment(access.teamId, { ...input, grantId: access.grantId, subjectUserId: subjectId }, session.csrfToken);
      }
      return api.createTeamCalendarEvent(access.teamId, { ...input, grantId: access.grantId }, session.csrfToken);
    },
    onSuccess: () => {
      setTitle(""); setNotes(""); setSubjectId("");
      const key = access
        ? protectedQueryKeys.teamCalendar(session?.user.id ?? "anonymous", access.teamId, range.from, range.to)
        : protectedQueryKeys.personalCalendar(session?.user.id ?? "anonymous", range.from, range.to);
      void client.invalidateQueries({ queryKey: key });
    },
  });
  if (access && !canManage) return null;
  const analysts = (members ?? []).filter((item) => item.state === "CURRENT" && item.role === "DELIVERY_SPECIALIST");
  return (
    <section className="calendar-form-panel">
      <header><span>Canonical event</span><h2>{access ? "Add to team calendar" : "Add personal event"}</h2><p>Every field is required. Shared views apply the selected privacy level before data leaves the service.</p></header>
      {access ? <div className="calendar-mode"><button aria-pressed={mode === "team"} onClick={() => setMode("team")} type="button">Team event</button><button aria-pressed={mode === "commitment"} onClick={() => setMode("commitment")} type="button">Personal commitment</button></div> : null}
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        {mode === "commitment" ? <label className="form-field">Analyst<span className="field-hint">Required</span><select onChange={(event) => setSubjectId(event.target.value)} required value={subjectId}><option value="">Select an Analyst</option>{analysts.map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}</option>)}</select></label> : null}
        <label className="form-field">Title<span className="field-hint">Required</span><input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></label>
        <label className="form-field">Notes<span className="field-hint">Required</span><textarea maxLength={2000} onChange={(event) => setNotes(event.target.value)} required rows={4} value={notes} /></label>
        <div className="calendar-form-grid"><label className="form-field">Starts<span className="field-hint">Required</span><input onChange={(event) => setStartsAt(event.target.value)} required type="datetime-local" value={startsAt} /></label><label className="form-field">Ends<span className="field-hint">Required</span><input min={startsAt} onChange={(event) => setEndsAt(event.target.value)} required type="datetime-local" value={endsAt} /></label></div>
        <div className="calendar-form-grid"><Select label="Category" onChange={(value) => setCategory(value as CalendarCategory)} options={["AVAILABILITY", "SERVICE_WORK", "LEAVE", "TRAINING", "DUTY", "APPOINTMENT", "OTHER"]} value={category} /><Select label="Privacy" onChange={(value) => setVisibility(value as CalendarVisibility)} options={["PRIVATE", "AVAILABILITY_ONLY", "TEAM_DETAIL"]} value={visibility} /></div>
        <div className="calendar-form-grid"><label className="form-field">Time zone<span className="field-hint">Required</span><select onChange={(event) => setTimeZone(event.target.value)} required value={timeZone}><option>Europe/London</option><option>Europe/Paris</option><option>America/New_York</option><option>Asia/Tokyo</option><option>Australia/Sydney</option></select></label><Select label="Repeats" onChange={(value) => setRecurrence(value as RecurrenceFrequency)} options={["NONE", "DAILY", "WEEKLY"]} value={recurrence} /></div>
        {recurrence !== "NONE" ? <div className="calendar-form-grid"><label className="form-field">Repeat interval<span className="field-hint">Required</span><input max={4} min={1} onChange={(event) => setInterval(Number(event.target.value))} required type="number" value={interval} /></label><label className="form-field">Repeat until<span className="field-hint">Required</span><input min={startsAt} onChange={(event) => setUntil(event.target.value)} required type="datetime-local" value={until} /></label></div> : null}
        <label className="calendar-check"><input checked={allDay} onChange={(event) => setAllDay(event.target.checked)} type="checkbox" />All-day activity</label>
        {mutation.isError ? <p className="form-banner form-banner--error" role="alert">{message(mutation.error)}</p> : null}
        <button className="button button--primary" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Saving…" : mode === "commitment" ? "Create commitment" : "Create event"}</button>
      </form>
    </section>
  );
}

function Select({ label, onChange, options, value }: { label: string; onChange: (value: string) => void; options: string[]; value: string }) {
  return <label className="form-field">{label}<span className="field-hint">Required</span><select onChange={(event) => onChange(event.target.value)} required value={value}>{options.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>;
}

function message(error: Error) { return error instanceof ApiError ? error.message : error.message || "The calendar event could not be saved."; }
