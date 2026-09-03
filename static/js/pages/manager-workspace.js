import { ApiError, apiRequest } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-manager-workspace]");

const state = {
    account: null,
    branchId: null,
    dashboard: null,
    staff: [],
    refreshSequence: 0,
};

const loading = root?.querySelector("[data-manager-loading]") || null;
const content = root?.querySelector("[data-manager-content]") || null;
const message = root?.querySelector("[data-manager-message]") || null;
const dateInput = root?.querySelector("[data-dashboard-date]") || null;
const refreshButton = root?.querySelector("[data-refresh-dashboard]") || null;
const counterBody = root?.querySelector("[data-counter-body]") || null;
const serviceList = root?.querySelector("[data-service-list]") || null;
const serviceEmpty = root?.querySelector("[data-service-empty]") || null;

function setText(selector, value) {
    const node = root?.querySelector(selector);
    if (node) node.textContent = value ?? "—";
}

function titleCase(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function localDateValue() {
    const now = new Date();
    const offset = now.getTimezoneOffset();
    return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10);
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime())
        ? value
        : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function formatClock(value) {
    if (!value) return "—";
    const [hours = "00", minutes = "00"] = String(value).split(":");
    const date = new Date();
    date.setHours(Number(hours), Number(minutes), 0, 0);
    return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
}

function setMessage(text, kind = "error") {
    if (!message) return;
    message.textContent = text || "";
    message.dataset.kind = kind;
    message.hidden = !text;
}

function setBusy(isBusy) {
    if (loading) loading.hidden = !isBusy;
    if (content) content.hidden = isBusy;
    if (refreshButton) refreshButton.disabled = isBusy;
}

function dashboardUrl() {
    const date = dateInput?.value || localDateValue();
    return `/api/v1/dashboard/branches/${state.branchId}/?date=${encodeURIComponent(date)}`;
}

function renderOverview(dashboard) {
    const branch = dashboard.branch || {};
    const customers = dashboard.customers || {};
    const totals = dashboard.lifecycle_totals || {};
    const checkIn = dashboard.check_in || {};

    setText("[data-manager-title]", `${branch.name || "Branch"} operations`);
    setText("[data-branch-name]", branch.name || "Branch operations");
    setText("[data-branch-city]", branch.city || "—");
    setText(
        "[data-branch-hours]",
        `${formatClock(branch.opening_time)}–${formatClock(branch.closing_time)}`,
    );
    setText("[data-report-date]", formatDate(dashboard.date));

    setText("[data-metric-total]", customers.total_customers ?? 0);
    setText("[data-metric-active]", customers.active_customers ?? 0);
    setText("[data-metric-completed]", totals.completed ?? 0);
    setText("[data-metric-checked-in]", checkIn.checked_in ?? 0);
}

function renderQueueActivity(dashboard) {
    const totals = dashboard.lifecycle_totals || {};
    const queueStats = dashboard.queue_statistics || {};
    const priority = queueStats.priority || {};
    const general = queueStats.general || {};
    const sources = dashboard.booking_sources || {};
    const checkIn = dashboard.check_in || {};

    const totalTickets = Object.values(totals).reduce(
        (sum, value) => sum + (Number(value) || 0),
        0,
    );
    setText("[data-lifecycle-total]", `${totalTickets} tickets`);
    setText("[data-life-scheduled]", totals.scheduled ?? 0);
    setText("[data-life-waiting]", totals.waiting ?? 0);
    setText("[data-life-serving]", totals.serving ?? 0);
    setText("[data-life-completed]", totals.completed ?? 0);
    setText("[data-life-no-show]", totals.no_show ?? 0);
    setText("[data-life-cancelled]", totals.cancelled ?? 0);

    setText("[data-priority-waiting]", priority.waiting ?? 0);
    setText("[data-priority-serving]", priority.serving ?? 0);
    setText("[data-priority-completed]", priority.completed ?? 0);
    setText("[data-general-waiting]", general.waiting ?? 0);
    setText("[data-general-serving]", general.serving ?? 0);
    setText("[data-general-completed]", general.completed ?? 0);

    setText("[data-source-online]", sources.online ?? 0);
    setText("[data-source-walkin]", sources.walk_in ?? 0);
    setText("[data-not-checked-in]", checkIn.not_checked_in ?? 0);
}

