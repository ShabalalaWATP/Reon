import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import "../../styles/teams.css";
import "../../styles/board.css";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { CalendarEventForm } from "./CalendarEventForm";
import { CalendarOccurrencePanel } from "./CalendarOccurrencePanel";
import { CalendarViews } from "./CalendarViews";
import { CapacityPanel } from "./CapacityPanel";
import { calendarRange, calendarTitle, moveAnchor, type CalendarView } from "./calendarDates";

const validViews: CalendarView[] = ["month", "week", "agenda"];

export function CalendarPage({ access }: { access?: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  const params = useParams();
  const initialView = validViews.includes(params.calendarView as CalendarView) ? params.calendarView as CalendarView : "month";
  const [view, setView] = useState<CalendarView>(initialView);
  const [anchor, setAnchor] = useState(() => new Date());
  const [selected, setSelected] = useState<CalendarOccurrence | null>(null);
  const [draftDate, setDraftDate] = useState<Date | null>(null);
  const [creating, setCreating] = useState(false);
  const range = calendarRange(anchor, view);
  const userId = session?.user.id ?? "anonymous";
  const queryKey = access
    ? protectedQueryKeys.teamCalendar(userId, access.teamId, range.from, range.to)
    : protectedQueryKeys.personalCalendar(userId, range.from, range.to);
  const query = useQuery({
    queryKey,
    queryFn: () => access ? api.teamCalendar(access.teamId, range.from, range.to) : api.personalCalendar(range.from, range.to),
  });
  const canManage = Boolean(access?.grantId && access.permissions.includes("CALENDAR"));
  const people = useQuery({
    queryKey: protectedQueryKeys.teamPeople(userId, access?.teamId),
    queryFn: () => api.teamPeople(access?.teamId ?? ""),
    enabled: canManage,
  });
  const openEventForm = (day: Date) => { setDraftDate(day); setCreating(true); };
  return (
    <div className={`calendar-page${access ? " calendar-page--embedded" : ""}`}>
      {!access ? <header className="page-heading" role="group"><span>Personal workspace</span><h1>My calendar</h1><p>Plan private time, availability and recurring delivery activity from one canonical record.</p></header> : null}
      <section aria-label="Calendar controls" className="calendar-toolbar">
        <div><button aria-label="Previous calendar period" onClick={() => setAnchor(moveAnchor(anchor, view, -1))} type="button">‹</button><button onClick={() => setAnchor(new Date())} type="button">Today</button><button aria-label="Next calendar period" onClick={() => setAnchor(moveAnchor(anchor, view, 1))} type="button">›</button></div>
        <h2>{calendarTitle(anchor, view)}</h2>
        <div className="calendar-toolbar__actions"><button className="calendar-toolbar__add" onClick={() => openEventForm(anchor)} type="button">Add event</button><div aria-label="Calendar view" className="calendar-view-switch">{validViews.map((item) => <button aria-pressed={view === item} key={item} onClick={() => setView(item)} type="button">{item}</button>)}</div></div>
      </section>
      {query.isPending ? <PageState kind="loading" title="Loading calendar" /> : null}
      {query.isError ? <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Calendar could not be loaded" /> : null}
      {query.data ? <CalendarViews anchor={anchor} items={query.data.items} onCreate={openEventForm} onSelect={setSelected} view={view} /> : null}
      <div className="calendar-support-grid calendar-support-grid--single">
        {access && canManage && access.unitKind !== "ROOT" && access.unitKind !== "COMMAND" && access.unitKind !== "OPS_GROUP" ? <CapacityPanel access={access} /> : <CalendarPrivacy />}
      </div>
      <ModalDrawer label="Add calendar event" onClose={() => setCreating(false)} open={creating} variant="dialog"><CalendarEventForm access={access} initialDate={draftDate} members={people.data?.items} onCreated={() => setCreating(false)} range={range} /></ModalDrawer>
      {selected ? <CalendarOccurrencePanel canManage={canManage} item={selected} key={`${selected.eventId}:${selected.occurrenceStart}`} onClose={() => setSelected(null)} queryKey={queryKey} /> : null}
    </div>
  );
}

function CalendarPrivacy() {
  return <section className="calendar-privacy"><span>Privacy at source</span><h2>One event, bounded views</h2><p>Private and availability-only details are redacted before a shared calendar response is created. Team-detail events remain visible to the current team.</p><ul><li>Private: you retain the full detail.</li><li>Availability only: shared views receive a busy period.</li><li>Team detail: your current team can see the title and notes.</li></ul></section>;
}
