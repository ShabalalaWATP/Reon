/** Format a Date for browser date controls using the user's local calendar. */
export function localDateInputValue(value: Date) {
  return [
    value.getFullYear().toString().padStart(4, "0"),
    (value.getMonth() + 1).toString().padStart(2, "0"),
    value.getDate().toString().padStart(2, "0"),
  ].join("-");
}

/** Format a Date for browser datetime-local controls without a UTC conversion. */
export function localDateTimeInputValue(value: Date) {
  const hours = value.getHours().toString().padStart(2, "0");
  const minutes = value.getMinutes().toString().padStart(2, "0");
  return `${localDateInputValue(value)}T${hours}:${minutes}`;
}

/** Move by local calendar days, preserving local wall-clock time through DST changes. */
export function addLocalDays(value: Date, count: number) {
  const result = new Date(value);
  result.setDate(result.getDate() + count);
  return result;
}