function renderServices(services = []) {
    if (!serviceList || !serviceEmpty) return;
    serviceList.replaceChildren();
    serviceEmpty.hidden = services.length > 0;

    if (!services.length) return;
    const maxCustomers = Math.max(...services.map((service) => Number(service.customers) || 0), 1);

    for (const service of services) {
        const row = document.createElement("div");
        row.className = "service-demand-row";

        const label = document.createElement("div");
        label.className = "service-demand-row__label";
        const name = document.createElement("strong");
        name.textContent = service.service_name || "Service";
        const code = document.createElement("small");
        code.textContent = service.service_code || "—";
        label.append(name, code);

        const bar = document.createElement("div");
        bar.className = "service-demand-bar";
        const fill = document.createElement("span");
        const percentage = Math.round(((Number(service.customers) || 0) / maxCustomers) * 100);
        fill.style.setProperty("--service-width", `${percentage}%`);
        bar.append(fill);

        const count = document.createElement("div");
        count.className = "service-demand-row__count";
        count.textContent = String(service.customers ?? 0);

        row.append(label, bar, count);
        serviceList.append(row);
    }
}

function availableStaffFor(counter) {
    return state.staff.filter(
        (person) => !person.assigned_counter_id || person.assigned_counter_id === counter.id,
    );
}

function statusBadge(status) {
    const badge = document.createElement("span");
    badge.className = `status-badge status-badge--${status || "closed"}`;
    badge.textContent = titleCase(status || "closed");
    return badge;
}

function counterNameCell(counter) {
    const cell = document.createElement("td");
    const wrapper = document.createElement("div");
    wrapper.className = "counter-name";
    const name = document.createElement("strong");
    name.textContent = `Counter ${counter.counter_number}`;
    const busy = document.createElement("small");
    busy.textContent = counter.is_busy ? "Serving customer" : "No active customer";
    wrapper.append(name, busy);
    cell.append(wrapper);
    return cell;
}

