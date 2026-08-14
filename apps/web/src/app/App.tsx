import { QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { BrowserRouter } from "react-router";

import { AuthProvider } from "../lib/auth/AuthProvider";
import { createAppQueryClient } from "../lib/api/queryClient";
import { ThemeProvider } from "../lib/theme/ThemeProvider";
import { ClassificationBanner } from "../components/ClassificationBanner";
import { AppRoutes } from "./AppRoutes";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

const MistReveal = lazy(() =>
  import("../components/MistReveal").then(({ MistReveal: component }) => ({ default: component })),
);

const queryClient = createAppQueryClient();

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <div className="classified-app">
              <ClassificationBanner />
              <div className="classified-app__body">
                <RouteErrorBoundary onReload={() => window.location.reload()}>
                  <AppRoutes />
                </RouteErrorBoundary>
              </div>
              <Suspense fallback={null}>
                <MistReveal />
              </Suspense>
            </div>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
