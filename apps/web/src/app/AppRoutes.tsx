import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { AppShell } from "../components/AppShell";
import { PageState } from "../components/PageState";
import { LoginPage } from "../features/auth/LoginPage";
import { CalendarPage } from "../features/calendar/CalendarPage";
import { AdminUserPage } from "../features/admin/AdminUserPage";
import { AdminUsersPage } from "../features/admin/AdminUsersPage";
import { OrganisationPage } from "../features/organisation/OrganisationPage";
import { NewRequestPage } from "../features/requests/NewRequestPage";
import { RequestDashboardPage } from "../features/requests/RequestDashboardPage";
import { RequestDetailPage } from "../features/requests/RequestDetailPage";
import { TrackingPage } from "../features/tracking/TrackingPage";
import { StatisticsPage } from "../features/statistics/StatisticsPage";
import { TeamWorkspacePage } from "../features/teams/TeamWorkspacePage";
import { StaffQueuePage } from "../features/work/StaffQueuePage";
import type { UserRole } from "../lib/api/types";
import { useAuth } from "../lib/auth/AuthProvider";
import { roleRoutes, trackingRoles } from "../lib/routes";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<RoleHome />} />
          <Route path="organisation" element={<OrganisationPage />} />
          <Route path="statistics" element={<StatisticsPage />} />
          <Route path="teams/:teamId/:view?" element={<TeamWorkspacePage />} />
          <Route element={<RoleGate allowed={["DELIVERY_TEAM_LEAD", "DELIVERY_SPECIALIST"]} />}>
            <Route path="calendar/:calendarView?" element={<CalendarPage />} />
          </Route>
          <Route element={<RoleGate allowed={["PLATFORM_ADMIN"]} />}>
            <Route path="admin/users" element={<AdminUsersPage />} />
            <Route path="admin/users/new" element={<AdminUserPage create />} />
            <Route path="admin/users/:userId" element={<AdminUserPage />} />
          </Route>
          <Route element={<RoleGate allowed={trackingRoles} />}>
            <Route path="tracking" element={<TrackingPage />} />
          </Route>
          <Route element={<RoleGate allowed={["REQUESTER"]} />}>
            <Route path="requests" element={<RequestDashboardPage />} />
            <Route path="requests/new" element={<NewRequestPage />} />
            <Route path="requests/drafts/:draftId" element={<NewRequestPage />} />
            <Route path="requests/:requestId" element={<RequestDetailPage />} />
          </Route>
          <Route element={<RoleGate allowed={["INTAKE_TRIAGE"]} />}>
            <Route path="triage" element={<StaffQueuePage description="Review new Customer demand, request information or route it to the appropriate command." eyebrow="JIOC routing" title="JIOC routing queue" />} />
          </Route>
          <Route element={<RoleGate allowed={["SERVICE_COORDINATION"]} />}>
            <Route path="coordination" element={<StaffQueuePage description="Oversee command routing, holds and onward hand-offs to operations." eyebrow="Command routing" title="Command routing queue" />} />
          </Route>
          <Route element={<RoleGate allowed={["OPERATIONS_ALLOCATION"]} />}>
            <Route path="allocation" element={<StaffQueuePage description="Select a team destination and record the capabilities required for production." eyebrow="Ops routing" title="Ops routing queue" />} />
          </Route>
          <Route element={<RoleGate allowed={["DELIVERY_TEAM_LEAD"]} />}>
            <Route path="delivery/team" element={<StaffQueuePage description="Assign Analysts and review submitted products." eyebrow="Team management" title="Team queue" />} />
          </Route>
          <Route element={<RoleGate allowed={["DELIVERY_SPECIALIST"]} />}>
            <Route path="delivery/my-work" element={<StaffQueuePage description="Produce and submit the products assigned to you." eyebrow="Product development" title="My work" />} />
          </Route>
          <Route element={<RoleGate allowed={["QUALITY_RELEASE"]} />}>
            <Route path="quality-release" element={<StaffQueuePage description="Review products, require changes or disseminate them to the Customer." eyebrow="Quality control" title="QC queue" />} />
          </Route>
          <Route path="*" element={<RoleHome />} />
        </Route>
      </Route>
    </Routes>
  );
}

function RequireAuth() {
  const { session, status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <PageState kind="loading" title="Opening ISTARI" />;
  if (!session) return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  return <Outlet />;
}

function RoleGate({ allowed }: { allowed: UserRole[] }) {
  const { session } = useAuth();
  return session && allowed.includes(session.user.role) ? <Outlet /> : <Navigate replace to={session ? roleRoutes[session.user.role] : "/login"} />;
}

function RoleHome() {
  const { session } = useAuth();
  if (!session) return null;
  return <Navigate replace to={roleRoutes[session.user.role]} />;
}
