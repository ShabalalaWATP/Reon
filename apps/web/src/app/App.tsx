import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router";

import { AuthProvider } from "../lib/auth/AuthProvider";
import { ThemeProvider } from "../lib/theme/ThemeProvider";
import { ClassificationBanner } from "../components/ClassificationBanner";
import { AppRoutes } from "./AppRoutes";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 15_000 } },
});

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider><BrowserRouter><div className="classified-app"><ClassificationBanner /><div className="classified-app__body"><AppRoutes /></div></div></BrowserRouter></AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
