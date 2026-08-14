import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "../../lib/api/client";
import type {
  CalendarCategory,
  CalendarVisibility,
  RecurrenceFrequency,
} from "../../lib/api/calendarTypes";
import type { BoardResult } from "../../lib/api/boardTypes";
import type { TeamMember } from "../../lib/api/teamTypes";
import { DateTimeField, Select, SubmitButton } from "./CalendarFormControls";
import type { CalendarEventDraft } from "./calendarEventModel";

type FieldsProps = {
  analysts: TeamMember[];
  draft: CalendarEventDraft;
  mutation: { error: Error | null; isError: boolean; isPending: boolean };
  requests: UseQueryResult<BoardResult>;
  sharingAudience?: string;
  submit: () => void;
  update: <Key extends keyof CalendarEventDraft>(key: Key, value: CalendarEventDraft[Key]) => void;
};

export function CalendarEventFields(props: FieldsProps) {
  const { draft, mutation, submit, update } = props;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <CommitmentFields {...props} />
      <TextFields draft={draft} update={update} />
      <TimingFields draft={draft} update={update} />
      <ClassificationFields {...props} />
      <RecurrenceFields draft={draft} update={update} />
      <label className="calendar-check">
        <input
          checked={draft.allDay}
          onChange={(event) => update("allDay", event.target.checked)}
          type="checkbox"
        />
        All-day activity
      </label>
      {mutation.isError && mutation.error ? (
        <p className="form-banner form-banner--error" role="alert">
          {errorMessage(mutation.error)}
        </p>
      ) : null}
      <SubmitButton draft={draft} pending={mutation.isPending} />
    </form>
  );
}

function CommitmentFields({ analysts, draft, requests, update }: FieldsProps) {
  if (draft.mode !== "commitment") return null;
  const requestItems = requests.data?.items.filter((item) => item.itemType === "SERVICE_REQUEST");
  return (
    <>
      <label className="form-field">
        Service request<span className="field-hint">Required</span>
        <select
          disabled={requests.isPending || requests.isError}
          onChange={(event) => update("requestId", event.target.value)}
          required
          value={draft.requestId}
        >
          <option value="">{requestPlaceholder(requests)}</option>
          {requestItems?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.reference} · {item.title}
            </option>
          ))}
        </select>
      </label>
      <label className="form-field">
        Analyst<span className="field-hint">Required</span>
        <select
          onChange={(event) => update("subjectId", event.target.value)}
          required
          value={draft.subjectId}
        >
          <option value="">Select an Analyst</option>
          {analysts.map((analyst) => (
            <option key={analyst.accountId} value={analyst.accountId}>
              {analyst.displayName}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

function TextFields({ draft, update }: Pick<FieldsProps, "draft" | "update">) {
  return (
    <>
      <label className="form-field">
        Title<span className="field-hint">Required</span>
        <input
          maxLength={160}
          minLength={3}
          onChange={(event) => update("title", event.target.value)}
          required
          value={draft.title}
        />
      </label>
      <label className="form-field">
        Notes<span className="field-hint">Required</span>
        <textarea
          maxLength={2000}
          onChange={(event) => update("notes", event.target.value)}
          required
          rows={4}
          value={draft.notes}
        />
      </label>
    </>
  );
}

function TimingFields({ draft, update }: Pick<FieldsProps, "draft" | "update">) {
  return (
    <div className="calendar-form-grid">
      <DateTimeField
        label="Starts"
        onChange={(value) => update("startsAt", value)}
        value={draft.startsAt}
      />
      <DateTimeField
        label="Ends"
        min={draft.startsAt}
        onChange={(value) => update("endsAt", value)}
        value={draft.endsAt}
      />
    </div>
  );
}

function ClassificationFields(props: FieldsProps) {
  const { draft, sharingAudience, update } = props;
  const className =
    draft.mode === "personal"
      ? "calendar-form-grid"
      : "calendar-form-grid calendar-form-grid--single";
  return (
    <div className={className}>
      <Select
        label="Category"
        onChange={(value) => update("category", value as CalendarCategory)}
        options={[
          "AVAILABILITY",
          "SERVICE_WORK",
          "LEAVE",
          "TRAINING",
          "DUTY",
          "APPOINTMENT",
          "OTHER",
        ]}
        value={draft.category}
      />
      {draft.mode === "personal" ? (
        <PrivacyChoice
          sharingAudience={sharingAudience}
          update={update}
          visibility={draft.visibility}
        />
      ) : null}
    </div>
  );
}

function PrivacyChoice({
  sharingAudience,
  update,
  visibility,
}: {
  sharingAudience?: string;
  update: FieldsProps["update"];
  visibility: CalendarVisibility;
}) {
  return (
    <label className="calendar-private-choice">
      <input
        checked={visibility === "PRIVATE"}
        onChange={(event) => update("visibility", event.target.checked ? "PRIVATE" : "TEAM_DETAIL")}
        type="checkbox"
      />
      <span>
        <strong>Private appointment</strong>
        <small>{privacyDescription(visibility, sharingAudience)}</small>
      </span>
    </label>
  );
}

function RecurrenceFields({ draft, update }: Pick<FieldsProps, "draft" | "update">) {
  return (
    <>
      <div className="calendar-form-grid">
        <label className="form-field">
          Time zone<span className="field-hint">Required</span>
          <select
            onChange={(event) => update("timeZone", event.target.value)}
            required
            value={draft.timeZone}
          >
            <option>Europe/London</option>
            <option>Europe/Paris</option>
            <option>America/New_York</option>
            <option>Asia/Tokyo</option>
            <option>Australia/Sydney</option>
          </select>
        </label>
        <Select
          label="Repeats"
          onChange={(value) => update("recurrence", value as RecurrenceFrequency)}
          options={["NONE", "DAILY", "WEEKLY"]}
          value={draft.recurrence}
        />
      </div>
      {draft.recurrence === "NONE" ? null : (
        <div className="calendar-form-grid">
          <label className="form-field">
            Repeat interval<span className="field-hint">Required</span>
            <input
              max={4}
              min={1}
              onChange={(event) => update("interval", Number(event.target.value))}
              required
              type="number"
              value={draft.interval}
            />
          </label>
          <DateTimeField
            label="Repeat until"
            min={draft.startsAt}
            onChange={(value) => update("until", value)}
            value={draft.until}
          />
        </div>
      )}
    </>
  );
}

function requestPlaceholder(requests: UseQueryResult<BoardResult>) {
  if (requests.isPending) return "Loading current requests…";
  if (requests.isError) return "Requests unavailable";
  return "Select a request";
}

function privacyDescription(visibility: CalendarVisibility, sharingAudience?: string) {
  if (visibility === "PRIVATE") {
    return "The title and notes will be hidden from colleagues. They will see Busy and the event time only.";
  }
  if (sharingAudience) {
    return `Title, category and notes are visible to other members of ${sharingAudience}.`;
  }
  return "This event remains personal while you have no current workspace. If you join one, active event details will appear there unless marked private.";
}

function errorMessage(error: Error) {
  return error instanceof ApiError
    ? error.message
    : error.message || "The calendar event could not be saved.";
}
