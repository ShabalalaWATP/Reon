import { ChevronDown, LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import type { Session } from "../lib/api/types";
import { roleLabels } from "../lib/routes";
import { formatDate } from "../lib/status";

type Props = {
  onSignOut: () => Promise<void>;
  pathname: string;
  session: Session;
};

export function AccountMenu({ onSignOut, pathname, session }: Props) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const user = session.user;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
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
        <span aria-hidden="true" className="account-avatar">{initials(user.displayName)}</span>
        <span className="account-menu__identity">
          <strong>{user.displayName}</strong>
          <small>{roleLabels[user.role]}</small>
        </span>
        <ChevronDown aria-hidden="true" className={open ? "account-menu__chevron--open" : ""} size={16} />
      </button>
      {open ? (
        <div aria-label="Account details" className="account-menu__popover" id={menuId} role="dialog">
          <header>
            <span aria-hidden="true" className="account-avatar account-avatar--large">{initials(user.displayName)}</span>
            <div><strong>{user.displayName}</strong><small>{user.username}</small></div>
          </header>
          <dl>
            <div><dt>Role</dt><dd>{roleLabels[user.role]}</dd></div>
            <div><dt>Scope</dt><dd>{user.scope}</dd></div>
            <div><dt>Session</dt><dd><ShieldCheck aria-hidden="true" size={14} /> Active until {formatDate(session.expiresAt, true)}</dd></div>
          </dl>
          <button className="account-menu__action" onClick={() => void signOut()} type="button">
            <LogOut aria-hidden="true" size={16} />Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

function initials(displayName: string) {
  return displayName
    .split(/\s+/u)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase("en-GB"))
    .join("");
}
