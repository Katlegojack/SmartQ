import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { errorMessage } from "../api";
import { login, registerCustomer, roleLabels, safeNextRoute } from "../auth";
import { Field, FormMessage } from "../components";
import type { Role } from "../types";

const STAFF_ROLES: Role[] = ["receptionist", "counter_staff", "branch_manager", "system_admin"];

export function LoginPage({ staff = false }: { staff?: boolean }) {
  const [role, setRole] = useState<Role>(staff ? "receptionist" : "customer");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const roles = staff ? STAFF_ROLES : (["customer"] as Role[]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      const account = await login(String(form.get("username") || ""), String(form.get("password") || ""), role);
      queryClient.setQueryData(["account"], account);
      navigate(safeNextRoute(account.role, params.get("next")), { replace: true });
    } catch (err) { setError(errorMessage(err, "Sign in failed.")); }
    finally { setBusy(false); }
  }

  return <div className="auth-page"><section className="auth-brand"><a className="brand brand--light" href="/"><span className="brand-mark">SQ</span><span><strong>Smart Q</strong><small>Where Time Meets Priority</small></span></a><div><span className="eyebrow">{staff ? "Operations access" : "Customer access"}</span><h1>{staff ? "Run the queue." : "Know your place. Keep your time."}</h1><p>{staff ? "Sign in to the workspace for your actual role. Smart Q keeps branch and operational authority on the server." : "Book, check in, track the live queue and get notified when your turn is close."}</p></div></section><section className="auth-panel"><form onSubmit={submit}><div className="auth-title"><span className="eyebrow">Registered users</span><h2>Sign in</h2><p>{params.get("expired") ? "Your session ended. Sign in again to continue." : "Use the account type assigned to you."}</p></div>{staff ? <Field label="Account type"><select value={role} onChange={(event) => setRole(event.target.value as Role)}>{roles.map((item) => <option value={item} key={item}>{roleLabels[item]}</option>)}</select></Field> : null}<Field label="Username"><input name="username" autoComplete="username" required /></Field><Field label="Password"><input name="password" type="password" autoComplete="current-password" required /></Field><FormMessage error={error} /><button className="button button--primary button--full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>{!staff ? <p className="auth-switch">New to Smart Q? <Link to="/register/">Create account</Link></p> : <p className="auth-switch"><Link to="/login/">Customer sign in</Link></p>}</form></section></div>;
}

export function RegisterPage() {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const navigate = useNavigate();
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      await registerCustomer({ username: form.get("username"), password: form.get("password"), first_name: form.get("first_name"), last_name: form.get("last_name"), email: form.get("email"), date_of_birth: form.get("date_of_birth"), gender: form.get("gender"), disability_status: form.get("disability_status") === "on" });
      navigate("/login/?created=1", { replace: true });
    } catch (err) { setError(errorMessage(err, "Account creation failed.")); }
    finally { setBusy(false); }
  }
  return <div className="auth-page"><section className="auth-brand"><a className="brand brand--light" href="/"><span className="brand-mark">SQ</span><span><strong>Smart Q</strong><small>Where Time Meets Priority</small></span></a><div><span className="eyebrow">Customer registration</span><h1>One account. Less waiting.</h1><p>Your profile helps Smart Q apply the queue rules consistently when you book or join a live queue.</p></div></section><section className="auth-panel auth-panel--wide"><form onSubmit={submit}><div className="auth-title"><span className="eyebrow">Create account</span><h2>Your details</h2></div><div className="form-grid"><Field label="First name"><input name="first_name" required /></Field><Field label="Last name"><input name="last_name" required /></Field><Field label="Username"><input name="username" autoComplete="username" required /></Field><Field label="Email"><input name="email" type="email" /></Field><Field label="Date of birth"><input name="date_of_birth" type="date" required /></Field><Field label="Gender"><select name="gender" required><option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></Field><Field label="Password"><input name="password" type="password" autoComplete="new-password" required /></Field><label className="check-field"><input name="disability_status" type="checkbox" /><span>I have a disability</span></label></div><FormMessage error={error} /><button className="button button--primary button--full" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button><p className="auth-switch">Already registered? <Link to="/login/">Sign in</Link></p></form></section></div>;
}
