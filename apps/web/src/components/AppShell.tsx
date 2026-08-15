import { Bell, Moon, ShieldCheck, Sun } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { AccountMenu } from "./AccountMenu";
import { useShellData } from "./useShellData";
import { RouteErrorBoundary } from "../app/RouteErrorBoundary";
import type { AccountContext, Session } from "../lib/api/types";
import { useAuth } from "../lib/auth/AuthProvider";
import { isNavigationItemActive, type NavigationItem } from "../lib/routes";
import { useTheme } from "../lib/theme/ThemeProvider";

export function AppShell() {
  const auth = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutError, setLogoutError] = useState(false);
  if (!auth.session) return null;
  return (
    <AuthenticatedShell
      auth={auth}
      locationPath={location.pathname}
      logoutError={logoutError}
      navigateToLogin={() => void navigate("/login", { replace: true })}
      session={auth.session}
      setLogoutError={setLogoutError}
      theme={theme}
      toggleTheme={toggleTheme}
    />
  );
}

type ShellProps = {
  auth: ReturnType<typeof useAuth>;
  locationPath: string;
  logoutError: boolean;
  navigateToLogin: () => void;
  session: Session;
  setLogoutError: (failed: boolean) => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
};

function AuthenticatedShell(props: ShellProps) {
  const { auth, locationPath } = props;
  const { session } = props;
  const shell = useShellData(session, locationPath);
  const [pageRecovery, setPageRecovery] = useState(0);
  const signOut = async () => {
    props.setLogoutError(false);
    try {
      await auth.logout();
      props.navigateToLogin();
    } catch {
      props.setLogoutError(true);
    }
  };
  const changeContext = async (context: AccountContext) => {
    if (!shell.capabilities.contextSwitching) return;
    try {
      await auth.switchContext(context);
    } catch {
      // AuthProvider reconciles the rotated session and exposes an accessible error.
    }
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside aria-label="Account and navigation" className="nav-rail">
        <NavLink aria-label="Mist home" className="shell-brand" to="/">
          <img alt="" height="42" src="/mist-logo-64.png" width="42" />
          <span>
            <strong>Mist</strong>
            <small>Service workspace</small>
          </span>
        </NavLink>
        <nav aria-label="Primary navigation">
          {shell.navigation.map((item) => (
            <PrimaryNavigationLink item={item} key={item.path} pathname={locationPath} />
          ))}
        </nav>
        <div className="nav-session-status">
          <ShieldCheck aria-hidden="true" size={15} />
          <span>
            <strong>Authenticated</strong>
            <small>Protected workspace</small>
          </span>
        </div>
      </aside>
      <div className="workspace">
        <header className="top-bar">
          <ShellIdentity context={session.activeContext} />
          <div className="top-bar__actions">
            {shell.capabilities.notifications ? (
              <NotificationLink count={shell.notificationCount} />
            ) : null}
            <button
              aria-label={`Use ${props.theme === "dark" ? "light" : "dark"} theme`}
              className="icon-button"
              onClick={props.toggleTheme}
              type="button"
            >
              {props.theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <AccountMenu
              contextSwitchingEnabled={shell.capabilities.contextSwitching}
              onSignOut={signOut}
              onSwitchContext={changeContext}
              pathname={locationPath}
              session={session}
              switchingContext={auth.contextSwitching}
              workspaceAccess={shell.teamWorkspaces.data?.items ?? []}
              workspaceAccessUnavailable={shell.teamWorkspaces.isError}
            />
          </div>
          {props.logoutError ? (
            <p className="top-bar__error" role="alert">
              Sign out failed. Please try again.
            </p>
          ) : null}
          {auth.contextSwitchError ? (
            <div className="top-bar__error top-bar__error--context" role="alert">
              <span>{auth.contextSwitchError}</span>
              <button onClick={auth.dismissContextSwitchError} type="button">
                Dismiss
              </button>
            </div>
          ) : null}
        </header>
        <div
          className="workspace__main"
          id="main-content"
          key={session.contextVersion}
          tabIndex={-1}
        >
          <RouteErrorBoundary
            actionLabel="Try this page again"
            description="The rest of the workspace is still available. Try this page again, or choose another destination."
            onReload={() => setPageRecovery((current) => current + 1)}
            resetKey={`${locationPath}#${pageRecovery}`}
          >
            <Outlet />
          </RouteErrorBoundary>
        </div>
      </div>
    </div>
  );
}

function ShellIdentity({ context }: { context: AccountContext }) {
  return (
    <div className="top-bar__identity">
      <span className="top-bar__context">Secure service workspace</span>
      <span className={`account-context-badge account-context-badge--${context.toLowerCase()}`}>
        {context === "CUSTOMER" ? "Customer context" : "Staff context"}
      </span>
    </div>
  );
}

function NotificationLink({ count }: { count: number }) {
  return (
    <NavLink
      aria-label={`${count} unread notifications`}
      className="notification-bell"
      to="/notifications"
    >
      <Bell aria-hidden="true" size={18} />
      {count ? <span>{count > 99 ? "99+" : count}</span> : null}
    </NavLink>
  );
}

function PrimaryNavigationLink({ item, pathname }: { item: NavigationItem; pathname: string }) {
  const active = isNavigationItemActive(pathname, item.path);
  return (
    <NavLink
      aria-current={active ? "page" : undefined}
      className={`nav-link${active ? " nav-link--active" : ""}`}
      end={item.path === "/requests"}
      to={item.path}
    >
      <span>{item.label}</span>
      <i aria-hidden="true" />
    </NavLink>
  );
}
