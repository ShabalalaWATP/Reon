import { ApiError } from "../../lib/api/client";
import type { CalendarOccurrenceAction, CalendarOccurrenceDraft } from "./calendarOccurrenceModel";

type ActionFormProps = {
  draft: CalendarOccurrenceDraft;
  error: Error | null;
  pending: boolean;
  selectAction: (action: CalendarOccurrenceAction) => void;
  submit: () => void;
  update: <Key extends keyof CalendarOccurrenceDraft>(
    key: Key,
    value: CalendarOccurrenceDraft[Key],
  ) => void;
};

export function CalendarOccurrenceActionForm(props: ActionFormProps) {
  const { draft, error, pending, selectAction, submit, update } = props;
  if (!draft.action) return null;
  return (
    <form
      className="calendar-detail__form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <EditableOccurrenceFields {...props} />
      <label className="form-field">
        Reason<span className="field-hint">Required, 10–500 characters</span>
        <textarea
          maxLength={500}
          minLength={10}
          onChange={(event) => update("reason", event.target.value)}
          required
          value={draft.reason}
        />
      </label>
      {error ? (
        <p className="form-banner form-banner--error" role="alert">
          {errorMessage(error)}
        </p>
      ) : null}
      <div className="calendar-detail__actions">
        <button className="button button--primary" disabled={pending} type="submit">
          Confirm {actionLabel(draft.action)}
        </button>
        <button className="button" onClick={() => selectAction(null)} type="button">
          Keep event
        </button>
      </div>
    </form>
  );
}

function EditableOccurrenceFields({ draft, update }: ActionFormProps) {
  const editable = draft.action === "edit" || draft.action === "split";
  if (!editable) return null;
  return (
    <>
      <label className="form-field">
        Title<span className="field-hint">Required</span>
        <input
          minLength={3}
          onChange={(event) => update("title", event.target.value)}
          required
          value={draft.title}
        />
      </label>
      <label className="form-field">
        Notes<span className="field-hint">Required</span>
        <textarea
          onChange={(event) => update("notes", event.target.value)}
          required
          value={draft.notes}
        />
      </label>
      <OccurrenceDateFields draft={draft} update={update} />
      {draft.action === "split" ? (
        <label className="form-field">
          Repeat until<span className="field-hint">Required</span>
          <input
            min={draft.startsAt}
            onChange={(event) => update("until", event.target.value)}
            required
            type="datetime-local"
            value={draft.until}
          />
        </label>
      ) : null}
    </>
  );
}

function OccurrenceDateFields({ draft, update }: Pick<ActionFormProps, "draft" | "update">) {
  return (
    <>
      <label className="form-field">
        Starts<span className="field-hint">Required</span>
        <input
          onChange={(event) => update("startsAt", event.target.value)}
          required
          type="datetime-local"
          value={draft.startsAt}
        />
      </label>
      <label className="form-field">
        Ends<span className="field-hint">Required</span>
        <input
          min={draft.startsAt}
          onChange={(event) => update("endsAt", event.target.value)}
          required
          type="datetime-local"
          value={draft.endsAt}
        />
      </label>
    </>
  );
}

function actionLabel(action: Exclude<CalendarOccurrenceAction, null>) {
  return action.replaceAll("-", " ");
}

function errorMessage(error: Error) {
  return error instanceof ApiError
    ? error.message
    : error.message || "The calendar change could not be saved.";
}
