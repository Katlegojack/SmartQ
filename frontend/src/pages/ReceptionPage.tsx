import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import { EmptyState, ErrorState, Field, FormMessage, ProtectedWorkspace, SectionHeader, StatusPill } from "../components";
import type { Account, Booking, BranchService, QueueTicket } from "../types";

function ReceptionBody({ account }: { account: Account }) {
  const client = useQueryClient();
  const branchId = account.branch_id;
  const [search, setSearch] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  const today = useQuery({
    queryKey: ["reception", "today"],
    queryFn: () => api<Booking[]>("/api/v1/bookings/reception/today/"),
    refetchInterval: 5_000,
  });
  const waiting = useQuery({
    queryKey: ["queue", "branch", branchId],
    queryFn: () => api<QueueTicket[]>(`/api/v1/queues/branches/${branchId}/waiting/`),
    enabled: Boolean(branchId),
    refetchInterval: 5_000,
  });
  const services = useQuery({
    queryKey: ["branch-services", branchId],
    queryFn: () => api<BranchService[]>(`/api/v1/services/branches/${branchId}/`),
    enabled: Boolean(branchId),
  });
  const searchResults = useQuery({
    queryKey: ["reception", "search", submittedSearch],
    queryFn: () => api<Booking[]>(`/api/v1/bookings/reception/search/?q=${encodeURIComponent(submittedSearch)}`),
    enabled: submittedSearch.length >= 2,
  });

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["reception"] }),
    client.invalidateQueries({ queryKey: ["queue", "branch", branchId] }),
  ]);

  const checkIn = useMutation({
    mutationFn: (id: number) => api<Booking>(`/api/v1/bookings/${id}/staff-check-in/`, { method: "POST" }),
    onSuccess: async () => { setMessage("Customer checked in."); setFormError(""); await refresh(); },
    onError: (error) => setFormError(errorMessage(error, "Could not check in this customer.")),
  });

  const walkIn = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api<Booking>("/api/v1/bookings/reception/walk-ins/", { method: "POST", body: payload }),
    onSuccess: async (booking) => {
      setMessage(`Walk-in added · ${booking.queue_ticket?.queue_number || "queue assigned"}`);
      setFormError("");
      await refresh();
    },
    onError: (error) => setFormError(errorMessage(error, "Could not add this walk-in.")),
  });

  const rows = submittedSearch ? (searchResults.data || []) : (today.data || []);

  async function submitWalkIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setMessage("");
    setFormError("");
    try {
      await walkIn.mutateAsync({
        full_name: data.get("full_name"),
        phone_number: data.get("phone_number"),
        date_of_birth: data.get("date_of_birth"),
        gender: data.get("gender"),
        disability_status: data.get("disability_status") === "on",
        is_pregnant: data.get("is_pregnant") === "on",
        service: Number(data.get("service")),
      });
      form.reset();
    } catch {
      // Mutation onError owns the user-facing message. Keep the form intact.
    }
  }

  return <>
    <FormMessage message={message} error={formError} />
    <section className="reception-command">
      <form className="search-bar" onSubmit={(event) => {
        event.preventDefault();
        const value = search.trim();
        if (value && value.length < 2) {
          setFormError("Enter at least 2 characters to search.");
          return;
        }
        setFormError("");
        setSubmittedSearch(value);
      }}>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search customer, username or booking number" aria-label="Search customer" />
        <button className="button button--dark">Search</button>
        {submittedSearch ? <button type="button" className="button button--quiet" onClick={() => { setSubmittedSearch(""); setSearch(""); setFormError(""); }}>Clear</button> : null}
      </form>
      <span className="live-indicator">Live · 5s</span>
    </section>

    <div className="reception-grid">
      <section className="surface surface--work">
        <SectionHeader eyebrow={submittedSearch ? "Search" : "Today"} title={submittedSearch ? "Search results" : "Today's customers"} />
        {submittedSearch && searchResults.isError ? <ErrorState error={searchResults.error} /> : today.isError ? <ErrorState error={today.error} /> : rows.length ? <div className="work-table">
          <div className="work-head"><span>Customer</span><span>Service</span><span>Time</span><span>Status</span><span /></div>
          {rows.map((booking) => <div className="work-row" key={booking.id}>
            <div><strong>{booking.customer_name}</strong><small>{booking.source === "walk_in" ? "Walk-in" : `Booking #${booking.id}`}</small></div>
            <span>{booking.service_name}</span>
            <span>{booking.booking_time.slice(0, 5)}</span>
            <StatusPill value={booking.is_checked_in ? booking.queue_ticket?.status : booking.status} />
            <div>{!booking.is_checked_in && !["cancelled", "completed", "no_show"].includes(booking.status) ? <button className="text-action" onClick={() => checkIn.mutate(booking.id)} disabled={checkIn.isPending}>Check in</button> : <span className="muted">Ready</span>}</div>
          </div>)}
        </div> : <EmptyState title={submittedSearch ? "No matches" : "No customers waiting for Reception"} />}
      </section>

      <section className="surface surface--queue">
        <SectionHeader eyebrow="Counter handoff" title="Live queue" action={<span className="count-badge">{waiting.data?.length || 0}</span>} />
        {waiting.isError ? <ErrorState error={waiting.error} /> : waiting.data?.length ? <div className="queue-stack">{waiting.data.map((ticket) => <article className="queue-row" key={ticket.id}><strong>{ticket.queue_number}</strong><div><span>{ticket.customer_name}</span><small>{ticket.service_name}</small></div><StatusPill value={ticket.status} /></article>)}</div> : <EmptyState title="Queue is clear" detail="Checked-in customers will appear here automatically." />}
      </section>
    </div>

    <section className="surface surface--flat">
      <SectionHeader eyebrow="Walk-in" title="Add customer" />
      <form className="form-grid form-grid--walkin" onSubmit={submitWalkIn}>
        <Field label="Full name"><input name="full_name" required /></Field>
        <Field label="Phone"><input name="phone_number" /></Field>
        <Field label="Date of birth"><input name="date_of_birth" type="date" required /></Field>
        <Field label="Gender"><select name="gender" required><option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></Field>
        <Field label="Service"><select name="service" required><option value="">Select service</option>{services.data?.map((item) => <option key={item.service_id} value={item.service_id}>{item.service_name}</option>)}</select></Field>
        <label className="check-field"><input type="checkbox" name="disability_status" /><span>Disability</span></label>
        <label className="check-field"><input type="checkbox" name="is_pregnant" /><span>Pregnant</span></label>
        <button className="button button--primary" disabled={walkIn.isPending}>{walkIn.isPending ? "Adding…" : "Add to queue"}</button>
      </form>
    </section>
  </>;
}

export function ReceptionPage() {
  return <ProtectedWorkspace role="receptionist" title="Reception" subtitle="Today's arrivals, check-ins and live handoff to counters.">{(account) => <ReceptionBody account={account} />}</ProtectedWorkspace>;
}
