import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { AppShell } from "../components/AppShell";
import { PageState } from "../components/PageState";
import { LoginPage } from "../features/auth/LoginPage";
import { MyWorkPage } from "../features/my-work/MyWorkPage";
import { NotificationsPage } from "../features/notifications/NotificationsPage";
import { ConfigurationPage } from "../features/configuration/ConfigurationPage";
import { ProductPackagePage } from "../features/products/ProductPackagePage";
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
import type { ServerCapabilities } from "../lib/api/capabilityClient";
import type { UserRole } from "../lib/api/types";
import { useAuth } from "../lib/auth/AuthProvider";
import { useCapabilities } from "../lib/capabilities/useCapabilities";
import { homeRouteForRole, trackingRoles } from "../lib/routes";

type CapabilityName = keyof ServerCapabilities;

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<RoleHome />} />
          <Route element={<CapabilityGate capability="myWork" />}>
            <Route path="my-work" element={<MyWorkPage />} />
          </Route>
          <Route element={<CapabilityGate capability="notifications" />}>
            <Route path="notifications" element={<NotificationsPage />} />
          </Route>
          <Route path="organisation" element={<OrganisationPage />} />
          <Route element={<CapabilityGate capability="statistics" />}>
            <Route path="statistics" element={<StatisticsPage />} />
          </Route>
          <Route path="teams/:teamId/:view?" element={<TeamWorkspacePage />} />
          <Route element={<RoleGate allowed={["DELIVERY_TEAM_LEAD", "DELIVERY_SPECIALIST"]} />}>
            <Route path="calendar/:calendarView?" element={<CalendarPage />} />
          </Route>
          <Route element={<RoleGate allowed={["PLATFORM_ADMIN"]} />}>
            <Route path="admin/users" element={<AdminUsersPage />} />
            <Route path="admin/users/new" element={<AdminUserPage create />} />
            <Route path="admin/users/:userId" element={<AdminUserPage />} />
            <Route element={<CapabilityGate capability="configuration" />}>
              <Route path="admin/configuration/:configurationId?" element={<ConfigurationPage />} />
            </Route>
          </Route>
          <Route element={<CapabilityGate capability="products" />}>
            <Route element={<RoleGate allowed={["DELIVERY_SPECIALIST", "DELIVERY_TEAM_LEAD", "QUALITY_RELEASE"]} />}>
              <Route path="product-packages/:packageId" element={<ProductPackagePage />} />
            </Route>
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
            <Route path="delivery/my-work" element={<StaffQueuePage description="Produce and submit the products assigned to you." eyebrow="Product development" title="Production queue" />} />
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
  return session && allowed.includes(session.user.role) ? <Outlet /> : <HomeRedirect />;
}

function CapabilityGate({ capability }: { capability: CapabilityName }) {
  const { capabilities, isPending } = useCapabilities();
  if (isPending) return <PageState kind="loading" title="Opening ISTARI" />;
  return capabilities[capability] ? <Outlet /> : <HomeRedirect />;
}

function HomeRedirect() {
  const { session } = useAuth();
  const { capabilities, isPending } = useCapabilities();
  if (isPending) return <PageState kind="loading" title="Opening ISTARI" />;
  return <Navigate replace to={session ? homeRouteForRole(session.user.role, capabilities) : "/login"} />;
}

function RoleHome() {
  const { session } = useAuth();
  const { capabilities, isPending } = useCapabilities();
  if (!session) return null;
  if (isPending) return <PageState kind="loading" title="Opening ISTARI" />;
  return <Navigate replace to={homeRouteForRole(session.user.role, capabilities)} />;
}
