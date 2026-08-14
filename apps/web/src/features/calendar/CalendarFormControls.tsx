import type { CalendarEventDraft } from "./calendarEventModel";

export function DateTimeField({
  label,
  min,
  onChange,
  value,
}: {
  label: string;
  min?: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="form-field">
      {label}
      <span className="field-hint">Required</span>
      <input
        min={min}
        onChange={(event) => onChange(event.target.value)}
        required
        type="datetime-local"
        value={value}
      />
    </label>
  );
}

export function Select({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <label className="form-field">
      {label}
      <span className="field-hint">Required</span>
      <select onChange={(event) => onChange(event.target.value)} required value={value}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SubmitButton({ draft, pending }: { draft: CalendarEventDraft; pending: boolean }) {
  const label = draft.mode === "commitment" ? "Create commitment" : "Create event";
  return (
    <button className="button button--primary" disabled={pending} type="submit">
      {pending ? "Saving…" : label}
    </button>
  );
}
