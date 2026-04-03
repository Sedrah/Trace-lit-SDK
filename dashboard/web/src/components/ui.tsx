/**
 * Small, focused UI primitives used across pages.
 * No external component library — just Tailwind + React.
 */

import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-gray-200 bg-white">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card (used on Overview)
// ---------------------------------------------------------------------------

export function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "green" | "red" | "blue" | "gray";
}) {
  const colours = {
    green: "text-green-600",
    red: "text-red-600",
    blue: "text-brand-600",
    gray: "text-gray-700",
  };
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${colours[accent ?? "gray"]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: "bg-green-100 text-green-700",
    error:   "bg-red-100   text-red-700",
    timeout: "bg-yellow-100 text-yellow-700",
    partial: "bg-orange-100 text-orange-700",
  };
  const cls = map[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Framework pill
// ---------------------------------------------------------------------------

export function FrameworkBadge({ framework }: { framework: string }) {
  const map: Record<string, string> = {
    langchain: "bg-purple-100 text-purple-700",
    langgraph: "bg-indigo-100 text-indigo-700",
    crewai:    "bg-sky-100    text-sky-700",
    raw:       "bg-gray-100   text-gray-600",
  };
  const cls = map[framework] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {framework}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Loading / error states
// ---------------------------------------------------------------------------

export function LoadingSpinner({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-gray-400 gap-3">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="mx-6 my-4 rounded-md bg-red-50 border border-red-200 p-4">
      <p className="text-sm font-medium text-red-800">Something went wrong</p>
      <p className="text-sm text-red-600 mt-1">{message}</p>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-gray-400">
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table primitives
// ---------------------------------------------------------------------------

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">{children}</table>
    </div>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide bg-gray-50 border-b border-gray-200">
      {children}
    </th>
  );
}

export function Td({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <td className={`px-4 py-3 border-b border-gray-100 text-gray-700 ${className}`}>
      {children}
    </td>
  );
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

export function Button({
  children,
  onClick,
  variant = "primary",
  size = "md",
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger";
  size?: "sm" | "md";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const base = "inline-flex items-center gap-1.5 font-medium rounded-md transition-colors disabled:opacity-50";
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm" };
  const variants = {
    primary:   "bg-brand-500 text-white hover:bg-brand-600",
    secondary: "bg-white text-gray-700 border border-gray-200 hover:bg-gray-50",
    danger:    "bg-red-500 text-white hover:bg-red-600",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${sizes[size]} ${variants[variant]}`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Cost formatter — always show in USD
// ---------------------------------------------------------------------------

export function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.0001) return `$${usd.toFixed(8)}`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}
