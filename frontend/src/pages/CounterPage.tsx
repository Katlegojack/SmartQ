import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, errorMessage } from "../api";
import { EmptyState, ErrorState, FormMessage, ProtectedWorkspace, SectionHeader, StatusPill } from "../components";
import type { Account, Counter, QueueTicket } from "../types";

async function assignedCounter(): Promise<Counter | null> {
  try {
    return await api<Counter>("/api/v1/counters/my/");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

async function currentTicket(counterId: number | undefined): Promise<QueueTicket | null> {
  if (!counterId) return null;
  try {
    return await api<QueueTicket>(`/api/v1/queues/counters/${counterId}/current/`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

function CounterBody({ account }: { account: Account }) {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const [operationError, setOperationError] = useState("");

  const counter = useQuery({
    queryKey: ["counter", "mine"],
    queryFn: assignedCounter,
    refetchInterval: 5_000,
  });
  const counterId = counter.data?.id;
  const current = useQuery({
    queryKey: ["counter", counterId, "current"],
    queryFn: () => currentTicket(counterId),
    enabled: Boolean(counterId),
    refetchInterval: 5_000,
  });
  const waiting = useQuery({
    queryKey: ["queue", "branch", account.branch_id],
    queryFn: () => api<QueueTicket[]>(`/api/v1/queues/branches/${account.branch_id}/waiting/`),
    enabled: Boolean(account.branch_id),
    refetchInterval: 5_000,
  });

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["counter"] }),
    client.invalidateQueries({ queryKey: ["queue", "branch", account.branch_id] }),
  ]);

  const action = useMutation({
    mutationFn: ({ path }: { path: string }) => api(`/api/v1/${path}`, { method: "POST" }),
    onSuccess: async () => {
      setMessage("Counter state updated.");
      setOperationError("");
      await refresh();
    },
    onError: (error) => {
      setMessage("");
      setOperationError(errorMessage(error, "That counter operation could not be completed."));
    },
  });

  if (counter.isError) return <ErrorState error={counter.error} />;
  if (!counter.data) return <EmptyState title="No counter assigned" detail="Ask your Branch Manager to assign you to a counter before starting service." />;

  const c = counter.data;
  const ticket = current.data;
  const canCall = c.status === "open" && !ticket;
  const working = action.isPending;

  return <>
    <FormMessage message={message} error={operationError} />
    <div className="counter-layout">
      <section className="counter-console">
        <div className="counter-console-head"><div><span className="eyebrow">Counter {c.counter_number}</span><h2>{c.branch_name}</h2></div><StatusPill value={c.status} /></div>
        {current.isError ? <ErrorState error={current.error} message="Could not restore the customer currently assigned to this counter." /> : ticket ? <div className="current-customer">
          <span className="eyebrow">Current customer</span>
          <strong className="ticket-number">{ticket.queue_number}</strong>
          <h3>{ticket.customer_name}</h3>
          <p>{ticket.service_name}</p>
          <div className="counter-primary-actions">
            <button className="button button--primary button--large" disabled={working} onClick={() => action.mutate({ path: `queues/counters/${c.id}/complete/` })}>Complete service</button>
            <button className="button button--quiet button--danger" disabled={working} onClick={() => action.mutate({ path: `queues/counters/${c.id}/no-show/` })}>No show</button>
          </div>
        </div> : <div className="counter-empty">
          <span className="eyebrow">Ready</span>
          <h3>No customer at this counter</h3>
          <p>{c.status === "open" ? "Call the next eligible customer when you are ready." : "Open or resume the counter before calling customers."}</p>
          <button className="button button--primary button--large" disabled={!canCall || working} onClick={() => action.mutate({ path: `queues/counters/${c.id}/call-next/` })}>Call next customer</button>
        </div>}
        <div className="counter-lifecycle">
          <button className="text-action" disabled={c.status === "open" || working} onClick={() => action.mutate({ path: `counters/${c.id}/${c.status === "paused" ? "resume" : "open"}/` })}>{c.status === "paused" ? "Resume counter" : "Open counter"}</button>
          <button className="text-action" disabled={c.status !== "open" || working} onClick={() => action.mutate({ path: `counters/${c.id}/pause/` })}>Pause</button>
          <button className="text-action text-action--danger" disabled={c.status === "closed" || Boolean(ticket) || working} onClick={() => action.mutate({ path: `counters/${c.id}/close/` })}>Close counter</button>
        </div>
      </section>

      <section className="surface">
        <SectionHeader eyebrow="Waiting" title="Next customers" action={<span className="live-indicator">Live · 5s</span>} />
        {waiting.isError ? <ErrorState error={waiting.error} /> : waiting.data?.length ? <div className="queue-stack">{waiting.data.slice(0, 12).map((item) => <article className="queue-row queue-row--counter" key={item.id}><strong>{item.queue_number}</strong><div><span>{item.customer_name}</span><small>{item.service_name}</small></div><StatusPill value={item.queue_type} /></article>)}</div> : <EmptyState title="No one waiting" />}
      </section>
    </div>
  </>;
}

export function CounterPage() {
  return <ProtectedWorkspace role="counter_staff" title="Counter" subtitle="Serve the customer in front of you. Smart Q chooses who comes next.">{(account) => <CounterBody account={account} />}</ProtectedWorkspace>;
}
