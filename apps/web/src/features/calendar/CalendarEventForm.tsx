import type { ReactNode } from "react";

import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { CalendarEventFields } from "./CalendarEventFields";
import type { CalendarEventMode } from "./calendarEventModel";
import { useCalendarEventForm } from "./useCalendarEventForm";

type CalendarEventFormProps = {
  access?: TeamWorkspaceAccess;
  initialDate?: Date | null;
  members?: TeamMember[];
  onCreated?: () => void;
  range: { from: string; to: string };
  sharingUnitName?: string;
};

export function CalendarEventForm(props: CalendarEventFormProps) {
  const controller = useCalendarEventForm(props);
  return (
    <section className="calendar-form-panel">
      <FormHeader hasWorkspace={Boolean(props.access)} />
      <ModeSelector
        canManage={controller.canManage}
        hasWorkspace={Boolean(props.access)}
        mode={controller.draft.mode}
        onSelect={controller.selectMode}
        ticketCommitments={controller.ticketCommitments}
      />
      <CalendarEventFields
        analysts={controller.analysts}
        draft={controller.draft}
        mutation={controller.mutation}
        requests={controller.requests}
        sharingAudience={props.access?.teamName ?? props.sharingUnitName}
        submit={controller.submit}
        update={controller.update}
      />
    </section>
  );
}

function FormHeader({ hasWorkspace }: { hasWorkspace: boolean }) {
  return (
    <header>
      <span>Canonical event</span>
      <h2>{hasWorkspace ? "Add calendar activity" : "Add personal event"}</h2>
      <p>
        Every account can record its own leave, courses, training and availability. Manager controls
        appear only where they apply.
      </p>
    </header>
  );
}

function ModeSelector({
  canManage,
  hasWorkspace,
  mode,
  onSelect,
  ticketCommitments,
}: {
  canManage: boolean;
  hasWorkspace: boolean;
  mode: CalendarEventMode;
  onSelect: (mode: CalendarEventMode) => void;
  ticketCommitments: boolean;
}) {
  if (!hasWorkspace) return null;
  return (
    <div className="calendar-mode">
      <ModeButton active={mode === "personal"} mode="personal" onSelect={onSelect}>
        My event
      </ModeButton>
      {canManage ? (
        <ModeButton active={mode === "team"} mode="team" onSelect={onSelect}>
          Unit event
        </ModeButton>
      ) : null}
      {ticketCommitments ? (
        <ModeButton active={mode === "commitment"} mode="commitment" onSelect={onSelect}>
          Ticket commitment
        </ModeButton>
      ) : null}
    </div>
  );
}

function ModeButton({
  active,
  children,
  mode,
  onSelect,
}: {
  active: boolean;
  children: ReactNode;
  mode: CalendarEventMode;
  onSelect: (mode: CalendarEventMode) => void;
}) {
  return (
    <button aria-pressed={active} onClick={() => onSelect(mode)} type="button">
      {children}
    </button>
  );
}
