import { useState, type FormEvent, type ReactNode } from "react";
import { Navigate, NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "./api";
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
  const [securityOpen, setSecurityOpen] = useState(false);
  const [securityBusy, setSecurityBusy] = useState(false);
  const [securityMessage, setSecurityMessage] = useState("");
  const [securityError, setSecurityError] = useState("");

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

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const currentPassword = String(data.get("current_password") || "");
    const newPassword = String(data.get("new_password") || "");
    const confirmation = String(data.get("confirm_password") || "");
    setSecurityMessage("");
    setSecurityError("");

    if (newPassword !== confirmation) {
      setSecurityError("New password and confirmation must match.");
      return;
    }

    setSecurityBusy(true);
    try {
      await api("/api/v1/accounts/change-password/", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      form.reset();
      setSecurityMessage("Password updated. Your current session remains active.");
    } catch (error) {
      setSecurityError(errorMessage(error, "Smart Q could not update the password."));
    } finally {
      setSecurityBusy(false);
    }
  }

  return <div className="workspace-shell">
    <aside className="workspace-nav">
      <a href="/" className="brand"><span className="brand-mark">SQ</span><span><strong>Smart Q</strong><small>Where Time Meets Priority</small></span></a>
      <nav aria-label="Workspace navigation">
        {(navigation[account.role] || []).map(([label, href]) => <NavLink key={href} to={href} className={({ isActive }) => isActive ? "nav-link is-active" : "nav-link"}>{label}</NavLink>)}
      </nav>
      <div className="nav-account">
        <span>{account.first_name || account.username}</span>
        <small>{roleLabels[account.role]}{account.branch_name ? ` · ${account.branch_name}` : ""}</small>
        <div className="nav-account-actions">
          <button className="link-button" type="button" onClick={() => { setSecurityOpen(true); setSecurityMessage(""); setSecurityError(""); }}>Security</button>
          <button className="link-button" type="button" onClick={signOut}>Sign out</button>
        </div>
      </div>
    </aside>
    <div className="workspace-content">
      <header className="workspace-header"><div><span className="eyebrow">{roleLabels[account.role]}</span><h1>{title}</h1>{subtitle ? <p>{subtitle}</p> : null}</div>{secondary}</header>
      {children}
    </div>
    <SimpleDialog open={securityOpen} title="Account security" onClose={() => setSecurityOpen(false)}>
      <p className="dialog-intro">Change your Smart Q password without ending the current trusted session.</p>
      <form onSubmit={changePassword}>
        <Field label="Current password"><input name="current_password" type="password" autoComplete="current-password" required /></Field>
        <Field label="New password"><input name="new_password" type="password" autoComplete="new-password" required /></Field>
        <Field label="Confirm new password"><input name="confirm_password" type="password" autoComplete="new-password" required /></Field>
        <FormMessage message={securityMessage} error={securityError} />
        <div className="dialog-actions">
          <button type="button" className="button button--quiet" onClick={() => setSecurityOpen(false)}>Close</button>
          <button className="button button--primary" disabled={securityBusy}>{securityBusy ? "Updating…" : "Change password"}</button>
        </div>
      </form>
    </SimpleDialog>
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
  return <div className="dialog-backdrop" onMouseDown={onClose}><section className="dialog" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><h2>{title}</h2><button type="button" className="icon-button" onClick={onClose} aria-label="Close">×</button></div>{children}</section></div>;
}

export function preventDefault(handler: (form: HTMLFormElement) => void | Promise<void>) {
  return (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handler(event.currentTarget);
  };
}
