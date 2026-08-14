import type { ReactNode } from "react";

import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { CalendarOccurrenceActionForm } from "./CalendarOccurrenceActionForm";
import type { CalendarOccurrenceAction } from "./calendarOccurrenceModel";
import { useCalendarOccurrence } from "./useCalendarOccurrence";

type PanelProps = {
  canManage: boolean;
  item: CalendarOccurrence;
  onClose: () => void;
  queryKey: readonly unknown[];
};

export function CalendarOccurrencePanel(props: PanelProps) {
  const controller = useCalendarOccurrence(props);
  return (
    <aside aria-labelledby="calendar-detail-title" className="calendar-detail">
      <OccurrenceHeader item={props.item} onClose={props.onClose} />
      <OccurrenceSummary item={props.item} />
      <OccurrenceNotes item={props.item} />
      <CommitmentActions
        acknowledge={controller.acknowledge}
        pending={controller.mutation.isPending}
        pendingCommitment={controller.pendingCommitment}
        selectAction={controller.selectAction}
      />
      <EventActions
        canChange={controller.canChange}
        item={props.item}
        selectAction={controller.selectAction}
      />
      <CalendarOccurrenceActionForm
        draft={controller.draft}
        error={controller.mutation.error}
        pending={controller.mutation.isPending}
        selectAction={controller.selectAction}
        submit={controller.submit}
        update={controller.update}
      />
    </aside>
  );
}

function OccurrenceHeader({ item, onClose }: { item: CalendarOccurrence; onClose: () => void }) {
  return (
    <header>
      <span>{item.category.replaceAll("_", " ")}</span>
      <h2 id="calendar-detail-title">{item.title}</h2>
      <button aria-label="Close calendar detail" onClick={onClose} type="button">
        ×
      </button>
    </header>
  );
}

function OccurrenceSummary({ item }: { item: CalendarOccurrence }) {
  return (
    <dl>
      <div>
        <dt>Person</dt>
        <dd>{item.subjectDisplayName}</dd>
      </div>
      <div>
        <dt>When</dt>
        <dd>{formatPeriod(item)}</dd>
      </div>
      <div>
        <dt>Visibility</dt>
        <dd>{visibilityLabel(item.visibility)}</dd>
      </div>
      <div>
        <dt>Response</dt>
        <dd>{item.commitmentStatus.replaceAll("_", " ")}</dd>
      </div>
    </dl>
  );
}

function OccurrenceNotes({ item }: { item: CalendarOccurrence }) {
  return item.notes ? (
    <p>{item.notes}</p>
  ) : (
    <p>Detail is protected by the event owner’s privacy setting.</p>
  );
}

function CommitmentActions({
  acknowledge,
  pending,
  pendingCommitment,
  selectAction,
}: {
  acknowledge: () => void;
  pending: boolean;
  pendingCommitment: boolean;
  selectAction: (action: CalendarOccurrenceAction) => void;
}) {
  if (!pendingCommitment) return null;
  return (
    <div className="calendar-detail__actions">
      <button
        className="button button--primary"
        disabled={pending}
        onClick={acknowledge}
        type="button"
      >
        Acknowledge
      </button>
      <button className="button" onClick={() => selectAction("dispute")} type="button">
        Dispute
      </button>
    </div>
  );
}

function EventActions({
  canChange,
  item,
  selectAction,
}: {
  canChange: boolean;
  item: CalendarOccurrence;
  selectAction: (action: CalendarOccurrenceAction) => void;
}) {
  if (!canChange) return null;
  return (
    <div className="calendar-detail__actions">
      <ActionButton action="edit" onSelect={selectAction}>
        Edit occurrence
      </ActionButton>
      <ActionButton action="cancel-occurrence" onSelect={selectAction}>
        Cancel occurrence
      </ActionButton>
      {item.recurrence !== "NONE" ? (
        <ActionButton action="split" onSelect={selectAction}>
          Change this and future
        </ActionButton>
      ) : null}
      <ActionButton action="cancel-series" danger onSelect={selectAction}>
        Cancel whole event
      </ActionButton>
    </div>
  );
}

function ActionButton({
  action,
  children,
  danger = false,
  onSelect,
}: {
  action: Exclude<CalendarOccurrenceAction, null>;
  children: ReactNode;
  danger?: boolean;
  onSelect: (action: CalendarOccurrenceAction) => void;
}) {
  return (
    <button
      className={danger ? "button button--danger" : "button"}
      onClick={() => onSelect(action)}
      type="button"
    >
      {children}
    </button>
  );
}

function visibilityLabel(visibility: CalendarOccurrence["visibility"]) {
  return {
    AVAILABILITY_ONLY: "Time only",
    PRIVATE: "Private appointment",
    TEAM_DETAIL: "Visible to unit",
  }[visibility];
}

function formatPeriod(item: CalendarOccurrence) {
  const format = new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: item.allDay ? undefined : "short",
  });
  return `${format.format(new Date(item.startsAt))} to ${format.format(new Date(item.endsAt))}`;
}
