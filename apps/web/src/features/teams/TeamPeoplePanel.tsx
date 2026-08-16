import type { FormEvent } from "react";

import { PageState } from "../../components/PageState";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { PeopleTable } from "./PeopleTable";
import {
  localRosterDateMinimum,
  useRosterController,
  type RosterMode,
} from "./useRosterController";

export function TeamPeoplePanel({
  access,
  userId,
}: {
  access: TeamWorkspaceAccess;
  userId: string;
}) {
  const controller = useRosterController(access);
  if (controller.peoplePending) return <PageState kind="loading" title="Loading team people" />;
  if (controller.peopleError)
    return (
      <PageState
        action={
          <button className="button" onClick={controller.refetchPeople}>
            Try again
          </button>
        }
        kind="error"
        title="Team people could not be loaded"
      />
    );
  return (
    <div className="team-people-layout">
      <section aria-labelledby="team-people-title" className="team-register">
        <header>
          <span>Effective membership</span>
          <h2 id="team-people-title">People</h2>
          <p>
            Every workspace has named Managers and Members. Current, scheduled and ended records
            remain visible as history.
          </p>
        </header>
        <PeopleTable access={access} items={controller.people} userId={userId} />
      </section>
      {controller.canManage ? <RosterControl controller={controller} /> : null}
    </div>
  );
}

function RosterControl({ controller }: { controller: ReturnType<typeof useRosterController> }) {
  return (
    <aside className="roster-control">
      <span>Manager action</span>
      <h2>Change roster</h2>
      <RosterModeButtons mode={controller.mode} setMode={controller.setMode} />
      {controller.eligiblePending ? <p className="inline-loading">Loading Members…</p> : null}
      {controller.eligibleError ? <EligibleError retry={controller.refetchEligible} /> : null}
      {!controller.eligiblePending && !controller.eligibleError ? (
        <RosterForm controller={controller} />
      ) : null}
    </aside>
  );
}

function RosterModeButtons({
  mode,
  setMode,
}: {
  mode: RosterMode;
  setMode: (mode: RosterMode) => void;
}) {
  return (
    <div className="roster-mode">
      <button aria-pressed={mode === "add"} onClick={() => setMode("add")} type="button">
        Add unassigned
      </button>
      <button aria-pressed={mode === "transfer"} onClick={() => setMode("transfer")} type="button">
        Schedule transfer
      </button>
    </div>
  );
}

function EligibleError({ retry }: { retry: () => void }) {
  return (
    <div className="form-banner form-banner--error" role="alert">
      <p>Eligible Members could not be loaded.</p>
      <button className="button" onClick={retry} type="button">
        Try again
      </button>
    </div>
  );
}

function RosterForm({ controller }: { controller: ReturnType<typeof useRosterController> }) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    controller.submit();
  };
  return (
    <form onSubmit={submit}>
      <MemberSelect controller={controller} />
      {controller.mode === "transfer" ? <TransferDate controller={controller} /> : null}
      <label className="form-field">
        Reason<span className="field-hint">Required, 10–500 characters</span>
        <textarea
          maxLength={500}
          minLength={10}
          onChange={(event) => controller.setReason(event.target.value)}
          required
          rows={4}
          value={controller.reason}
        />
      </label>
      {controller.error ? (
        <p className="form-banner form-banner--error" role="alert">
          {controller.error}
        </p>
      ) : null}
      <button
        className="button button--primary"
        disabled={controller.saving || controller.options.length === 0}
        type="submit"
      >
        {controller.saving
          ? "Saving…"
          : controller.mode === "add"
            ? "Add Member"
            : "Confirm transfer"}
      </button>
    </form>
  );
}

function MemberSelect({ controller }: { controller: ReturnType<typeof useRosterController> }) {
  if (controller.emptyReason) {
    return (
      <p className="inline-empty roster-empty" role="status">
        {controller.emptyReason}
      </p>
    );
  }
  return (
    <label className="form-field">
      Member<span className="field-hint">Required</span>
      <select
        onChange={(event) => controller.setSelectedId(event.target.value)}
        required
        value={controller.selectedId}
      >
        <option value="">Select a compatible Member</option>
        {controller.options.map((item) => (
          <option key={item.accountId} value={item.accountId}>
            {item.displayName}
            {item.currentTeamName ? ` · ${item.currentTeamName}` : " · Unassigned"}
          </option>
        ))}
      </select>
    </label>
  );
}

function TransferDate({ controller }: { controller: ReturnType<typeof useRosterController> }) {
  return (
    <label className="form-field">
      Effective date and time<span className="field-hint">Required</span>
      <input
        min={localRosterDateMinimum()}
        onChange={(event) => controller.setEffectiveFrom(event.target.value)}
        required
        type="datetime-local"
        value={controller.effectiveFrom}
      />
    </label>
  );
}
