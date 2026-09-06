import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import { useCurrentAccountQuery } from "../auth";
import {
  EmptyState,
  ErrorState,
  Field,
  FormMessage,
  Metric,
  PageLoading,
  SectionHeader,
  StatusPill,
  WorkspaceShell,
} from "../components";
import type { Branch, BranchService, QueueEvent } from "../types";

type Report = {
  summary: {
    events: number;
    checked_in: number;
    called: number;
    completed: number;
    no_show: number;
    cancelled: number;
  };
  timing: {
    average_actual_wait_minutes: number | null;
    average_service_minutes: number | null;
  };
  outcomes: {
    completion_rate_percent: number | null;
    no_show_rate_percent: number | null;
  };
  services: Array<{
    service_id: number;
    service_name: string;
    checked_in: number;
    completed: number;
    no_show: number;
    cancelled: number;
  }>;
};

type ForecastingSummary = {
  model_status: "data_collection" | string;
  machine_learning_enabled: boolean;
  observations: number;
  wait_labels: number;
  service_labels: number;
  baseline_wait_mae_minutes: number | null;
  baseline_wait_bias_minutes: number | null;
  service_target_mae_minutes: number | null;
  service_target_bias_minutes: number | null;
};

type Pause = {
  pause_impact: {
    id: number;
    is_active: boolean;
    reason: string;
    booking_date: string;
    service_name?: string;
  };
  service?: { name?: string };
  reason?: string;
  is_active?: boolean;
};

function isoOffset(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toLocaleDateString("en-CA");
}

function minuteValue(value: number | null) {
  return value == null ? "—" : `${value} min`;
}

