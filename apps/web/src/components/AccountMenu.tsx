import { ChevronDown, LogOut, Repeat2, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";

import {
  profileAccessLabel,
  profileInitials,
  profilePositionLabel,
  profileWorkspacePositionText,
} from "../features/profile/profileModel";
import type { TeamWorkspaceAccess } from "../lib/api/teamTypes";
import type { AccountContext, Session } from "../lib/api/types";
import { roleLabels } from "../lib/routes";
import { formatDate } from "../lib/status";

type Props = {
  contextSwitchingEnabled: boolean;
  onSignOut: () => Promise<void>;
  onSwitchContext: (context: AccountContext) => Promise<void>;
  pathname: string;
  session: Session;
  switchingContext: boolean;
  workspaceAccess: TeamWorkspaceAccess[];
  workspaceAccessUnavailable: boolean;
};

export function AccountMenu({
  contextSwitchingEnabled,
  onSignOut,
  onSwitchContext,
  pathname,
  session,
  switchingContext,
  workspaceAccess,
  workspaceAccessUnavailable,
}: Props) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const user = session.user;
  const position = profilePositionLabel(workspaceAccess);
  const identityLabel = `${roleLabels[user.role]}${position ? ` · ${position}` : ""}`;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    panel.current!.focus();
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

  async function switchContext(context: AccountContext) {
    setOpen(false);
    await onSwitchContext(context);
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
        <span aria-hidden="true" className="account-avatar">
          {profileInitials(user.displayName)}
        </span>
        <span className="account-menu__identity">
          <strong>{user.displayName}</strong>
          <small>{identityLabel}</small>
        </span>
        <ChevronDown
          aria-hidden="true"
          className={open ? "account-menu__chevron--open" : ""}
          size={16}
        />
      </button>
      {open ? (
        <div
          aria-label="Account details"
          className="account-menu__popover"
          id={menuId}
          ref={panel}
          role="dialog"
          tabIndex={-1}
        >
          <div className="account-menu__header">
            <span aria-hidden="true" className="account-avatar account-avatar--large">
              {profileInitials(user.displayName)}
            </span>
            <div>
              <strong>{user.displayName}</strong>
              <small>{user.username}</small>
            </div>
          </div>
          <dl>
            <div>
              <dt>Role</dt>
              <dd>{roleLabels[user.role]}</dd>
            </div>
            {user.organisationUnitIds.length > 0 ? (
              <div>
                <dt>Workspace position</dt>
                <dd>
                  {profileWorkspacePositionText(
                    user.organisationUnitIds.length,
                    workspaceAccess,
                    workspaceAccessUnavailable,
                  )}
                </dd>
              </div>
            ) : null}
            <div>
              <dt>Access</dt>
              <dd>{profileAccessLabel(user, workspaceAccess)}</dd>
            </div>
            <div>
              <dt>Session</dt>
              <dd>
                <ShieldCheck aria-hidden="true" size={14} /> Active until{" "}
                {formatDate(session.expiresAt, true)}
              </dd>
            </div>
          </dl>
          {contextSwitchingEnabled && session.availableContexts.length > 1 ? (
            <section aria-label="Account contexts" className="account-menu__contexts">
              <span>Work as</span>
              {session.availableContexts.map((context) =>
                context === session.activeContext ? (
                  <div
                    className="account-menu__context account-menu__context--active"
                    key={context}
                  >
                    <strong>{contextLabel(context)}</strong>
                    <small>Active context</small>
                  </div>
                ) : (
                  <button
                    aria-label={`Switch to ${contextLabel(context)} context`}
                    className="account-menu__context"
                    disabled={switchingContext}
                    key={context}
                    onClick={() => void switchContext(context)}
                    type="button"
                  >
                    <Repeat2 aria-hidden="true" size={16} />
                    <span>
                      <strong>{contextLabel(context)}</strong>
                      <small>{contextDescription(context)}</small>
                    </span>
                  </button>
                ),
              )}
            </section>
          ) : null}
          <Link className="account-menu__action account-menu__action--profile" to="/profile">
            <UserRound aria-hidden="true" size={16} />
            View profile
          </Link>
          <button
            className="account-menu__action account-menu__action--signout"
            onClick={() => void signOut()}
            type="button"
          >
            <LogOut aria-hidden="true" size={16} />
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

function contextLabel(context: AccountContext) {
  return context === "CUSTOMER" ? "Customer" : "Staff";
}

function contextDescription(context: AccountContext) {
  return context === "CUSTOMER" ? "Open My requests" : "Open your staff Home";
}
