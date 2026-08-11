import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../../lib/api/client";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { localInput } from "./calendarDates";

type Action = "cancel-occurrence" | "cancel-series" | "edit" | "split" | "dispute" | null;

export function CalendarOccurrencePanel({
  canManage,
  item,
  onClose,
  queryKey,
}: {
  canManage: boolean;
  item: CalendarOccurrence;
  onClose: () => void;
  queryKey: readonly unknown[];
}) {
  const { session } = useAuth();
  const client = useQueryClient();
  const [action, setAction] = useState<Action>(null);
  const [reason, setReason] = useState("");
  const [title, setTitle] = useState(item.title);
  const [notes, setNotes] = useState(item.notes ?? "Protected calendar detail.");
  const [startsAt, setStartsAt] = useState(localInput(new Date(item.startsAt)));
  const [endsAt, setEndsAt] = useState(localInput(new Date(item.endsAt)));
  const [until, setUntil] = useState(localInput(new Date(new Date(item.startsAt).getTime() + 7 * 86_400_000)));
  const ownsEvent = session?.user.id === item.subjectUserId && item.kind === "PERSONAL";
  const canChange = ownsEvent || (canManage && item.kind !== "PERSONAL");
  const pendingCommitment = session?.user.id === item.subjectUserId && item.kind === "COMMITMENT" && item.commitmentStatus === "PENDING";
  const mutation = useMutation({
    mutationFn: async (acknowledge?: boolean) => {
      if (!session) throw new Error("Sign in is required.");
      if (acknowledge !== undefined) return api.decideCalendarCommitment(item.eventId, { expectedVersion: item.version, reason: acknowledge ? null : reason }, acknowledge, session.csrfToken);
      if (action === "cancel-series") return api.cancelCalendarEvent(item.eventId, { expectedVersion: item.version, occurrenceStart: item.occurrenceStart, reason }, session.csrfToken);
      if (action === "cancel-occurrence") return api.cancelCalendarOccurrence(item.eventId, { expectedVersion: item.version, occurrenceStart: item.occurrenceStart, reason }, session.csrfToken);
      if (action === "edit") return api.editCalendarOccurrence(item.eventId, { expectedVersion: item.version, occurrenceStart: item.occurrenceStart, reason, title, notes, replacementStart: new Date(startsAt).toISOString(), replacementEnd: new Date(endsAt).toISOString() }, session.csrfToken);
      if (action === "split") return api.splitCalendarSeries(item.eventId, { expectedVersion: item.version, splitFrom: item.occurrenceStart, reason, title, notes, startsAt: new Date(startsAt).toISOString(), endsAt: new Date(endsAt).toISOString(), timeZone: item.timeZone, allDay: item.allDay, category: item.category, visibility: item.visibility, recurrence: item.recurrence, recurrenceInterval: 1, recurrenceUntil: new Date(until).toISOString() }, session.csrfToken);
      throw new Error("Select a calendar action.");
    },
    onSuccess: () => { void client.invalidateQueries({ queryKey }); onClose(); },
  });
  return (
    <aside aria-labelledby="calendar-detail-title" className="calendar-detail">
      <header><span>{item.category.replaceAll("_", " ")}</span><h2 id="calendar-detail-title">{item.title}</h2><button aria-label="Close calendar detail" onClick={onClose} type="button">×</button></header>
      <dl><div><dt>Person</dt><dd>{item.subjectDisplayName}</dd></div><div><dt>When</dt><dd>{formatPeriod(item)}</dd></div><div><dt>Visibility</dt><dd>{visibilityLabel(item.visibility)}</dd></div><div><dt>Response</dt><dd>{item.commitmentStatus.replaceAll("_", " ")}</dd></div></dl>
      {item.notes ? <p>{item.notes}</p> : <p>Detail is protected by the event owner’s privacy setting.</p>}
      {pendingCommitment ? <div className="calendar-detail__actions"><button className="button button--primary" disabled={mutation.isPending} onClick={() => mutation.mutate(true)} type="button">Acknowledge</button><button className="button" onClick={() => setAction("dispute")} type="button">Dispute</button></div> : null}
      {canChange ? <div className="calendar-detail__actions"><button className="button" onClick={() => setAction("edit")} type="button">Edit occurrence</button><button className="button" onClick={() => setAction("cancel-occurrence")} type="button">Cancel occurrence</button>{item.recurrence !== "NONE" ? <button className="button" onClick={() => setAction("split")} type="button">Change this and future</button> : null}<button className="button button--danger" onClick={() => setAction("cancel-series")} type="button">Cancel whole event</button></div> : null}
      {action ? <form className="calendar-detail__form" onSubmit={(event) => { event.preventDefault(); mutation.mutate(action === "dispute" ? false : undefined); }}>
        {action === "edit" || action === "split" ? <><label className="form-field">Title<span className="field-hint">Required</span><input minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></label><label className="form-field">Notes<span className="field-hint">Required</span><textarea onChange={(event) => setNotes(event.target.value)} required value={notes} /></label><label className="form-field">Starts<span className="field-hint">Required</span><input onChange={(event) => setStartsAt(event.target.value)} required type="datetime-local" value={startsAt} /></label><label className="form-field">Ends<span className="field-hint">Required</span><input min={startsAt} onChange={(event) => setEndsAt(event.target.value)} required type="datetime-local" value={endsAt} /></label>{action === "split" ? <label className="form-field">Repeat until<span className="field-hint">Required</span><input min={startsAt} onChange={(event) => setUntil(event.target.value)} required type="datetime-local" value={until} /></label> : null}</> : null}
        <label className="form-field">Reason<span className="field-hint">Required, 10–500 characters</span><textarea maxLength={500} minLength={10} onChange={(event) => setReason(event.target.value)} required value={reason} /></label>
        {mutation.isError ? <p className="form-banner form-banner--error" role="alert">{message(mutation.error)}</p> : null}
        <div className="calendar-detail__actions"><button className="button button--primary" disabled={mutation.isPending} type="submit">Confirm {label(action)}</button><button className="button" onClick={() => setAction(null)} type="button">Keep event</button></div>
      </form> : null}
    </aside>
  );
}

function label(action: Exclude<Action, null>) { return action.replaceAll("-", " "); }
function visibilityLabel(visibility: CalendarOccurrence["visibility"]) {
  return { PRIVATE: "Private appointment", AVAILABILITY_ONLY: "Time only", TEAM_DETAIL: "Visible to unit" }[visibility];
}
function formatPeriod(item: CalendarOccurrence) { const format = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: item.allDay ? undefined : "short" }); return `${format.format(new Date(item.startsAt))} to ${format.format(new Date(item.endsAt))}`; }
function message(error: Error) { return error instanceof ApiError ? error.message : error.message || "The calendar change could not be saved."; }
