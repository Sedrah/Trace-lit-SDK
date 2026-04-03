import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/",         label: "Overview",  icon: "⬡" },
  { to: "/traces",   label: "Traces",    icon: "⟳" },
  { to: "/agents",   label: "Agents",    icon: "◈" },
  { to: "/costs",    label: "Costs",     icon: "$" },
  { to: "/failures", label: "Failures",  icon: "⚠" },
  { to: "/alerts",   label: "Alerts",    icon: "🔔" },
];

export function Layout() {
  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200">
          <span className="font-bold text-brand-600 text-lg tracking-tight">AMO</span>
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
        <div className="px-4 py-3 border-t border-gray-200 text-xs text-gray-400">
          v0.1.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
