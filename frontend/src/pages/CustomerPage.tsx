import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, errorMessage } from "../api";
import { EmptyState, ErrorState, Field, FormMessage, Metric, ProtectedWorkspace, SectionHeader, StatusPill } from "../components";
import type { Account, AvailabilityResponse, Booking, Branch, BranchService, CurrentQueue } from "../types";

const FINAL = new Set(["completed", "cancelled", "no_show"]);
const today = () => new Date().toLocaleDateString("en-CA");
const niceDate = (value: string) => new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" }).format(new Date(`${value}T00:00:00`));
const niceTime = (value: string) => value.slice(0, 5);

async function getCurrentQueue(): Promise<CurrentQueue | null> {
  try { return await api<CurrentQueue>("/api/v1/queues/my-current/"); }
  catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error; }
}

function CustomerBody({ account }: { account: Account }) {
  const client = useQueryClient();
  const [branchId, setBranchId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [date, setDate] = useState(today());
  const [slot, setSlot] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  const bookings = useQuery({ queryKey: ["bookings", "mine"], queryFn: () => api<Booking[]>("/api/v1/bookings/my/"), refetchInterval: 5_000 });
  const queue = useQuery({ queryKey: ["queue", "mine"], queryFn: getCurrentQueue, refetchInterval: 5_000 });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => api<Branch[]>("/api/v1/branches/") });
  const services = useQuery({ queryKey: ["branch-services", branchId], queryFn: () => api<BranchService[]>(`/api/v1/services/branches/${branchId}/`), enabled: Boolean(branchId) });
  const availability = useQuery({ queryKey: ["availability", branchId, serviceId, date], queryFn: () => api<AvailabilityResponse>(`/api/v1/services/branches/${branchId}/${serviceId}/availability/?date=${date}`), enabled: Boolean(branchId && serviceId && date), refetchInterval: date === today() ? 15_000 : false });

  const refresh = async () => Promise.all([client.invalidateQueries({ queryKey: ["bookings", "mine"] }), client.invalidateQueries({ queryKey: ["queue", "mine"] })]);
  const createBooking = useMutation({ mutationFn: () => api<Booking>("/api/v1/bookings/", { method: "POST", body: { branch: Number(branchId), service: Number(serviceId), booking_date: date, booking_time: slot, is_pregnant: false } }), onSuccess: async () => { setMessage("Appointment booked."); setFormError(""); setSlot(""); await refresh(); await client.invalidateQueries({ queryKey: ["availability"] }); }, onError: (err) => setFormError(errorMessage(err, "Could not book that appointment.")) });
  const checkIn = useMutation({ mutationFn: (id: number) => api<Booking>(`/api/v1/bookings/${id}/check-in/`, { method: "POST" }), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: (id: number) => api<Booking>(`/api/v1/bookings/${id}/cancel/`, { method: "PATCH", body: {} }), onSuccess: refresh });
  const joinQueue = useMutation({ mutationFn: () => api<Booking>("/api/v1/bookings/walk-ins/", { method: "POST", body: { branch: Number(branchId), service: Number(serviceId), is_pregnant: false } }), onSuccess: async () => { setMessage("You joined the live queue."); await refresh(); }, onError: (err) => setFormError(errorMessage(err, "Could not join the queue.")) });

  const upcoming = useMemo(() => (bookings.data || []).filter((item) => !FINAL.has(item.status) && item.source !== "walk_in").sort((a, b) => `${a.booking_date}${a.booking_time}`.localeCompare(`${b.booking_date}${b.booking_time}`)), [bookings.data]);
  const history = useMemo(() => (bookings.data || []).filter((item) => FINAL.has(item.status)).slice(0, 8), [bookings.data]);
  const next = upcoming[0];
  const activeQueue = queue.data;

  return <>
    {activeQueue ? <section className="priority-panel"><div><span className="eyebrow">Live queue</span><div className="queue-number">{activeQueue.ticket.queue_number}</div><h2>{activeQueue.ticket.service_name}</h2><p>{activeQueue.ticket.branch_name}</p></div><div className="queue-facts"><Metric label="People ahead" value={activeQueue.prediction.people_ahead} /><Metric label="Estimated wait" value={`${activeQueue.prediction.estimated_wait_time} min`} /><Metric label="Status" value={<StatusPill value={activeQueue.ticket.status} />} /></div><div className="queue-message">{activeQueue.ticket.status === "serving" ? `Please go to counter ${activeQueue.ticket.assigned_counter ?? "assigned"}.` : "Keep this page open. Your place updates automatically."}</div></section> : null}

    {!activeQueue && next ? <section className="next-visit"><div><span className="eyebrow">Next visit</span><h2>{next.service_name}</h2><p>{next.branch_name}</p></div><div className="visit-time"><strong>{niceDate(next.booking_date)}</strong><span>{niceTime(next.booking_time)}</span></div><div className="visit-actions"><StatusPill value={next.is_checked_in ? next.queue_ticket?.status : next.status} />{!next.is_checked_in ? <button className="button button--primary" onClick={() => checkIn.mutate(next.id)} disabled={checkIn.isPending}>Check in</button> : null}<button className="button button--quiet button--danger" onClick={() => cancel.mutate(next.id)} disabled={cancel.isPending}>Cancel</button></div></section> : null}

    <div className="content-grid content-grid--customer">
      <section className="surface"><SectionHeader eyebrow="Appointments" title="Book a visit" /><FormMessage message={message} error={formError} /><div className="form-grid"><Field label="Branch"><select value={branchId} onChange={(e) => { setBranchId(e.target.value); setServiceId(""); setSlot(""); }}><option value="">Choose branch</option>{branches.data?.map((branch) => <option key={branch.id} value={branch.id}>{branch.name} · {branch.city}</option>)}</select></Field><Field label="Service"><select value={serviceId} onChange={(e) => { setServiceId(e.target.value); setSlot(""); }} disabled={!branchId}><option value="">Choose service</option>{services.data?.map((service) => <option key={service.service_id} value={service.service_id}>{service.service_name}</option>)}</select></Field><Field label="Date"><input type="date" min={today()} value={date} onChange={(e) => { setDate(e.target.value); setSlot(""); }} /></Field></div><div className="slot-list" aria-label="Available times">{availability.isFetching ? <span className="muted">Checking times…</span> : availability.data?.slots.filter((item) => item.is_available).map((item) => <button key={item.time} className={slot === item.time ? "slot is-selected" : "slot"} onClick={() => setSlot(item.time)}>{niceTime(item.time)}</button>)}</div>{availability.data && !availability.data.slots.some((item) => item.is_available) ? <EmptyState title="No times available" detail="Try another date." /> : null}<div className="form-actions"><button className="button button--primary" disabled={!slot || createBooking.isPending} onClick={() => createBooking.mutate()}>{createBooking.isPending ? "Booking…" : "Book appointment"}</button><button className="button button--secondary" disabled={!branchId || !serviceId || Boolean(activeQueue) || joinQueue.isPending} onClick={() => joinQueue.mutate()}>{activeQueue ? "Already in queue" : "Join live queue now"}</button></div></section>

      <section className="surface"><SectionHeader eyebrow="Upcoming" title="Your visits" />{bookings.isError ? <ErrorState error={bookings.error} /> : upcoming.length ? <div className="list-stack">{upcoming.map((item) => <article className="list-row" key={item.id}><div><strong>{item.service_name}</strong><span>{item.branch_name}</span></div><div><strong>{niceDate(item.booking_date)}</strong><span>{niceTime(item.booking_time)}</span></div><StatusPill value={item.is_checked_in ? item.queue_ticket?.status : item.status} /><div className="row-actions">{!item.is_checked_in ? <button className="text-action" onClick={() => checkIn.mutate(item.id)}>Check in</button> : null}<button className="text-action text-action--danger" onClick={() => cancel.mutate(item.id)}>Cancel</button></div></article>)}</div> : <EmptyState title="No upcoming visits" detail="Book an appointment when you are ready." />}</section>
    </div>

    {history.length ? <section className="surface surface--flat"><SectionHeader eyebrow="Recent" title="History" /><div className="list-stack">{history.map((item) => <article className="list-row list-row--history" key={item.id}><div><strong>{item.service_name}</strong><span>{item.branch_name}</span></div><div><strong>{niceDate(item.booking_date)}</strong><span>{niceTime(item.booking_time)}</span></div><StatusPill value={item.status} /></article>)}</div></section> : null}
  </>;
}

export function CustomerPage() {
  return <ProtectedWorkspace role="customer" title="My Smart Q" subtitle="Appointments and live queue status, in one place.">{(account) => <CustomerBody account={account} />}</ProtectedWorkspace>;
}
