import { Bell, LogOut, Moon, Sun } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";

import { useAuth } from "../lib/auth/AuthProvider";
import { useCapabilities } from "../lib/capabilities/useCapabilities";
import { api } from "../lib/api/client";
import { actionNotificationApi } from "../lib/api/actionNotificationClient";
import { protectedQueryKeys } from "../lib/api/queryKeys";
import { navigationForRole, roleLabels } from "../lib/routes";
import { useTheme } from "../lib/theme/ThemeProvider";

export function AppShell() {
  const { logout, session } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [logoutError, setLogoutError] = useState(false);
  const { capabilities } = useCapabilities();
  const notificationCount = useQuery({
    queryKey: protectedQueryKeys.notificationCount(session?.user.id ?? "anonymous"),
    queryFn: actionNotificationApi.notificationCount,
    enabled: Boolean(session && capabilities.notifications),
    refetchInterval: 30_000,
  });
  const statisticsScopes = useQuery({
    queryKey: protectedQueryKeys.statisticsScopes(session?.user.id ?? "anonymous"),
    queryFn: api.statisticsScopes,
    enabled: Boolean(session && capabilities.statistics),
    staleTime: 60_000,
  });
  const teamWorkspaces = useQuery({
    queryKey: protectedQueryKeys.teamWorkspaces(session?.user.id ?? "anonymous"),
    queryFn: api.teamWorkspaces,
    enabled: Boolean(session),
    staleTime: 60_000,
  });
  if (!session) return null;
  const navigation = navigationForRole(session.user.role, capabilities);
  if (["DELIVERY_TEAM_LEAD", "DELIVERY_SPECIALIST"].includes(session.user.role)) {
    navigation.splice(1, 0, { label: "My calendar", path: "/calendar/month" });
  }
  if ((statisticsScopes.data?.items.length ?? 0) > 0) {
    navigation.splice(navigation.length - 1, 0, {
      label: "Statistics",
      path: "/statistics",
    });
  }
  if (teamWorkspaces.data?.items[0]) {
    navigation.splice(navigation.length - 1, 0, {
      label: "Team workspace",
      path: `/teams/${teamWorkspaces.data.items[0].teamId}/overview`,
    });
  }

  async function signOut() {
    setLogoutError(false);
    try {
      await logout();
      void navigate("/login", { replace: true });
    } catch {
      setLogoutError(true);
    }
  }

  return (
    <div className="app-shell">
      <aside aria-label="Account and navigation" className="nav-rail">
        <NavLink aria-label="ISTARI home" className="shell-brand" to="/">
          <img alt="" height="42" src="/istari-logo-64.png" width="42" />
          <span><strong>ISTARI</strong><small>Service workspace</small></span>
        </NavLink>
        <nav aria-label="Primary navigation">
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
              key={item.path}
              to={item.path}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="nav-profile">
          <strong>{session.user.displayName}</strong>
          <small>{roleLabels[session.user.role]}</small>
          <span>{session.user.scope}</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="top-bar">
          <span className="top-bar__context">Secure service workspace</span>
          <div className="top-bar__actions">
            {capabilities.notifications ? <NavLink aria-label={`${notificationCount.data?.unreadCount ?? 0} unread notifications`} className="notification-bell" to="/notifications"><Bell aria-hidden="true" size={18} />{notificationCount.data?.unreadCount ? <span>{notificationCount.data.unreadCount > 99 ? "99+" : notificationCount.data.unreadCount}</span> : null}</NavLink> : null}
            <button
              aria-label={`Use ${theme === "dark" ? "light" : "dark"} theme`}
              className="icon-button"
              onClick={toggleTheme}
              type="button"
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button className="button button--quiet" onClick={() => void signOut()} type="button">
              <LogOut aria-hidden="true" size={16} />Sign out
            </button>
          </div>
          {logoutError ? <p className="top-bar__error" role="alert">Sign out failed. Please try again.</p> : null}
        </header>
        <div className="workspace__main"><Outlet /></div>
      </div>
    </div>
  );
}
