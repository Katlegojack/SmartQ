import type { FormEvent, ReactNode } from "react";
import { Navigate, NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { errorMessage } from "./api";
import { logout, roleLabels, roleRoutes, useCurrentAccountQuery } from "./auth";
import type { Account, Role } from "./types";

export function PageLoading({ label = "Loading" }: { label?: string }) {
  return <div className="page-state"><span className="spinner" aria-hidden="true" /><p>{label}</p></div>;
}

export function ErrorState({ error, message = "Smart Q could not load this view." }: { error: unknown; message?: string }) {
  return <div className="notice notice--error" role="alert">{errorMessage(error, message)}</div>;
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return <div className="empty-state"><strong>{title}</strong>{detail ? <span>{detail}</span> : null}</div>;
}

export function StatusPill({ value }: { value: string | null | undefined }) {
  const normalized = String(value || "unknown").toLowerCase();
  const positive = ["active", "open", "serving", "completed", "confirmed", "applied"].includes(normalized);
  const caution = ["waiting", "pending", "paused", "scheduled"].includes(normalized);
  const negative = ["cancelled", "no_show", "closed", "inactive"].includes(normalized);
  const tone = positive ? "positive" : caution ? "caution" : negative ? "negative" : "neutral";
  return <span className={`status status--${tone}`}>{normalized.replaceAll("_", " ")}</span>;
}

export function SectionHeader({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return <div className="section-heading"><div>{eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}<h2>{title}</h2></div>{action}</div>;
}

export function Metric({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail ? <small>{detail}</small> : null}</div>;
}

export function WorkspaceShell({ account, title, subtitle, children, secondary }: { account: Account; title: string; subtitle?: string; children: ReactNode; secondary?: ReactNode }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const navigation: Partial<Record<Role, Array<[string, string]>>> = {
    customer: [["Overview", "/app/customer/"], ["Recovery", "/app/recovery/"]],
    receptionist: [["Reception", "/app/reception/"]],
    counter_staff: [["Counter", "/app/counter/"]],
    branch_manager: [["Operations", "/app/manager/"], ["History", "/app/history/"]],
    system_admin: [["Administration", "/app/admin/"], ["History", "/app/history/"]],
  };
  async function signOut() {
    await logout();
    queryClient.clear();
    navigate(account.role === "customer" ? "/login/" : "/staff-login/", { replace: true });
  }
  return <div className="workspace-shell">
    <aside className="workspace-nav">
      <a href="/" className="brand"><span className="brand-mark">SQ</span><span><strong>Smart Q</strong><small>Where Time Meets Priority</small></span></a>
      <nav aria-label="Workspace navigation">
        {(navigation[account.role] || []).map(([label, href]) => <NavLink key={href} to={href} className={({ isActive }) => isActive ? "nav-link is-active" : "nav-link"}>{label}</NavLink>)}
      </nav>
      <div className="nav-account"><span>{account.first_name || account.username}</span><small>{roleLabels[account.role]}{account.branch_name ? ` · ${account.branch_name}` : ""}</small><button className="link-button" onClick={signOut}>Sign out</button></div>
    </aside>
    <div className="workspace-content">
      <header className="workspace-header"><div><span className="eyebrow">{roleLabels[account.role]}</span><h1>{title}</h1>{subtitle ? <p>{subtitle}</p> : null}</div>{secondary}</header>
      {children}
    </div>
  </div>;
}

export function ProtectedWorkspace({ role, title, subtitle, children, secondary }: { role: Role; title: string; subtitle?: string; children: (account: Account) => ReactNode; secondary?: ReactNode }) {
  const account = useCurrentAccountQuery();
  if (account.isLoading) return <PageLoading label="Opening Smart Q" />;
  if (account.isError || !account.data) return <Navigate to={role === "customer" ? "/login/" : "/staff-login/"} replace />;
  if (account.data.role !== role) return <Navigate to={roleRoutes[account.data.role]} replace />;
  return <WorkspaceShell account={account.data} title={title} subtitle={subtitle} secondary={secondary}>{children(account.data)}</WorkspaceShell>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}</span>{children}{hint ? <small>{hint}</small> : null}</label>;
}

export function FormMessage({ message, error }: { message?: string; error?: string }) {
  if (!message && !error) return null;
  return <div className={`notice ${error ? "notice--error" : "notice--success"}`} role="status">{error || message}</div>;
}

export function SimpleDialog({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
  if (!open) return null;
  return <div className="dialog-backdrop" onMouseDown={onClose}><section className="dialog" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close">×</button></div>{children}</section></div>;
}

export function preventDefault(handler: (form: HTMLFormElement) => void | Promise<void>) {
  return (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handler(event.currentTarget);
  };
}
