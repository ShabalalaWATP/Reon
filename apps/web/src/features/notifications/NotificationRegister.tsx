import { Link } from "react-router";

import type { PersonalNotification } from "../../lib/api/actionNotificationTypes";
import { formatActionDate, humaniseCode, safeWorkspaceHref } from "../my-work/myWorkModel";

type Props = {
  items: PersonalNotification[];
  selected: Set<string>;
  toggle: (id: string) => void;
};

export function NotificationRegister({ items, selected, toggle }: Props) {
  return <ol className="notification-register" aria-label="Notifications">{items.map((item) => {
    const href = safeWorkspaceHref(item.deepLink);
    return <li className={item.isRead ? "notification-row" : "notification-row notification-row--unread"} key={item.id}>
      <label className="notification-select"><input aria-label={`Select ${item.subject}`} checked={selected.has(item.id)} onChange={() => toggle(item.id)} type="checkbox" /><span className="sr-only">Select</span></label>
      <div className="notification-main"><span className="mono-ref">{humaniseCode(item.eventGroup)}</span><strong>{item.subject}</strong><small>{humaniseCode(item.eventType)} · {formatActionDate(item.occurredAt)}</small></div>
      <div className="notification-state">{item.isArchived ? <span className="status-pill">Archived</span> : item.isActionCompleted ? <span className="status-pill status-pill--success">Action complete</span> : item.isRead ? <span className="status-pill">Read</span> : <span className="status-pill status-pill--active">Unread</span>}</div>
      <div>{href ? <Link aria-label={`Open ${item.subject}`} className="button button--quiet" to={href}>Open</Link> : item.deepLink ? <span className="work-link-ended">Access ended</span> : null}</div>
    </li>;
  })}</ol>;
}