function currentCustomerCell(counter) {
    const cell = document.createElement("td");
    const current = counter.current_customer;
    if (!current) {
        cell.textContent = "—";
        return cell;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "current-ticket";
    const number = document.createElement("strong");
    number.textContent = current.queue_number || "—";
    const detail = document.createElement("small");
    detail.textContent = `${current.customer_name || "Customer"} · ${current.service || "Service"}`;
    wrapper.append(number, detail);
    cell.append(wrapper);
    return cell;
}

function staffingCell(counter) {
    const cell = document.createElement("td");

    if (counter.status !== "closed" || counter.is_busy) {
        const note = document.createElement("span");
        note.className = "assignment-meta";
        note.textContent = "Close and free the counter before changing staff.";
        cell.append(note);
        return cell;
    }

    if (counter.assigned_staff_id) {
        const button = document.createElement("button");
        button.className = "btn btn--secondary btn--sm";
        button.type = "button";
        button.textContent = "Unassign";
        button.dataset.unassignCounter = String(counter.id);
        cell.append(button);
        return cell;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "staff-action";
    const select = document.createElement("select");
    select.className = "input";
    select.dataset.staffSelect = String(counter.id);

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Choose Counter Staff";
    select.append(placeholder);

    for (const person of availableStaffFor(counter)) {
        if (person.assigned_counter_id) continue;
        const option = document.createElement("option");
        option.value = String(person.id);
        option.textContent = person.display_name || person.username;
        select.append(option);
    }

    const button = document.createElement("button");
    button.className = "btn btn--primary btn--sm";
    button.type = "button";
    button.textContent = "Assign";
    button.dataset.assignCounter = String(counter.id);

    if (select.options.length === 1) {
        select.disabled = true;
        button.disabled = true;
        placeholder.textContent = "No available staff";
    }

    wrapper.append(select, button);
    cell.append(wrapper);
    return cell;
}

function renderCounters(counterData = {}) {
    if (!counterBody) return;
    const summary = counterData.summary || {};
    const counters = counterData.counters || [];

    setText("[data-counter-open]", summary.open ?? 0);
    setText("[data-counter-busy]", summary.busy ?? 0);
    setText("[data-counter-free]", summary.free ?? 0);
    setText("[data-counter-unstaffed]", summary.unstaffed ?? 0);

    counterBody.replaceChildren();

    for (const counter of counters) {
        const row = document.createElement("tr");
        row.append(counterNameCell(counter));

        const queue = document.createElement("td");
        queue.textContent = titleCase(counter.queue_type);
        row.append(queue);

        const status = document.createElement("td");
        status.append(statusBadge(counter.status));
        row.append(status);

        const assigned = document.createElement("td");
        assigned.textContent = counter.assigned_staff_username || "Unstaffed";
        row.append(assigned);

        row.append(currentCustomerCell(counter));
        row.append(staffingCell(counter));
        counterBody.append(row);
    }

    if (!counters.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.textContent = "No counters are configured for this branch.";
        row.append(cell);
        counterBody.append(row);
    }
}

function renderDashboard(dashboard) {
    renderOverview(dashboard);
    renderQueueActivity(dashboard);
    renderServices(dashboard.services || []);
    renderCounters(dashboard.counters || {});
}

async function refreshWorkspace({ silent = false } = {}) {
    if (!state.branchId) return;
    const sequence = ++state.refreshSequence;
    if (!silent) setBusy(true);
    setMessage("");

    try {
        const [dashboard, staff] = await Promise.all([
            apiRequest(dashboardUrl()),
            apiRequest(`/api/v1/counters/branches/${state.branchId}/counter-staff/`),
        ]);
        if (sequence !== state.refreshSequence) return;
        state.dashboard = dashboard;
        state.staff = staff || [];
        renderDashboard(dashboard);
        if (content) content.hidden = false;
    } catch (error) {
        if (sequence !== state.refreshSequence) return;
        const detail = error instanceof ApiError
            ? error.message
            : "Smart Q could not load this branch dashboard.";
        setMessage(detail);
    } finally {
        if (sequence === state.refreshSequence) {
            if (loading) loading.hidden = true;
            if (refreshButton) refreshButton.disabled = false;
        }
    }
}

async function mutateStaffing(counterId, action, staffUserId = null, button = null) {
    if (button) button.disabled = true;
    setMessage("");
    try {
        const options = { method: "POST" };
        if (action === "assign") options.body = { staff_user_id: Number(staffUserId) };
        await apiRequest(`/api/v1/counters/${counterId}/${action}/`, options);
        setMessage(
            action === "assign" ? "Counter Staff assigned." : "Counter Staff unassigned.",
            "success",
        );
        await refreshWorkspace({ silent: true });
    } catch (error) {
        setMessage(
            error instanceof ApiError ? error.message : "The staffing change could not be completed.",
        );
        if (button) button.disabled = false;
    }
}

counterBody?.addEventListener("click", async (event) => {
    const assignButton = event.target.closest("[data-assign-counter]");
    if (assignButton) {
        const counterId = assignButton.dataset.assignCounter;
        const select = counterBody.querySelector(`[data-staff-select="${counterId}"]`);
        if (!select?.value) {
            setMessage("Choose an available Counter Staff member first.");
            return;
        }
        await mutateStaffing(counterId, "assign", select.value, assignButton);
        return;
    }

    const unassignButton = event.target.closest("[data-unassign-counter]");
    if (unassignButton) {
        await mutateStaffing(
            unassignButton.dataset.unassignCounter,
            "unassign",
            null,
            unassignButton,
        );
    }
});

refreshButton?.addEventListener("click", () => refreshWorkspace());
dateInput?.addEventListener("change", () => refreshWorkspace());

async function bootstrap() {
    if (!root) return;
    if (dateInput) dateInput.value = localDateValue();

    try {
        const account = await getCurrentAccount();
        if (!account) {
            const next = encodeURIComponent(window.location.pathname);
            window.location.replace(`/login/?next=${next}`);
            return;
        }
        if (account.role !== "branch_manager") {
            window.location.replace(routeForRole(account.role));
            return;
        }
        if (!account.branch_id) {
            setBusy(false);
            setMessage("This Branch Manager account has no assigned branch. A System Admin must correct the account scope.");
            return;
        }

        state.account = account;
        state.branchId = account.branch_id;
        await refreshWorkspace();
    } catch (error) {
        setBusy(false);
        setMessage("Smart Q could not initialise the Branch Manager workspace. Refresh or sign in again.");
    }
}

bootstrap();
