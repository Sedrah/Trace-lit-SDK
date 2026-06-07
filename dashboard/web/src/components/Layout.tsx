import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSessionToken, getSessionToken } from "../api/client";

const NAV = [
  { to: "/",          label: "Overview",  icon: "⬡" },
  { to: "/traces",    label: "Traces",    icon: "⟳" },
  { to: "/agents",    label: "Agents",    icon: "◈" },
  { to: "/costs",     label: "Costs",     icon: "$" },
  { to: "/failures",  label: "Failures",  icon: "⚠" },
  { to: "/alerts",    label: "Alerts",    icon: "🔔" },
  { to: "/settings",  label: "Settings",  icon: "⚙" },
];

function useMe() {
  return useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => {
      const res = await fetch("/api/v1/auth/me", {
        headers: { "X-Tracelit-Session": getSessionToken() },
      });
      if (!res.ok) return null;
      return res.json() as Promise<{ org_id: string; email: string }>;
    },
    staleTime: Infinity,
    retry: false,
  });
}

export function Layout() {
  const navigate = useNavigate();
  const { data: me } = useMe();

  async function signOut() {
    const token = getSessionToken();
    if (token) {
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: { "X-Tracelit-Session": token },
      }).catch(() => {});
    }
    clearSessionToken();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
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

        <div className="px-4 py-3 border-t border-gray-200">
          {me && (
            <p className="text-xs text-gray-500 truncate mb-1.5">
              <span className="text-gray-400">Signed in as </span>
              <span className="font-medium text-gray-700">{me.email ?? me.org_id}</span>
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

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
