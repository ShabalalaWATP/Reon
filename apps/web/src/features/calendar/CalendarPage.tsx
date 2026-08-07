import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

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
  return (
    <div className={`calendar-page${access ? " calendar-page--embedded" : ""}`}>
      {!access ? <header className="page-heading" role="group"><span>Personal workspace</span><h1>My calendar</h1><p>Plan private time, availability and recurring delivery activity from one canonical record.</p></header> : null}
      <section aria-label="Calendar controls" className="calendar-toolbar">
        <div><button aria-label="Previous calendar period" onClick={() => setAnchor(moveAnchor(anchor, view, -1))} type="button">‹</button><button onClick={() => setAnchor(new Date())} type="button">Today</button><button aria-label="Next calendar period" onClick={() => setAnchor(moveAnchor(anchor, view, 1))} type="button">›</button></div>
        <h2>{calendarTitle(anchor, view)}</h2>
        <div aria-label="Calendar view" className="calendar-view-switch">{validViews.map((item) => <button aria-pressed={view === item} key={item} onClick={() => setView(item)} type="button">{item}</button>)}</div>
      </section>
      {query.isPending ? <PageState kind="loading" title="Loading calendar" /> : null}
      {query.isError ? <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Calendar could not be loaded" /> : null}
      {query.data ? <CalendarViews anchor={anchor} items={query.data.items} onSelect={setSelected} view={view} /> : null}
      <div className="calendar-support-grid">
        <CalendarEventForm access={access} members={people.data?.items} range={range} />
        {access ? <CapacityPanel access={access} /> : <CalendarPrivacy />}
      </div>
      {selected ? <CalendarOccurrencePanel canManage={canManage} item={selected} onClose={() => setSelected(null)} queryKey={queryKey} /> : null}
    </div>
  );
}

function CalendarPrivacy() {
  return <section className="calendar-privacy"><span>Privacy at source</span><h2>One event, bounded views</h2><p>Private and availability-only details are redacted before a shared calendar response is created. Team-detail events remain visible to the current team.</p><ul><li>Private: you retain the full detail.</li><li>Availability only: shared views receive a busy period.</li><li>Team detail: your current team can see the title and notes.</li></ul></section>;
}
