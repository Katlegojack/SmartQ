import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import { EmptyState, ErrorState, FormMessage, Metric, ProtectedWorkspace, SectionHeader, StatusPill } from "../components";
import type { Account } from "../types";

type CounterRow = {
  id: number;
  counter_number: string;
  queue_type: string;
  status: string;
  is_staffed: boolean;
  assigned_staff_id: number | null;
  assigned_staff_username: string | null;
  is_busy: boolean;
  current_customer: { queue_number: string; customer_name: string; service: string } | null;
};

type Dashboard = {
  branch: { id: number; name: string; city: string; opening_time: string; closing_time: string };
  customers: { scheduled_customers: number; active_customers: number; resolved_customers: number; total_customers: number };
  lifecycle_totals: Record<string, number>;
  services: Array<{ service_id: number; service_name: string; customers: number }>;
  counters: {
    summary: { total: number; open: number; paused: number; closed: number; staffed: number; unstaffed: number; free: number; busy: number };
    counters: CounterRow[];
  };
};

type Staff = { id: number; display_name: string; assigned_counter_id: number | null };

function ManagerBody({ account }: { account: Account }) {
  const branchId = account.branch_id!;
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const [operationError, setOperationError] = useState("");

  const dashboard = useQuery({
    queryKey: ["manager", branchId],
    queryFn: () => api<Dashboard>(`/api/v1/dashboard/branches/${branchId}/`),
    refetchInterval: 5_000,
  });
  const staff = useQuery({
    queryKey: ["counter-staff", branchId],
    queryFn: () => api<Staff[]>(`/api/v1/counters/branches/${branchId}/counter-staff/`),
  });

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["manager", branchId] }),
    client.invalidateQueries({ queryKey: ["counter-staff", branchId] }),
  ]);

  const counterAction = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api(`/api/v1/${path}`, { method: "POST", body }),
    onSuccess: async () => {
      setMessage("Counter operation updated.");
      setOperationError("");
      await refresh();
    },
    onError: (error) => {
      setMessage("");
      setOperationError(errorMessage(error, "That counter operation could not be completed."));
    },
  });

  if (dashboard.isError) return <ErrorState error={dashboard.error} />;
  if (!dashboard.data) return <EmptyState title="Loading branch operations" />;

  const data = dashboard.data;
  const working = counterAction.isPending;

  return <>
    <FormMessage message={message} error={operationError} />
    <section className="manager-metrics">
      <Metric label="Customers today" value={data.customers.total_customers} detail={`${data.customers.scheduled_customers} scheduled`} />
      <Metric label="Waiting" value={data.lifecycle_totals.waiting || 0} />
      <Metric label="Serving" value={data.lifecycle_totals.serving || 0} />
      <Metric label="Open counters" value={`${data.counters.summary.open}/${data.counters.summary.total}`} />
      <Metric label="Busy counters" value={data.counters.summary.busy} />
    </section>

    <div className="manager-grid">
      <section className="surface">
        <SectionHeader eyebrow="Live floor" title="Counters" action={<span className="live-indicator">Live · 5s</span>} />
        {staff.isError ? <ErrorState error={staff.error} message="Could not load available Counter Staff." /> : null}
        <div className="counter-table">
          <div className="counter-table-head"><span>Counter</span><span>Staff</span><span>Status</span><span>Customer</span><span>Controls</span></div>
          {data.counters.counters.map((counter) => <div className="counter-table-row" key={counter.id}>
            <strong>{counter.counter_number}</strong>
            <div>
              {counter.assigned_staff_username || "Unassigned"}
              {counter.status === "closed" ? <select
                value={counter.assigned_staff_id || ""}
                disabled={working}
                aria-label={`Assign Counter Staff to counter ${counter.counter_number}`}
                onChange={(event) => {
                  const id = Number(event.target.value);
                  if (id && id !== counter.assigned_staff_id) {
                    counterAction.mutate({ path: `counters/${counter.id}/assign/`, body: { staff_user_id: id } });
                  }
                }}
              >
                <option value="">Assign staff</option>
                {staff.data?.filter((person) => !person.assigned_counter_id || person.assigned_counter_id === counter.id).map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}
              </select> : null}
            </div>
            <StatusPill value={counter.status} />
            <div>{counter.current_customer ? <><strong>{counter.current_customer.queue_number}</strong><small>{counter.current_customer.customer_name}</small></> : <span className="muted">Free</span>}</div>
            <div className="row-actions">
              {counter.status === "closed" ? <button className="text-action" disabled={working || !counter.assigned_staff_id} onClick={() => counterAction.mutate({ path: `counters/${counter.id}/open/` })}>Open</button> : counter.status === "paused" ? <button className="text-action" disabled={working} onClick={() => counterAction.mutate({ path: `counters/${counter.id}/resume/` })}>Resume</button> : <button className="text-action" disabled={working} onClick={() => counterAction.mutate({ path: `counters/${counter.id}/pause/` })}>Pause</button>}
              {counter.status === "closed" && counter.assigned_staff_id ? <button className="text-action text-action--danger" disabled={working} onClick={() => counterAction.mutate({ path: `counters/${counter.id}/unassign/` })}>Unassign</button> : null}
            </div>
          </div>)}
        </div>
      </section>

      <section className="surface">
        <SectionHeader eyebrow="Demand" title="Services today" />
        {data.services.length ? <div className="service-pressure">{data.services.map((service) => {
          const max = Math.max(...data.services.map((item) => item.customers), 1);
          return <article key={service.service_id}><div><span>{service.service_name}</span><strong>{service.customers}</strong></div><div className="bar"><span style={{ width: `${Math.max(5, (service.customers / max) * 100)}%` }} /></div></article>;
        })}</div> : <EmptyState title="No service activity yet" />}
      </section>
    </div>
  </>;
}

export function ManagerPage() {
  return <ProtectedWorkspace role="branch_manager" title="Branch operations" subtitle="Live branch state, staffing and customer flow without dashboard clutter.">{(account) => <ManagerBody account={account} />}</ProtectedWorkspace>;
}
