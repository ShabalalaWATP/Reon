import { Link } from "react-router";

import "../../styles/teams.css";
import "../../styles/board.css";
import "../../styles/calendar.css";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { CalendarEventForm } from "./CalendarEventForm";
import { CalendarOccurrencePanel } from "./CalendarOccurrencePanel";
import { CalendarViews } from "./CalendarViews";
import { CapacityPanel } from "./CapacityPanel";
import { calendarTitle, type CalendarView } from "./calendarDates";
import { useCalendarPage, validCalendarViews } from "./useCalendarPage";

export function CalendarPage({ access }: { access?: TeamWorkspaceAccess }) {
  const page = useCalendarPage(access);
  return (
    <div className={`calendar-page${access ? " calendar-page--embedded" : ""}`}>
      <PersonalCalendarHeader access={access} personalWorkspace={page.personalWorkspace} />
      <CalendarToolbar
        anchor={page.anchor}
        move={page.move}
        onCreate={page.openCreate}
        setToday={page.setToday}
        setView={page.setView}
        view={page.view}
      />
      <CalendarQueryState
        anchor={page.anchor}
        data={page.calendar.data?.items}
        error={page.calendar.isError}
        onCreate={page.openCreate}
        onRetry={() => void page.calendar.refetch()}
        onSelect={page.selectOccurrence}
        pending={page.calendar.isPending}
        view={page.view}
      />
      <CalendarSupport
        access={access}
        canManage={page.canManage}
        sharingUnitName={page.sharingUnitName}
      />
      <ModalDrawer
        label="Add calendar event"
        onClose={page.closeCreate}
        open={page.creating}
        variant="dialog"
      >
        <CalendarEventForm
          access={access}
          initialDate={page.draftDate}
          members={page.people}
          onCreated={page.closeCreate}
          range={page.range}
          sharingUnitName={page.sharingUnitName}
        />
      </ModalDrawer>
      <SelectedOccurrence
        canManage={page.canManage}
        item={page.selected}
        onClose={page.closeSelected}
        queryKey={page.queryKey}
      />
    </div>
  );
}

function PersonalCalendarHeader({
  access,
  personalWorkspace,
}: {
  access?: TeamWorkspaceAccess;
  personalWorkspace?: TeamWorkspaceAccess;
}) {
  if (access) return null;
  return (
    <header className="page-heading" role="group">
      <span>Personal schedule</span>
      <h1>Personal calendar</h1>
      <p>{personalCalendarDescription(personalWorkspace)}</p>
      {personalWorkspace ? (
        <Link className="button" to={`/teams/${personalWorkspace.teamId}/calendar`}>
          Open {personalWorkspace.teamName} calendar
        </Link>
      ) : null}
    </header>
  );
}

function CalendarToolbar({
  anchor,
  move,
  onCreate,
  setToday,
  setView,
  view,
}: {
  anchor: Date;
  move: (direction: -1 | 1) => void;
  onCreate: (day: Date) => void;
  setToday: () => void;
  setView: (view: CalendarView) => void;
  view: CalendarView;
}) {
  return (
    <section aria-label="Calendar controls" className="calendar-toolbar">
      <div>
        <button aria-label="Previous calendar period" onClick={() => move(-1)} type="button">
          ‹
        </button>
        <button onClick={setToday} type="button">
          Today
        </button>
        <button aria-label="Next calendar period" onClick={() => move(1)} type="button">
          ›
        </button>
      </div>
      <h2>{calendarTitle(anchor, view)}</h2>
      <div className="calendar-toolbar__actions">
        <button className="calendar-toolbar__add" onClick={() => onCreate(anchor)} type="button">
          Add event
        </button>
        <div aria-label="Calendar view" className="calendar-view-switch">
          {validCalendarViews.map((candidate) => (
            <button
              aria-pressed={view === candidate}
              key={candidate}
              onClick={() => setView(candidate)}
              type="button"
            >
              {candidate}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

type CalendarQueryStateProps = {
  anchor: Date;
  data?: CalendarOccurrence[];
  error: boolean;
  onCreate: (day: Date) => void;
  onRetry: () => void;
  onSelect: (item: CalendarOccurrence) => void;
  pending: boolean;
  view: CalendarView;
};

function CalendarQueryState(props: CalendarQueryStateProps) {
  return (
    <>
      {props.pending ? <PageState kind="loading" title="Loading calendar" /> : null}
      {props.error ? (
        <PageState
          action={
            <button className="button" onClick={props.onRetry}>
              Try again
            </button>
          }
          kind="error"
          title="Calendar could not be loaded"
        />
      ) : null}
      {props.data ? (
        <CalendarViews
          anchor={props.anchor}
          items={props.data}
          onCreate={props.onCreate}
          onSelect={props.onSelect}
          view={props.view}
        />
      ) : null}
    </>
  );
}

function CalendarSupport({
  access,
  canManage,
  sharingUnitName,
}: {
  access?: TeamWorkspaceAccess;
  canManage: boolean;
  sharingUnitName?: string;
}) {
  const showCapacity =
    access &&
    canManage &&
    access.unitKind !== "ROOT" &&
    access.unitKind !== "COMMAND" &&
    access.unitKind !== "OPS_GROUP";
  return (
    <div className="calendar-support-grid calendar-support-grid--single">
      {showCapacity ? (
        <CapacityPanel access={access} />
      ) : (
        <CalendarPrivacy sharingUnitName={sharingUnitName} />
      )}
    </div>
  );
}

function SelectedOccurrence({
  canManage,
  item,
  onClose,
  queryKey,
}: {
  canManage: boolean;
  item: CalendarOccurrence | null;
  onClose: () => void;
  queryKey: readonly unknown[];
}) {
  if (!item) return null;
  return (
    <CalendarOccurrencePanel
      canManage={canManage}
      item={item}
      key={`${item.eventId}:${item.occurrenceStart}`}
      onClose={onClose}
      queryKey={queryKey}
    />
  );
}

function CalendarPrivacy({ sharingUnitName }: { sharingUnitName?: string }) {
  return (
    <section className="calendar-privacy">
      <span>Visibility at source</span>
      <h2>Clear by default, private by choice</h2>
      <p>{privacyDescription(sharingUnitName)}</p>
      <ul>
        <li>Visible to unit: current colleagues see the event detail.</li>
        <li>Private appointment: colleagues see only Busy and the time.</li>
        <li>Existing time-only events keep their original protection.</li>
      </ul>
    </section>
  );
}

function personalCalendarDescription(personalWorkspace?: TeamWorkspaceAccess) {
  if (personalWorkspace) {
    return `Events you add here also appear in the ${personalWorkspace.teamName} calendar. Details are shared unless you mark an appointment as private.`;
  }
  return "Plan your own availability and recurring activity. If you join a workspace, active events will also appear in its team calendar.";
}

function privacyDescription(sharingUnitName?: string) {
  if (sharingUnitName) {
    return `${sharingUnitName} can normally see the title, category and notes for personal calendar activity. Select Private appointment when those details should be hidden.`;
  }
  return "This account has no current workspace, so its events remain on the personal calendar. If the account joins a workspace, active events will follow the visibility selected here.";
}
