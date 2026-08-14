import { Link } from "react-router";

import type { AdminUser } from "../../lib/api/types";
import { roleLabels } from "../../lib/routes";

export function AdminUserRegister({ users }: { users: AdminUser[] }) {
  return (
    <div
      className="admin-table-scroll"
      role="region"
      aria-label="User account register"
      tabIndex={0}
    >
      <table className="admin-table">
        <thead>
          <tr>
            <th>Account</th>
            <th>Name</th>
            <th>Role</th>
            <th>Scope</th>
            <th>Memberships</th>
            <th>Status</th>
            <th>
              <span className="sr-only">Action</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td className="admin-account-identity">
                <strong className="mono-ref">{user.username}</strong>
                <small>{user.email}</small>
              </td>
              <td>
                <strong>{user.displayName}</strong>
              </td>
              <td>{roleLabels[user.role]}</td>
              <td>{user.scope}</td>
              <td>
                {user.memberships.length
                  ? user.memberships.map((membership) => membership.organisationUnitName).join(", ")
                  : "None"}
              </td>
              <td>
                <span
                  className={`status-pill status-pill--${user.isActive ? "success" : "attention"}`}
                >
                  {user.isActive ? "Active" : "Inactive"}
                </span>
              </td>
              <td>
                <Link
                  aria-label={`Manage ${user.displayName}`}
                  className="button button--quiet"
                  to={`/admin/users/${user.id}`}
                >
                  Manage
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
