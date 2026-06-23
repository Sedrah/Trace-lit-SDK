import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { hasSession } from "./api/client";
import { Layout } from "./components/Layout";
import Agents from "./pages/Agents";
import Alerts from "./pages/Alerts";
import Costs from "./pages/Costs";
import Failures from "./pages/Failures";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Datasets from "./pages/Datasets";
import Prompts from "./pages/Prompts";
import Signup from "./pages/Signup";
import Verify from "./pages/Verify";
import Settings from "./pages/Settings";
import TraceDetail from "./pages/TraceDetail";
import Traces from "./pages/Traces";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  return hasSession() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login"  element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/verify" element={<Verify />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/"                    element={<Overview />} />
            <Route path="/traces"              element={<Traces />} />
            <Route path="/traces/:traceId"     element={<TraceDetail />} />
            <Route path="/agents"              element={<Agents />} />
            <Route path="/costs"               element={<Costs />} />
            <Route path="/prompts"             element={<Prompts />} />
            <Route path="/failures"            element={<Failures />} />
            <Route path="/alerts"              element={<Alerts />} />
            <Route path="/datasets"            element={<Datasets />} />
            <Route path="/settings"            element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
