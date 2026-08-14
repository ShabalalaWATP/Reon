import { Link } from "react-router";
import type { ReactNode } from "react";

import type { ActionColumn, PersonalAction } from "../../lib/api/actionNotificationTypes";
import {
  actionColumns,
  actionTypeLabel,
  availableToLabel,
  columnLabels,
  formatActionDate,
  safeWorkspaceHref,
} from "./myWorkModel";

export function ActionRegister({
  columns,
  items,
  label,
}: {
  columns: ActionColumn[];
  items: PersonalAction[];
  label: string;
}) {
  return (
    <div className="work-register-scroll" role="region" aria-label={label} tabIndex={0}>
      <table className="work-register">
        <thead>
          <tr>
            {actionColumns
              .filter((column) => columns.includes(column))
              .map((column) => (
                <th key={column}>{columnLabels[column]}</th>
              ))}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <ActionRow columns={columns} item={item} key={item.id} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionRow({ columns, item }: { columns: ActionColumn[]; item: PersonalAction }) {
  const href = safeWorkspaceHref(item.deepLink);
  return (
    <tr>
      {actionColumns
        .filter((column) => columns.includes(column))
        .map((column) => (
          <ActionCell column={column} item={item} key={column} />
        ))}
      <td>
        <ActionLink href={href} item={item} />
      </td>
    </tr>
  );
}

const cellContent: Record<ActionColumn, (item: PersonalAction) => ReactNode> = {
  REFERENCE: (item) => item.reference,
  TITLE: (item) => (
    <>
      <strong>{item.title ?? "Restricted item"}</strong>
      <small>{actionTypeLabel(item.actionType)}</small>
      <small>
        {item.actionAccess === "PERSONAL"
          ? "Assigned to you"
          : `Available to ${availableToLabel(item.currentOwner)}`}
      </small>
    </>
  ),
  CURRENT_OWNER: (item) => item.currentOwner ?? "Unassigned",
  REQUIRED_BY: (item) => formatActionDate(item.requiredBy),
  AGE: (item) => (item.ageDays === 0 ? "Today" : `${item.ageDays}d`),
  LAST_CHANGED: (item) => formatActionDate(item.lastChangedAt),
};

function ActionCell({ column, item }: { column: ActionColumn; item: PersonalAction }) {
  return (
    <td className={column === "REFERENCE" ? "mono-ref" : undefined}>{cellContent[column](item)}</td>
  );
}

function ActionLink({ href, item }: { href: string | null; item: PersonalAction }) {
  if (item.isStale) return <span className="status-pill status-pill--attention">Refreshing</span>;
  if (href)
    return (
      <Link aria-label={`Open ${item.reference}`} className="button button--quiet" to={href}>
        Open
      </Link>
    );
  return <span className="work-link-ended">Access ended</span>;
}