export function HistoryPage() {
  const account = useCurrentAccountQuery();
  const client = useQueryClient();
  const [branchId, setBranchId] = useState("");
  const [start, setStart] = useState(isoOffset(-29));
  const [end, setEnd] = useState(isoOffset(0));
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (account.data?.branch_id) setBranchId(String(account.data.branch_id));
  }, [account.data?.branch_id]);

  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => api<Branch[]>("/api/v1/branches/"),
    enabled: account.data?.role === "system_admin",
  });
  const report = useQuery({
    queryKey: ["history", "report", branchId, start, end],
    queryFn: () => api<Report>(
      `/api/v1/queues/branches/${branchId}/reports/operational/?start_date=${start}&end_date=${end}`,
    ),
    enabled: Boolean(branchId),
  });
  const forecasting = useQuery({
    queryKey: ["history", "forecasting", branchId, start, end],
    queryFn: () => api<ForecastingSummary>(
      `/api/v1/queues/branches/${branchId}/reports/forecasting/?start_date=${start}&end_date=${end}`,
    ),
    enabled: Boolean(branchId),
  });
  const events = useQuery({
    queryKey: ["history", "events", branchId],
    queryFn: () => api<{ events: QueueEvent[] }>(`/api/v1/queues/branches/${branchId}/events/`),
    enabled: Boolean(branchId),
  });
  const pauses = useQuery({
    queryKey: ["history", "pauses", branchId],
    queryFn: () => api<{ pauses: Pause[] }>(`/api/v1/rescheduling/branches/${branchId}/pauses/`),
    enabled: Boolean(branchId),
  });
  const services = useQuery({
    queryKey: ["branch-services", branchId],
    queryFn: () => api<BranchService[]>(`/api/v1/services/branches/${branchId}/`),
    enabled: Boolean(branchId),
  });

  const pauseAction = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api(path, { method: "POST", body }),
    onSuccess: async () => {
      setMessage("Operation updated.");
      setFormError("");
      await Promise.all([
        client.invalidateQueries({ queryKey: ["history", "pauses", branchId] }),
        client.invalidateQueries({ queryKey: ["history", "events", branchId] }),
        client.invalidateQueries({ queryKey: ["history", "report", branchId] }),
        client.invalidateQueries({ queryKey: ["history", "forecasting", branchId] }),
      ]);
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  if (account.isLoading) return <PageLoading />;
  if (!account.data) return <Navigate to="/staff-login/" replace />;
  if (!["branch_manager", "system_admin"].includes(account.data.role)) {
    return <Navigate to="/app/" replace />;
  }

  const operational = report.data;
  const forecast = forecasting.data;

  return <WorkspaceShell
    account={account.data}
    title="History & recovery control"
    subtitle="Operational evidence, service disruption and recovery in one place."
  >
    <div className="history-toolbar">
      {account.data.role === "system_admin" ? <Field label="Branch">
        <select value={branchId} onChange={(event) => setBranchId(event.target.value)}>
          <option value="">Select branch</option>
          {branches.data?.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
        </select>
      </Field> : null}
      <Field label="From"><input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></Field>
      <Field label="To"><input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></Field>
    </div>

    {branchId && operational ? <section className="manager-metrics history-metrics">
      <Metric label="Events" value={operational.summary.events} />
      <Metric label="Completed" value={operational.summary.completed} />
      <Metric label="No shows" value={operational.summary.no_show} />
      <Metric label="Actual wait" value={minuteValue(operational.timing.average_actual_wait_minutes)} />
      <Metric
        label="Completion"
        value={operational.outcomes.completion_rate_percent == null ? "—" : `${operational.outcomes.completion_rate_percent}%`}
      />
    </section> : null}

    {branchId ? <section className="surface surface--flat">
      <SectionHeader eyebrow="Forecasting foundation" title="Data collection quality" />
      {forecasting.isError ? <ErrorState error={forecasting.error} message="Could not load forecasting observation quality." /> : forecast ? <>
        <p className="muted">
          Smart Q is collecting labelled operational observations and measuring the current deterministic baseline.
          No machine-learning model is active yet.
        </p>
        <section className="manager-metrics history-metrics">
          <Metric label="Observations" value={forecast.observations} />
          <Metric label="Wait labels" value={forecast.wait_labels} />
          <Metric label="Service labels" value={forecast.service_labels} />
          <Metric label="Wait baseline MAE" value={minuteValue(forecast.baseline_wait_mae_minutes)} />
          <Metric label="Service target MAE" value={minuteValue(forecast.service_target_mae_minutes)} />
        </section>
      </> : <EmptyState title="No forecasting observations yet" detail="Completed live-queue visits will build this dataset automatically." />}
    </section> : null}

    <div className="history-grid">
      <section className="surface">
        <SectionHeader eyebrow="Audit" title="Recent queue events" />
        {events.data?.events.length ? <div className="event-list">
          {events.data.events.slice(0, 40).map((event) => <article key={event.id}>
            <span className="event-time">{new Date(event.occurred_at).toLocaleString()}</span>
            <div>
              <strong>{event.event_type.replaceAll("_", " ")}</strong>
              <small>
                {event.queue_number || `Booking ${event.booking_id || ""}`}
                {event.actor_username ? ` · ${event.actor_username}` : ""}
              </small>
            </div>
            <StatusPill value={event.to_ticket_status || event.to_booking_status || event.event_type} />
          </article>)}
        </div> : <EmptyState title="No recorded events in this branch" />}
      </section>

      <section className="surface">
        <SectionHeader eyebrow="Disruptions" title="Service pauses" />
        <FormMessage message={message} error={formError} />
        <form className="pause-form" onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          pauseAction.mutate({
            path: `/api/v1/rescheduling/branches/${branchId}/pauses/`,
            body: {
              service_id: Number(form.get("service_id")),
              booking_date: form.get("booking_date"),
              reason: form.get("reason"),
            },
          });
        }}>
          <Field label="Service">
            <select name="service_id" required>
              <option value="">Select service</option>
              {services.data?.map((service) => <option key={service.service_id} value={service.service_id}>{service.service_name}</option>)}
            </select>
          </Field>
          <Field label="Date"><input name="booking_date" type="date" defaultValue={isoOffset(0)} required /></Field>
          <Field label="Reason"><input name="reason" placeholder="Network outage, system issue…" required /></Field>
          <button className="button button--dark">Pause service</button>
        </form>
        <div className="pause-list">
          {pauses.data?.pauses.map((item) => {
            const pause = item.pause_impact;
            return <article key={pause.id}>
              <div>
                <strong>{pause.service_name || item.service?.name || "Service"}</strong>
                <span>{pause.booking_date} · {pause.reason || item.reason || "No reason"}</span>
              </div>
              <StatusPill value={pause.is_active ? "active" : "completed"} />
              {pause.is_active ? <button
                className="text-action"
                onClick={() => pauseAction.mutate({ path: `/api/v1/rescheduling/pauses/${pause.id}/resume/` })}
              >Resume</button> : null}
            </article>;
          })}
        </div>
      </section>
    </div>
  </WorkspaceShell>;
}
