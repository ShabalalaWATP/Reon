import { useEffect, useState } from "react";

import type { NotificationPreference } from "../../lib/api/actionNotificationTypes";
import { humaniseCode } from "../my-work/myWorkModel";

const reminderOptions = [1, 2, 3, 5, 7];

export function NotificationPreferencesPanel({
  disabled,
  onSave,
  preferences,
}: {
  disabled: boolean;
  onSave: (preference: NotificationPreference, enabled: boolean, days: number[]) => void;
  preferences: NotificationPreference[];
}) {
  return (
    <section aria-labelledby="notification-preferences-title" className="notification-preferences">
      <div className="section-heading">
        <span>In-application delivery</span>
        <h2 id="notification-preferences-title">Notification preferences</h2>
      </div>
      <p>
        Safety-critical account and release updates remain enabled. External delivery is not active.
      </p>
      <div className="preference-list">
        {preferences.map((preference) => (
          <PreferenceRow
            disabled={disabled}
            key={preference.eventGroup}
            onSave={onSave}
            preference={preference}
          />
        ))}
      </div>
    </section>
  );
}

function PreferenceRow({
  disabled,
  onSave,
  preference,
}: {
  disabled: boolean;
  onSave: (preference: NotificationPreference, enabled: boolean, days: number[]) => void;
  preference: NotificationPreference;
}) {
  const [enabled, setEnabled] = useState(preference.enabled);
  const [days, setDays] = useState(preference.reminderDays);
  useEffect(() => {
    setEnabled(preference.enabled);
    setDays(preference.reminderDays);
  }, [preference]);
  const toggleDay = (day: number) =>
    setDays((current) =>
      current.includes(day)
        ? current.filter((value) => value !== day)
        : [...current, day].sort((a, b) => b - a),
    );
  return (
    <article className="preference-row">
      <div>
        <strong>{humaniseCode(preference.eventGroup)}</strong>
        {preference.mandatory ? (
          <small>Mandatory safety notification</small>
        ) : (
          <small>May be switched off</small>
        )}
      </div>
      <label>
        <input
          checked={enabled}
          disabled={preference.mandatory}
          onChange={(event) => setEnabled(event.target.checked)}
          type="checkbox"
        />
        Enabled
      </label>
      <fieldset>
        <legend>Reminder days</legend>
        {reminderOptions.map((day) => (
          <label key={day}>
            <input checked={days.includes(day)} onChange={() => toggleDay(day)} type="checkbox" />
            {day}d
          </label>
        ))}
      </fieldset>
      <button
        className="button"
        disabled={disabled}
        onClick={() => onSave(preference, enabled, days)}
        type="button"
      >
        Save
      </button>
    </article>
  );
}
