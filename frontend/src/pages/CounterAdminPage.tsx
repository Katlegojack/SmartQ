import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import { EmptyState, Field, FormMessage, ProtectedWorkspace, SectionHeader, StatusPill } from "../components";
import type { Branch } from "../types";

type CounterConfig = {
  id: number;
  branch: number;
  branch_name: string;
  counter_number: string;
  queue_type: "general" | "priority";
  status: "open" | "closed" | "paused";
  assigned_staff: number | null;
  assigned_staff_username: string | null;
  is_staffed: boolean;
};

type CounterWrite = {
  path: string;
  method: "POST" | "PATCH";
  body: Record<string, unknown>;
};

function CounterAdminBody() {
  const client = useQueryClient();
  const [editing, setEditing] = useState<CounterConfig | null>(null);
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  const branches = useQuery({
    queryKey: ["admin", "branches"],
    queryFn: () => api<Branch[]>("/api/v1/branches/admin/"),
  });
  const counters = useQuery({
    queryKey: ["admin-counters"],
    queryFn: () => api<CounterConfig[]>("/api/v1/counters/admin/"),
    refetchInterval: 5_000,
  });

  const write = useMutation({
    mutationFn: ({ path, method, body }: CounterWrite) => api<CounterConfig>(path, { method, body }),
    onSuccess: async (_saved, request) => {
      setMessage(request.method === "POST" ? "Counter created. The Branch Manager can now assign Counter Staff." : "Counter configuration updated.");
      setFormError("");
      setEditing(null);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["admin-counters"] }),
        client.invalidateQueries({ queryKey: ["manager"] }),
        client.invalidateQueries({ queryKey: ["counter-staff"] }),
      ]);
    },
    onError: (error) => {
      setMessage("");
      setFormError(errorMessage(error, "Could not save this counter."));
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const branch = Number(form.get("branch"));
    const counterNumber = String(form.get("counter_number") || "").trim();
    const queueType = String(form.get("queue_type") || "general");

    if (!editing && !branch) {
      setFormError("Select an active branch.");
      return;
    }
    if (!counterNumber) {
      setFormError("Counter number is required.");
      return;
    }

    write.mutate({
      path: editing ? `/api/v1/counters/admin/${editing.id}/` : "/api/v1/counters/admin/",
      method: editing ? "PATCH" : "POST",
      body: editing
        ? { counter_number: counterNumber, queue_type: queueType }
        : { branch, counter_number: counterNumber, queue_type: queueType },
    });
  }

  const activeBranches = branches.data?.filter((branch) => branch.is_active) || [];

  return <>
    <FormMessage message={message} error={formError} />
    <div className="admin-split">
      <section className="surface">
        <SectionHeader eyebrow="Operations setup" title="Counters" />
        {counters.isError ? <FormMessage error={errorMessage(counters.error, "Could not load counters.")} /> : null}
        {!counters.isLoading && !counters.data?.length ? <EmptyState
          title="No counters configured"
          detail="Create a counter for each physical serving position. Branch Managers assign Counter Staff after that."
        /> : null}
        <div className="admin-list">
          {counters.data?.map((counter) => <button
            type="button"
            key={counter.id}
            className={editing?.id === counter.id ? "admin-list-row is-selected" : "admin-list-row"}
            onClick={() => { setEditing(counter); setMessage(""); setFormError(""); }}
          >
            <div>
              <strong>{counter.branch_name} · Counter {counter.counter_number}</strong>
              <span>{counter.queue_type} queue · {counter.assigned_staff_username || "Unassigned"}</span>
            </div>
            <StatusPill value={counter.status} />
          </button>)}
        </div>
      </section>

      <section className="surface">
        <SectionHeader
          eyebrow={editing ? "Edit" : "Create"}
          title={editing ? `${editing.branch_name} · Counter ${editing.counter_number}` : "New counter"}
          action={editing ? <button type="button" className="text-action" onClick={() => { setEditing(null); setMessage(""); setFormError(""); }}>New counter</button> : undefined}
        />
        {!activeBranches.length ? <EmptyState title="Create an active branch first" detail="A counter must belong to an active Smart Q branch." /> : <form key={editing?.id || "new"} onSubmit={submit}>
          <Field label="Branch" hint={editing ? "Counter branch is locked after creation to preserve operational history." : undefined}>
            <select name="branch" required={!editing} disabled={Boolean(editing)} defaultValue={editing?.branch || ""}>
              <option value="">Select branch</option>
              {branches.data?.filter((branch) => branch.is_active || branch.id === editing?.branch).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select>
          </Field>
          <Field label="Counter number">
            <input name="counter_number" maxLength={20} required defaultValue={editing?.counter_number || ""} placeholder="e.g. 1" />
          </Field>
          <Field label="Queue type">
            <select name="queue_type" required defaultValue={editing?.queue_type || "general"}>
              <option value="general">General</option>
              <option value="priority">Priority</option>
            </select>
          </Field>
          {editing && editing.status !== "closed" ? <FormMessage error="Close this counter from the Branch Manager workspace before changing its configuration." /> : null}
          <button className="button button--primary" disabled={write.isPending || Boolean(editing && editing.status !== "closed")}>
            {write.isPending ? "Saving…" : editing ? "Update counter" : "Create counter"}
          </button>
        </form>}
      </section>
    </div>
  </>;
}

export function CounterAdminPage() {
  return <ProtectedWorkspace role="system_admin" title="Counters">
    {() => <CounterAdminBody />}
  </ProtectedWorkspace>;
}
