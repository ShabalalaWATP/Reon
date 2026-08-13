import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { BrowserRouter } from "react-router";

import { AuthProvider } from "../lib/auth/AuthProvider";
import { ThemeProvider } from "../lib/theme/ThemeProvider";
import { ClassificationBanner } from "../components/ClassificationBanner";
import { AppRoutes } from "./AppRoutes";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

const MistReveal = lazy(() => import("../components/MistReveal")
  .then(({ MistReveal: component }) => ({ default: component })));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 15_000 } },
});

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider><BrowserRouter><div className="classified-app"><ClassificationBanner /><div className="classified-app__body"><RouteErrorBoundary onReload={() => window.location.reload()}><AppRoutes /></RouteErrorBoundary></div><Suspense fallback={null}><MistReveal /></Suspense></div></BrowserRouter></AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
