import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { NotificationCenter } from "./components/NotificationCenter";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { retryQuery } from "./lib/errors";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";
const queryClient = new QueryClient({
    defaultOptions: {
        queries: { retry: retryQuery, refetchOnWindowFocus: false },
        mutations: { retry: false },
    },
});
createRoot(document.getElementById("root")).render(<StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppErrorBoundary><AuthProvider>
          <App />
        </AuthProvider></AppErrorBoundary>
        <NotificationCenter />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>);
