import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError } from "../../lib/api/client";
import { boardApi } from "../../lib/api/boardClient";
import type { CalendarCategory, CalendarEventInput, CalendarVisibility, RecurrenceFrequency } from "../../lib/api/calendarTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { localInput } from "./calendarDates";

type Mode = "personal" | "team" | "commitment";

export function CalendarEventForm({ access, initialDate, members, onCreated, range }: {
  access?: TeamWorkspaceAccess;
  initialDate?: Date | null;
  members?: TeamMember[];
  onCreated?: () => void;
  range: { from: string; to: string };
}) {
  const { session } = useAuth();
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>("personal");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [startsAt, setStartsAt] = useState(() => localInput(new Date(Date.now() + 86_400_000)));
  const [endsAt, setEndsAt] = useState(() => localInput(new Date(Date.now() + 90_000_000)));
  const [timeZone, setTimeZone] = useState("Europe/London");
  const [allDay, setAllDay] = useState(false);
  const [category, setCategory] = useState<CalendarCategory>("OTHER");
  const [visibility, setVisibility] = useState<CalendarVisibility>(access ? "AVAILABILITY_ONLY" : "PRIVATE");
  const [recurrence, setRecurrence] = useState<RecurrenceFrequency>("NONE");
  const [interval, setInterval] = useState(1);
  const [until, setUntil] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [requestId, setRequestId] = useState("");
  const canManage = Boolean(access?.grantId && access.permissions.includes("CALENDAR"));
  const ticketCommitments = canManage && access?.unitKind === "TEAM";
  const requests = useQuery({
    queryKey: protectedQueryKeys.teamBoard(session?.user.id ?? "anonymous", access?.teamId ?? "", "calendar-commitments"),
    queryFn: () => boardApi.board(access?.teamId ?? "", { itemTypes: ["SERVICE_REQUEST"] }, { limit: 100 }),
    enabled: Boolean(access && ticketCommitments && mode === "commitment"),
  });
  useEffect(() => {
    if (!initialDate) return;
    const start = new Date(initialDate);
    start.setHours(9, 0, 0, 0);
    setStartsAt(localInput(start));
    setEndsAt(localInput(new Date(start.getTime() + 3_600_000)));
  }, [initialDate]);
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
      if (!access || mode === "personal") return api.createPersonalCalendarEvent(input, session.csrfToken);
      if (!access.grantId) throw new Error("Calendar management authority is required.");
      if (mode === "commitment") {
        if (!subjectId || !requestId) throw new Error("Select a request and an Analyst.");
        return api.createCalendarCommitment(access.teamId, { ...input, grantId: access.grantId, requestId, subjectUserId: subjectId }, session.csrfToken);
      }
      return api.createTeamCalendarEvent(access.teamId, { ...input, grantId: access.grantId }, session.csrfToken);
    },
    onSuccess: () => {
      setTitle(""); setNotes(""); setSubjectId(""); setRequestId("");
      const key = access
        ? protectedQueryKeys.teamCalendar(session?.user.id ?? "anonymous", access.teamId, range.from, range.to)
        : protectedQueryKeys.personalCalendar(session?.user.id ?? "anonymous", range.from, range.to);
      void client.invalidateQueries({ queryKey: key });
      onCreated?.();
    },
  });
  const analysts = (members ?? []).filter((item) => item.state === "CURRENT" && item.role === "DELIVERY_SPECIALIST");
  return (
    <section className="calendar-form-panel">
      <header><span>Canonical event</span><h2>{access ? "Add calendar activity" : "Add personal event"}</h2><p>Every member can record their own leave, courses, training and availability. Manager controls appear only where they apply.</p></header>
      {access ? <div className="calendar-mode"><button aria-pressed={mode === "personal"} onClick={() => { setMode("personal"); setVisibility("AVAILABILITY_ONLY"); }} type="button">My event</button>{canManage ? <button aria-pressed={mode === "team"} onClick={() => { setMode("team"); setVisibility("TEAM_DETAIL"); }} type="button">Unit event</button> : null}{ticketCommitments ? <button aria-pressed={mode === "commitment"} onClick={() => { setMode("commitment"); setVisibility("TEAM_DETAIL"); }} type="button">Ticket commitment</button> : null}</div> : null}
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        {mode === "commitment" ? <><label className="form-field">Service request<span className="field-hint">Required</span><select disabled={requests.isPending || requests.isError} onChange={(event) => setRequestId(event.target.value)} required value={requestId}><option value="">{requests.isPending ? "Loading current requests…" : requests.isError ? "Requests unavailable" : "Select a request"}</option>{requests.data?.items.filter((item) => item.itemType === "SERVICE_REQUEST").map((item) => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label><label className="form-field">Analyst<span className="field-hint">Required</span><select onChange={(event) => setSubjectId(event.target.value)} required value={subjectId}><option value="">Select an Analyst</option>{analysts.map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}</option>)}</select></label></> : null}
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
