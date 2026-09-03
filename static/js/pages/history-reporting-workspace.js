import { ApiError, apiRequest, fieldErrors } from "../api/client.js";
import { getCurrentAccount, roleLabel, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-history-workspace]");
const one = (selector, scope = root) => scope?.querySelector(selector) || null;
const all = (selector, scope = root) => [...(scope?.querySelectorAll(selector) || [])];

const state = {
    account: null,
    role: null,
    branchId: null,
    branches: [],
    report: null,
    auditEvents: [],
    services: [],
    pauses: [],
    refreshSequence: 0,
};

function titleCase(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function localDateValue(date = new Date()) {
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 10);
}

function daysBefore(value, days) {
    const date = new Date(`${value}T12:00:00`);
    date.setDate(date.getDate() - days);
    return localDateValue(date);
}

function formatDate(value) {
    if (!value) return "—";
    const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatTime(value) {
    return value ? String(value).slice(0, 5) : "—";
}

function formatDateTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function errorText(error, fallback = "The request could not be completed.") {
    if (!(error instanceof ApiError)) return fallback;
    const fields = fieldErrors(error.data);
    if (fields.length) return fields.map(({ field, message }) => `${titleCase(field)}: ${message}`).join(" ");
    return error.message || fallback;
}

function setMessage(text = "", kind = "error") {
    const node = one("[data-history-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setPauseMessage(text = "", kind = "error") {
    const node = one("[data-pause-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setBusy(button, label) {
    if (!button) return () => {};
    const original = button.textContent;
    button.disabled = true;
    button.textContent = label;
    return () => {
        button.disabled = false;
        button.textContent = original;
    };
}

function textCell(value, secondary = "") {
    const cell = document.createElement("td");
    const primary = document.createElement("span");
    primary.className = "day49-table-primary";
    primary.textContent = value ?? "—";
    cell.append(primary);
    if (secondary) {
        const extra = document.createElement("span");
        extra.className = "day49-table-secondary";
        extra.textContent = secondary;
        cell.append(extra);
    }
    return cell;
}

function plainCell(value) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "—";
    return cell;
}

function currentBranchName() {
    if (state.role === "branch_manager") return state.account?.branch_name || "Your branch";
    return state.branches.find((item) => item.id === Number(state.branchId))?.name || "Selected branch";
}

function configureRoleUI() {
    const manager = state.role === "branch_manager";
    for (const node of all("[data-manager-only]")) node.hidden = !manager;
    for (const node of all("[data-admin-only]")) node.hidden = manager;

    const back = one("[data-history-back]");
    if (back) {
        back.href = manager ? "/app/manager/" : "/app/admin/";
        back.textContent = manager ? "Back to branch operations" : "Back to admin control plane";
    }
    one("[data-history-title]").textContent = manager ? "Branch history & disruption" : "Global history & reporting";
    one("[data-history-scope]").textContent = manager ? "Own branch" : "Global branch selection";
}

function fillAdminBranches() {
    const select = one("[data-history-branch]");
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Choose active branch";
    select.append(blank);
    for (const branch of state.branches.filter((item) => item.is_active)) {
        const option = document.createElement("option");
        option.value = String(branch.id);
        option.textContent = `${branch.name} (${branch.branch_code})`;
        select.append(option);
    }
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
    if (!select.value) {
        const first = state.branches.find((item) => item.is_active);
        if (first) select.value = String(first.id);
    }
    state.branchId = select.value ? Number(select.value) : null;
}

function updateBranchLabels() {
    const name = currentBranchName();
    one("[data-report-branch-label]").textContent = name;
    const shellBranch = one("[data-shell-branch]");
    if (state.role === "system_admin" && shellBranch) shellBranch.textContent = "Global Smart Q scope";
}

function renderMix(containerSelector, emptySelector, values) {
    const container = one(containerSelector);
    const empty = one(emptySelector);
    container.replaceChildren();
    const entries = Object.entries(values || {});
    empty.hidden = entries.length > 0;
    for (const [key, count] of entries) {
        const chip = document.createElement("span");
        chip.className = "day49-chip";
        const label = document.createElement("span");
        label.textContent = titleCase(key);
        const value = document.createElement("strong");
        value.textContent = count;
        chip.append(label, value);
        container.append(chip);
    }
}

function rateText(value) {
    return value === null || value === undefined ? "—" : `${value}%`;
}

function minutesText(value) {
    return value === null || value === undefined ? "—" : `${value} min`;
}

function renderReport() {
    const report = state.report || {};
    const summary = report.summary || {};
    const timing = report.timing || {};
    const outcomes = report.outcomes || {};

    one("[data-report-events]").textContent = summary.events ?? 0;
    one("[data-report-completed]").textContent = summary.completed ?? 0;
    one("[data-report-wait]").textContent = minutesText(timing.average_actual_wait_minutes);
    one("[data-report-service-time]").textContent = minutesText(timing.average_service_minutes);
    one("[data-report-completion-rate]").textContent = rateText(outcomes.completion_rate_percent);
    one("[data-report-no-show-rate]").textContent = rateText(outcomes.no_show_rate_percent);
    one("[data-report-wait-sample]").textContent = `${timing.measured_waits ?? 0} measured waits`;
    one("[data-report-service-sample]").textContent = `${timing.measured_services ?? 0} measured services`;

    renderMix("[data-queue-type-mix]", "[data-queue-type-empty]", report.queue_type_check_ins);
    renderMix("[data-source-mix]", "[data-source-empty]", report.source_check_ins);

    const dailyBody = one("[data-daily-body]");
    dailyBody.replaceChildren();
    const daily = report.daily_activity || [];
    one("[data-daily-empty]").hidden = daily.length > 0;
    for (const item of daily) {
        const row = document.createElement("tr");
        row.append(
            textCell(formatDate(item.date)),
            plainCell(item.checked_in ?? 0),
            plainCell(item.called ?? 0),
            plainCell(item.completed ?? 0),
            plainCell(item.no_show ?? 0),
            plainCell(item.cancelled ?? 0),
        );
        dailyBody.append(row);
    }

    const serviceBody = one("[data-report-service-body]");
    serviceBody.replaceChildren();
    const services = report.services || [];
    one("[data-report-service-empty]").hidden = services.length > 0;
    for (const item of services) {
        const row = document.createElement("tr");
        row.append(
            textCell(item.service_name || "Unknown service", item.service_id ? `Service #${item.service_id}` : ""),
            plainCell(item.checked_in ?? 0),
            plainCell(item.completed ?? 0),
            plainCell(item.no_show ?? 0),
            plainCell(item.cancelled ?? 0),
        );
        serviceBody.append(row);
    }
}

async function loadReport({ quiet = false } = {}) {
    if (!state.branchId) {
        state.report = null;
        renderReport();
        return;
    }
    const start = one("[data-report-start]").value;
    const end = one("[data-report-end]").value;
    if (!start || !end || start > end) {
        if (!quiet) setMessage("Choose a valid reporting period where the start date is not after the end date.");
        return;
    }

    const button = one("[data-load-report]");
    const restore = quiet ? () => {} : setBusy(button, "Loading...");
    try {
        state.report = await apiRequest(
            `/api/v1/queues/branches/${state.branchId}/reports/operational/?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`,
        );
        renderReport();
        if (!quiet) setMessage(`Historical report loaded for ${currentBranchName()}.`, "success");
    } catch (error) {
        setMessage(errorText(error, "Smart Q could not load this historical report."));
    } finally {
        restore();
    }
}

function auditSubject(event) {
    if (event.queue_number) return event.queue_number;
    if (event.booking_id) return `Booking #${event.booking_id}`;
    if (event.counter_id) return `Counter #${event.counter_id}`;
    if (event.ticket_id) return `Ticket #${event.ticket_id}`;
    return "Branch event";
}

function auditTransition(event) {
    const ticketFrom = event.from_ticket_status;
    const ticketTo = event.to_ticket_status;
    if (ticketFrom || ticketTo) return `${titleCase(ticketFrom || "—")} → ${titleCase(ticketTo || "—")}`;
    const bookingFrom = event.from_booking_status;
    const bookingTo = event.to_booking_status;
    if (bookingFrom || bookingTo) return `${titleCase(bookingFrom || "—")} → ${titleCase(bookingTo || "—")}`;
    return "—";
}

function auditActor(event) {
    const actor = event.actor_username || "System";
    const role = event.actor_role ? titleCase(event.actor_role) : titleCase(event.source || "system");
    return { actor, role };
}

function renderAudit() {
    const typeFilter = one("[data-audit-event-filter]").value;
    const query = one("[data-audit-search]").value.trim().toLowerCase();
    const filtered = state.auditEvents.filter((event) => {
        if (typeFilter && event.event_type !== typeFilter) return false;
        if (!query) return true;
        const haystack = [
            event.actor_username,
            event.actor_role,
            event.queue_number,
            event.booking_id,
            event.ticket_id,
            event.counter_id,
            event.event_type,
        ].filter((value) => value !== null && value !== undefined).join(" ").toLowerCase();
        return haystack.includes(query);
    });

    const visible = filtered.slice(0, 100);
    const body = one("[data-audit-body]");
    body.replaceChildren();
    one("[data-audit-empty]").hidden = visible.length > 0;
    one("[data-audit-summary]").textContent = filtered.length > 100
        ? `Showing the most recent 100 of ${filtered.length} matching events (${state.auditEvents.length} total loaded).`
        : `${filtered.length} matching event${filtered.length === 1 ? "" : "s"} (${state.auditEvents.length} total loaded).`;

    for (const event of visible) {
        const row = document.createElement("tr");
        const actor = auditActor(event);
        row.append(
            textCell(formatDateTime(event.occurred_at)),
            textCell(titleCase(event.event_type), event.source ? `Source: ${titleCase(event.source)}` : ""),
            textCell(auditSubject(event), event.booking_id && event.queue_number ? `Booking #${event.booking_id}` : ""),
            plainCell(auditTransition(event)),
            textCell(actor.actor, actor.role),
        );
        body.append(row);
    }
}

async function loadAudit({ quiet = false } = {}) {
    if (!state.branchId) {
        state.auditEvents = [];
        renderAudit();
        return;
    }
    const button = one("[data-refresh-audit]");
    const restore = quiet ? () => {} : setBusy(button, "Refreshing...");
    try {
        const data = await apiRequest(`/api/v1/queues/branches/${state.branchId}/events/`);
        state.auditEvents = Array.isArray(data?.events) ? data.events : [];
        renderAudit();
    } catch (error) {
        setMessage(errorText(error, "Smart Q could not load the branch audit trail."));
    } finally {
        restore();
    }
}

function fillPauseServices() {
    const select = one("[data-pause-service]");
    if (!select) return;
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Choose branch service";
    select.append(blank);
    for (const service of state.services) {
        const option = document.createElement("option");
        option.value = String(service.id);
        option.textContent = service.name || service.service_name || `Service #${service.id}`;
        select.append(option);
    }
}

async function loadPauseServices() {
    if (state.role !== "branch_manager" || !state.branchId) return;
    try {
        const data = await apiRequest(`/api/v1/services/branches/${state.branchId}/`);
        state.services = Array.isArray(data) ? data : [];
        fillPauseServices();
    } catch (error) {
        setPauseMessage(errorText(error, "Smart Q could not load branch services."));
    }
}

function pauseImpact(item) {
    return item?.pause_impact || {};
}

function renderPauseDetail(item) {
    const detail = one("[data-pause-detail]");
    if (!item) {
        detail.hidden = true;
        return;
    }
    const impact = pauseImpact(item);
    detail.hidden = false;
    one("[data-pause-detail-title]").textContent = impact.service || "Service disruption";
    const status = one("[data-pause-detail-status]");
    status.textContent = impact.is_active ? "Active" : "Ended";
    status.dataset.state = impact.is_active ? "active" : "ended";
    one("[data-pause-detail-date]").textContent = formatDate(impact.booking_date);
    one("[data-pause-detail-duration]").textContent = `${impact.duration_minutes ?? 0} min`;
    one("[data-pause-detail-capacity]").textContent = `${impact.lost_service_capacity ?? 0} service opportunities`;
    one("[data-pause-detail-affected]").textContent = item.affected_waiting_count ?? 0;
    one("[data-pause-detail-risk]").textContent = item.reschedule_risk_count ?? 0;
    one("[data-pause-detail-reason]").textContent = impact.reason || "No reason recorded.";
    const risk = item.reschedule_risk_tickets || [];
    one("[data-pause-detail-risk-tickets]").textContent = risk.length ? risk.join(", ") : "None currently";
}

function renderPauses() {
    const body = one("[data-pause-body]");
    const empty = one("[data-pause-empty]");
    body.replaceChildren();
    empty.hidden = state.pauses.length > 0;

    for (const item of state.pauses) {
        const impact = pauseImpact(item);
        const row = document.createElement("tr");
        row.append(textCell(impact.service || "Service", formatDate(impact.booking_date)));
        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = "day49-status";
        status.dataset.state = impact.is_active ? "active" : "ended";
        status.textContent = impact.is_active ? "Active" : "Ended";
        statusCell.append(status);
        row.append(statusCell);
        row.append(
            plainCell(`${impact.duration_minutes ?? 0} min`),
            plainCell(item.affected_waiting_count ?? 0),
            plainCell(item.reschedule_risk_count ?? 0),
        );

        const action = document.createElement("td");
        const group = document.createElement("div");
        group.className = "table-actions";
        const details = document.createElement("button");
        details.type = "button";
        details.className = "btn btn--secondary btn--sm";
        details.textContent = "Details";
        details.dataset.pauseDetails = String(impact.id);
        group.append(details);
        if (impact.is_active) {
            const resume = document.createElement("button");
            resume.type = "button";
            resume.className = "btn btn--primary btn--sm";
            resume.textContent = "Resume & process";
            resume.dataset.pauseResume = String(impact.id);
            group.append(resume);
        }
        action.append(group);
        row.append(action);
        body.append(row);
    }

    const active = state.pauses.find((item) => pauseImpact(item).is_active);
    renderPauseDetail(active || state.pauses[0] || null);
}

async function loadPauses({ quiet = false } = {}) {
    if (state.role !== "branch_manager" || !state.branchId) return;
    const button = one("[data-refresh-pauses]");
    const restore = quiet ? () => {} : setBusy(button, "Refreshing...");
    try {
        const data = await apiRequest(`/api/v1/rescheduling/branches/${state.branchId}/pauses/`);
        state.pauses = Array.isArray(data?.pauses) ? data.pauses : [];
        renderPauses();
    } catch (error) {
        setPauseMessage(errorText(error, "Smart Q could not restore disruption state."));
    } finally {
        restore();
    }
}

async function createPause(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = one("[data-pause-submit]");
    const restore = setBusy(submit, "Pausing...");
    setPauseMessage("");
    try {
        const payload = {
            service_id: Number(form.elements.service_id.value),
            booking_date: form.elements.booking_date.value,
            reason: form.elements.reason.value.trim(),
        };
        const result = await apiRequest(`/api/v1/rescheduling/branches/${state.branchId}/pauses/`, {
            method: "POST",
            body: payload,
        });
        setPauseMessage("Service queue paused. Smart Q is now measuring disruption impact.", "success");
        await loadPauses({ quiet: true });
        const createdId = pauseImpact(result).id;
        renderPauseDetail(state.pauses.find((item) => pauseImpact(item).id === createdId) || result);
    } catch (error) {
        setPauseMessage(errorText(error, "Smart Q could not pause this service queue."));
    } finally {
        restore();
    }
}

async function resumePause(id, button) {
    const restore = setBusy(button, "Processing...");
    setPauseMessage("");
    try {
        const data = await apiRequest(`/api/v1/rescheduling/pauses/${id}/resume/`, { method: "POST" });
        const impacts = data?.impact_processing || {};
        const recovery = data?.rescheduling || {};
        setPauseMessage(
            `Service resumed. ${impacts.affected_processed ?? 0} affected customer(s) processed; ${recovery.recommendations_created ?? 0} recovery recommendation(s) created.`,
            "success",
        );
        await Promise.all([loadPauses({ quiet: true }), loadAudit({ quiet: true }), loadReport({ quiet: true })]);
        const match = state.pauses.find((item) => pauseImpact(item).id === Number(id));
        renderPauseDetail(match || data?.disruption || null);
    } catch (error) {
        setPauseMessage(errorText(error, "Smart Q could not resume and process this disruption."));
    } finally {
        restore();
    }
}

async function prepareScope() {
    if (state.role === "branch_manager") {
        if (!state.account.branch_id) throw new Error("This Branch Manager account has no branch assignment.");
        state.branchId = Number(state.account.branch_id);
        return;
    }
    state.branches = await apiRequest("/api/v1/branches/admin/");
    if (!Array.isArray(state.branches)) state.branches = [];
    fillAdminBranches();
}

async function refreshWorkspace({ firstLoad = false } = {}) {
    const sequence = ++state.refreshSequence;
    const loading = one("[data-history-loading]");
    const content = one("[data-history-content]");
    const refresh = one("[data-history-refresh]");
    refresh.disabled = true;
    setMessage("");
    if (firstLoad) {
        loading.hidden = false;
        content.hidden = true;
    }

    try {
        if (state.role === "system_admin" && !state.branches.length) await prepareScope();
        updateBranchLabels();
        const tasks = [loadReport({ quiet: true }), loadAudit({ quiet: true })];
        if (state.role === "branch_manager") tasks.push(loadPauseServices(), loadPauses({ quiet: true }));
        await Promise.all(tasks);
        if (sequence !== state.refreshSequence) return;
        loading.hidden = true;
        content.hidden = false;
    } catch (error) {
        if (sequence !== state.refreshSequence) return;
        loading.hidden = true;
        setMessage(errorText(error, error.message || "Smart Q could not load historical operations."));
    } finally {
        if (sequence === state.refreshSequence) refresh.disabled = false;
    }
}

function bindEvents() {
    one("[data-load-report]")?.addEventListener("click", () => loadReport());
    one("[data-refresh-audit]")?.addEventListener("click", () => loadAudit());
    one("[data-audit-event-filter]")?.addEventListener("change", renderAudit);
    one("[data-audit-search]")?.addEventListener("input", renderAudit);
    one("[data-history-refresh]")?.addEventListener("click", () => refreshWorkspace());
    one("[data-pause-form]")?.addEventListener("submit", createPause);
    one("[data-refresh-pauses]")?.addEventListener("click", () => loadPauses());
    one("[data-history-branch]")?.addEventListener("change", async (event) => {
        state.branchId = event.currentTarget.value ? Number(event.currentTarget.value) : null;
        updateBranchLabels();
        await Promise.all([loadReport({ quiet: true }), loadAudit({ quiet: true })]);
    });

    root?.addEventListener("click", (event) => {
        const details = event.target.closest("[data-pause-details]");
        if (details) {
            const item = state.pauses.find((pause) => pauseImpact(pause).id === Number(details.dataset.pauseDetails));
            renderPauseDetail(item || null);
            one("[data-pause-detail]")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            return;
        }
        const resume = event.target.closest("[data-pause-resume]");
        if (resume) resumePause(Number(resume.dataset.pauseResume), resume);
    });
}

async function bootstrap() {
    if (!root) return;
    const today = localDateValue();
    one("[data-report-end]").value = today;
    one("[data-report-start]").value = daysBefore(today, 29);
    one("[data-pause-date]").value = today;
    bindEvents();

    try {
        state.account = await getCurrentAccount();
        if (!state.account) {
            window.location.replace(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
            return;
        }
        state.role = state.account.role;
        if (!new Set(["branch_manager", "system_admin"]).has(state.role)) {
            window.location.replace(routeForRole(state.role));
            return;
        }
        configureRoleUI();
        if (state.role === "branch_manager") await prepareScope();
        await refreshWorkspace({ firstLoad: true });
    } catch (error) {
        one("[data-history-loading]").hidden = true;
        setMessage(errorText(error, error.message || "Smart Q could not open this management workspace."));
    }
}

bootstrap();
