import { ChevronDown, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";

import {
  profileAccessLabel,
  profileInitials,
  profilePositionLabel,
  profileWorkspacePositionText,
} from "../features/profile/profileModel";
import type { TeamWorkspaceAccess } from "../lib/api/teamTypes";
import type { Session } from "../lib/api/types";
import { roleLabels } from "../lib/routes";
import { formatDate } from "../lib/status";

type Props = {
  onSignOut: () => Promise<void>;
  pathname: string;
  session: Session;
  workspaceAccess: TeamWorkspaceAccess[];
  workspaceAccessUnavailable: boolean;
};

export function AccountMenu({
  onSignOut,
  pathname,
  session,
  workspaceAccess,
  workspaceAccessUnavailable,
}: Props) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const user = session.user;
  const position = profilePositionLabel(workspaceAccess);
  const identityLabel = `${roleLabels[user.role]}${position ? ` · ${position}` : ""}`;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = (event: PointerEvent) => {
      if (!container.current!.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  async function signOut() {
    setOpen(false);
    await onSignOut();
  }

  return (
    <div className="account-menu" ref={container}>
      <button
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Open account menu for ${user.displayName}`}
        className="account-menu__trigger"
        onClick={() => setOpen((current) => !current)}
        ref={trigger}
        type="button"
      >
        <span aria-hidden="true" className="account-avatar">{profileInitials(user.displayName)}</span>
        <span className="account-menu__identity">
          <strong>{user.displayName}</strong>
          <small>{identityLabel}</small>
        </span>
        <ChevronDown aria-hidden="true" className={open ? "account-menu__chevron--open" : ""} size={16} />
      </button>
      {open ? (
        <div aria-label="Account details" className="account-menu__popover" id={menuId} role="dialog">
          <header>
            <span aria-hidden="true" className="account-avatar account-avatar--large">{profileInitials(user.displayName)}</span>
            <div><strong>{user.displayName}</strong><small>{user.username}</small></div>
          </header>
          <dl>
            <div><dt>Role</dt><dd>{roleLabels[user.role]}</dd></div>
            {user.organisationUnitIds.length > 0 ? <div><dt>Workspace position</dt><dd>{profileWorkspacePositionText(user.organisationUnitIds.length, workspaceAccess, workspaceAccessUnavailable)}</dd></div> : null}
            <div><dt>Access</dt><dd>{profileAccessLabel(user, workspaceAccess)}</dd></div>
            <div><dt>Session</dt><dd><ShieldCheck aria-hidden="true" size={14} /> Active until {formatDate(session.expiresAt, true)}</dd></div>
          </dl>
          <Link className="account-menu__action account-menu__action--profile" to="/profile">
            <UserRound aria-hidden="true" size={16} />View profile
          </Link>
          <button className="account-menu__action account-menu__action--signout" onClick={() => void signOut()} type="button">
            <LogOut aria-hidden="true" size={16} />Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
