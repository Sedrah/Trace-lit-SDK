import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Agents from "./pages/Agents";
import Alerts from "./pages/Alerts";
import Costs from "./pages/Costs";
import Failures from "./pages/Failures";
import Overview from "./pages/Overview";
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

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/"                    element={<Overview />} />
            <Route path="/traces"              element={<Traces />} />
            <Route path="/traces/:traceId"     element={<TraceDetail />} />
            <Route path="/agents"              element={<Agents />} />
            <Route path="/costs"               element={<Costs />} />
            <Route path="/failures"            element={<Failures />} />
            <Route path="/alerts"              element={<Alerts />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
