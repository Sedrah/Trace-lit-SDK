import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearApiKey, getApiKey } from "../api/client";
import { useQuery } from "@tanstack/react-query";

const NAV = [
  { to: "/",          label: "Overview",  icon: "⬡" },
  { to: "/traces",    label: "Traces",    icon: "⟳" },
  { to: "/agents",    label: "Agents",    icon: "◈" },
  { to: "/costs",     label: "Costs",     icon: "$" },
  { to: "/failures",  label: "Failures",  icon: "⚠" },
  { to: "/alerts",    label: "Alerts",    icon: "🔔" },
  { to: "/settings",  label: "Settings",  icon: "⚙" },
];

function useOrgId() {
  return useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => {
      const res = await fetch("/api/v1/auth/me", {
        headers: { "X-Tracelit-Api-Key": getApiKey() },
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data.org_id as string;
    },
    staleTime: Infinity,
    retry: false,
  });
}

export function Layout() {
  const navigate = useNavigate();
  const { data: orgId } = useOrgId();

  function signOut() {
    clearApiKey();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200">
          <span className="font-bold text-brand-600 text-lg tracking-tight">Tracelit</span>
          <p className="text-xs text-gray-500 mt-0.5">Agent Monitoring</p>
        </div>

        <nav className="flex-1 py-4 space-y-0.5 px-2">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`
              }
            >
              <span className="text-base w-4 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Signed-in org + sign out */}
        <div className="px-4 py-3 border-t border-gray-200">
          {orgId && (
            <p className="text-xs text-gray-500 truncate mb-1.5">
              <span className="text-gray-400">Signed in as </span>
              <span className="font-medium text-gray-700">{orgId}</span>
            </p>
          )}
          <button
            onClick={signOut}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
