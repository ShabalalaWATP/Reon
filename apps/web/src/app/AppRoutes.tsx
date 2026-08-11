import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { AppShell } from "../components/AppShell";
import { PageState } from "../components/PageState";
import type { ServerCapabilities } from "../lib/api/capabilityClient";
import type { UserRole } from "../lib/api/types";
import { useAuth } from "../lib/auth/AuthProvider";
import { useCapabilities } from "../lib/capabilities/useCapabilities";
import { homeRouteForRole, trackingRoles } from "../lib/routes";

const LoginPage = lazy(() => import("../features/auth/LoginPage")
  .then(({ LoginPage: page }) => ({ default: page })));
const MyWorkPage = lazy(() => import("../features/my-work/MyWorkPage")
  .then(({ MyWorkPage: page }) => ({ default: page })));
const NotificationsPage = lazy(() => import("../features/notifications/NotificationsPage")
  .then(({ NotificationsPage: page }) => ({ default: page })));
const ConfigurationPage = lazy(() => import("../features/configuration/ConfigurationPage")
  .then(({ ConfigurationPage: page }) => ({ default: page })));
const ProductPackagePage = lazy(() => import("../features/products/ProductPackagePage")
  .then(({ ProductPackagePage: page }) => ({ default: page })));
const CalendarPage = lazy(() => import("../features/calendar/CalendarPage")
  .then(({ CalendarPage: page }) => ({ default: page })));
const AdminUserPage = lazy(() => import("../features/admin/AdminUserPage")
  .then(({ AdminUserPage: page }) => ({ default: page })));
const AdminUsersPage = lazy(() => import("../features/admin/AdminUsersPage")
  .then(({ AdminUsersPage: page }) => ({ default: page })));
const OrganisationPage = lazy(() => import("../features/organisation/OrganisationPage")
  .then(({ OrganisationPage: page }) => ({ default: page })));
const NewRequestPage = lazy(() => import("../features/requests/NewRequestPage")
  .then(({ NewRequestPage: page }) => ({ default: page })));
const RequestDashboardPage = lazy(() => import("../features/requests/RequestDashboardPage")
  .then(({ RequestDashboardPage: page }) => ({ default: page })));
const RequestDetailPage = lazy(() => import("../features/requests/RequestDetailPage")
  .then(({ RequestDetailPage: page }) => ({ default: page })));
const TrackingPage = lazy(() => import("../features/tracking/TrackingPage")
  .then(({ TrackingPage: page }) => ({ default: page })));
const TrackingDetailPage = lazy(() => import("../features/tracking/TrackingDetailPage")
  .then(({ TrackingDetailPage: page }) => ({ default: page })));
const StatisticsPage = lazy(() => import("../features/statistics/StatisticsPage")
  .then(({ StatisticsPage: page }) => ({ default: page })));
const TeamWorkspacePage = lazy(() => import("../features/teams/TeamWorkspacePage")
  .then(({ TeamWorkspacePage: page }) => ({ default: page })));
const StaffQueuePage = lazy(() => import("../features/work/StaffQueuePage")
  .then(({ StaffQueuePage: page }) => ({ default: page })));
const ProfilePage = lazy(() => import("../features/profile/ProfilePage")
  .then(({ ProfilePage: page }) => ({ default: page })));
const RoleOverviewPage = lazy(() => import("../features/overview/RoleOverviewPage")
  .then(({ RoleOverviewPage: page }) => ({ default: page })));

type CapabilityName = keyof ServerCapabilities;
const staffMyWorkRoles: UserRole[] = [
  "PLATFORM_ADMIN",
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
  "DELIVERY_TEAM_LEAD",
  "DELIVERY_SPECIALIST",
  "QUALITY_RELEASE",
];

export function AppRoutes() {
  return (
    <Suspense fallback={<PageState kind="loading" title="Opening ISTARI" />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route index element={<RoleHome />} />
            <Route element={<CapabilityGate capability="myWork" />}>
              <Route element={<RoleGate allowed={staffMyWorkRoles} />}>
                <Route path="my-work" element={<MyWorkPage />} />
              </Route>
            </Route>
            <Route path="profile" element={<ProfilePage />} />
            <Route element={<CapabilityGate capability="statistics" />}>
              <Route path="overview" element={<RoleOverviewPage />} />
            </Route>
            <Route element={<CapabilityGate capability="notifications" />}>
              <Route path="notifications" element={<NotificationsPage />} />
            </Route>
            <Route path="organisation" element={<OrganisationPage />} />
            <Route element={<CapabilityGate capability="statistics" />}>
              <Route path="statistics" element={<StatisticsPage />} />
            </Route>
            <Route path="teams/:teamId/:view?" element={<TeamWorkspacePage />} />
            <Route path="calendar/:calendarView?" element={<CalendarPage />} />
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
              <Route path="tracking/:requestId" element={<TrackingDetailPage />} />
            </Route>
            <Route element={<RoleGate allowed={["REQUESTER"]} />}>
              <Route path="requests" element={<RequestDashboardPage />} />
              <Route path="requests/new" element={<NewRequestPage />} />
              <Route path="requests/drafts/:draftId" element={<NewRequestPage />} />
              <Route path="requests/:requestId" element={<RequestDetailPage />} />
            </Route>
            <Route element={<RoleGate allowed={["INTAKE_TRIAGE"]} />}>
              <Route
                path="triage"
                element={<StaffQueuePage description="Review new Customer demand, request information or route it to the appropriate command." eyebrow="CRIOC routing" title="CRIOC routing queue" />}
              />
            </Route>
            <Route element={<RoleGate allowed={["SERVICE_COORDINATION"]} />}>
              <Route
                path="coordination"
                element={<StaffQueuePage description="A new request has been submitted and requires your attention. Claim it to review the details and choose the next organisation." eyebrow="Request coordination" title="Incoming requests" />}
              />
            </Route>
            <Route element={<RoleGate allowed={["OPERATIONS_ALLOCATION"]} />}>
              <Route
                path="allocation"
                element={<StaffQueuePage description="Select a team destination and record the capabilities required for production." eyebrow="Ops routing" title="Ops routing queue" />}
              />
            </Route>
            <Route element={<RoleGate allowed={["DELIVERY_TEAM_LEAD"]} />}>
              <Route
                path="delivery/team"
                element={<StaffQueuePage description="Assign Analysts and review submitted products." eyebrow="Team management" title="Team queue" />}
              />
            </Route>
            <Route element={<RoleGate allowed={["DELIVERY_SPECIALIST"]} />}>
              <Route
                path="delivery/my-work"
                element={<StaffQueuePage description="Produce and submit the products assigned to you." eyebrow="Product development" title="Production queue" />}
              />
            </Route>
            <Route element={<RoleGate allowed={["QUALITY_RELEASE"]} />}>
              <Route
                path="quality-release"
                element={<StaffQueuePage description="Review products, require changes or disseminate them to the Customer." eyebrow="Quality control" title="QC queue" />}
              />
            </Route>
            <Route path="*" element={<RoleHome />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
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
  return <Navigate replace to={homeRouteForRole(session!.user.role, capabilities)} />;
}

function RoleHome() {
  const { session } = useAuth();
  const { capabilities, isPending } = useCapabilities();
  if (isPending) return <PageState kind="loading" title="Opening ISTARI" />;
  return <Navigate replace to={homeRouteForRole(session!.user.role, capabilities)} />;
}
