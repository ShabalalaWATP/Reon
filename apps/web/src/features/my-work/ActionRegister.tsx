import { Link } from "react-router";

import type { ActionColumn, PersonalAction } from "../../lib/api/actionNotificationTypes";
import { actionColumns, actionTypeLabel, availableToLabel, columnLabels, formatActionDate, safeWorkspaceHref } from "./myWorkModel";

export function ActionRegister({ columns, items, label }: { columns: ActionColumn[]; items: PersonalAction[]; label: string }) {
  return (
    <div className="work-register-scroll" role="region" aria-label={label} tabIndex={0}>
      <table className="work-register">
        <thead><tr>{actionColumns.filter((column) => columns.includes(column)).map((column) => <th key={column}>{columnLabels[column]}</th>)}<th>Action</th></tr></thead>
        <tbody>{items.map((item) => <ActionRow columns={columns} item={item} key={item.id} />)}</tbody>
      </table>
    </div>
  );
}

function ActionRow({ columns, item }: { columns: ActionColumn[]; item: PersonalAction }) {
  const href = safeWorkspaceHref(item.deepLink);
  return <tr>
    {columns.includes("REFERENCE") ? <td className="mono-ref">{item.reference}</td> : null}
    {columns.includes("TITLE") ? <td><strong>{item.title ?? "Restricted item"}</strong><small>{actionTypeLabel(item.actionType)}</small><small>{item.actionAccess === "PERSONAL" ? "Assigned to you" : `Available to ${availableToLabel(item.currentOwner)}`}</small></td> : null}
    {columns.includes("CURRENT_OWNER") ? <td>{item.currentOwner ?? "Unassigned"}</td> : null}
    {columns.includes("REQUIRED_BY") ? <td>{formatActionDate(item.requiredBy)}</td> : null}
    {columns.includes("AGE") ? <td>{item.ageDays === 0 ? "Today" : `${item.ageDays}d`}</td> : null}
    {columns.includes("LAST_CHANGED") ? <td>{formatActionDate(item.lastChangedAt)}</td> : null}
    <td>{item.isStale ? <span className="status-pill status-pill--attention">Refreshing</span> : href ? <Link className="button button--quiet" to={href}>Open<span className="sr-only"> {item.reference}</span></Link> : <span className="work-link-ended">Access ended</span>}</td>
  </tr>;
}
