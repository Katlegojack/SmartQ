import { ApiError, apiRequest } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-counter-workspace]");
const one = (selector, scope = root) => scope?.querySelector(selector) || null;

let account = null;
let counter = null;
let currentTicket = null;
let refreshSequence = 0;

function label(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateTimeLabel(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}

function appointmentLabel(ticket) {
    if (!ticket?.booking_date) return "—";
    const date = new Date(`${ticket.booking_date}T00:00:00`);
    const dateText = Number.isNaN(date.getTime())
        ? ticket.booking_date
        : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
    const timeText = ticket.booking_time ? String(ticket.booking_time).slice(0, 5) : "—";
    return `${dateText} · ${timeText}`;
}

function errorMessage(error, fallback) {
    if (error instanceof ApiError) return error.message || fallback;
    return fallback;
}

function setMessage(text = "", kind = "info") {
    const node = one("[data-counter-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setBusy(button, busyText) {
    if (!button) return () => {};
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    return () => {
        button.disabled = false;
        button.textContent = original;
    };
}

function renderAssignment() {
    if (!counter) return;
    const number = `Counter ${counter.counter_number}`;
    one("[data-counter-chip]").textContent = `${number} · ${label(counter.status)}`;
    one("[data-counter-number]").textContent = counter.counter_number;
    one("[data-counter-status]").textContent = label(counter.status);
    one("[data-counter-type]").textContent = label(counter.queue_type);
    one("[data-assignment-title]").textContent = number;
    one("[data-assignment-branch]").textContent = counter.branch_name || account?.branch_name || "—";
    one("[data-assignment-type]").textContent = label(counter.queue_type);
    one("[data-assignment-status]").textContent = label(counter.status);
}

function renderCurrent(ticket) {
    currentTicket = ticket;
    const currentCard = one("[data-current-card]");
    const freeCard = one("[data-free-card]");

    if (!ticket) {
        currentCard.hidden = true;
        freeCard.hidden = false;
        one("[data-free-copy]").textContent = counter?.status === "open"
            ? "Your counter is open and ready. Let Smart Q select the next eligible customer."
            : counter?.status === "paused"
                ? "Your counter is paused. Resume it before calling another customer."
                : "Open your assigned counter before calling a customer.";
        renderLifecycleActions();
        return;
    }

    freeCard.hidden = true;
    currentCard.hidden = false;
    one("[data-current-queue-number]").textContent = ticket.queue_number || "—";
    one("[data-current-customer]").textContent = ticket.customer_name || "Unnamed customer";
    one("[data-current-service]").textContent = ticket.service_name || "—";
    one("[data-current-type]").textContent = label(ticket.queue_type);
    one("[data-current-appointment]").textContent = appointmentLabel(ticket);
    one("[data-current-checkin]").textContent = dateTimeLabel(ticket.checked_in_at);
    renderLifecycleActions();
}

function renderWaiting(tickets) {
    const filtered = tickets.filter((ticket) => ticket.queue_type === counter.queue_type);
    one("[data-waiting-loading]").hidden = true;
    one("[data-waiting-count]").textContent = filtered.length;
    one("[data-next-number]").textContent = filtered[0]?.queue_number || "—";
    one("[data-counter-type]").textContent = label(counter.queue_type);

    const table = one("[data-waiting-table]");
    const empty = one("[data-waiting-empty]");
    const body = one("[data-waiting-body]");
    body.replaceChildren();

    if (!filtered.length) {
        table.hidden = true;
        empty.hidden = false;
        return;
    }

    empty.hidden = true;
    for (const ticket of filtered) {
        const row = document.createElement("tr");
        const values = [
            ticket.queue_number || "—",
            ticket.customer_name || "—",
            ticket.service_name || "—",
            dateTimeLabel(ticket.checked_in_at),
            label(ticket.status),
        ];
        values.forEach((value, index) => {
            const cell = document.createElement("td");
            if (index < 3) {
                const primary = document.createElement("span");
                primary.className = "table-primary";
                primary.textContent = value;
                cell.append(primary);
            } else {
                cell.textContent = value;
            }
            row.append(cell);
        });
        body.append(row);
    }
    table.hidden = false;
}

function renderLifecycleActions() {
    if (!counter) return;
    const actions = {
        open: one('[data-counter-action="open"]'),
        pause: one('[data-counter-action="pause"]'),
        resume: one('[data-counter-action="resume"]'),
        close: one('[data-counter-action="close"]'),
    };

    Object.values(actions).forEach((button) => {
        button.hidden = true;
        button.disabled = false;
    });

    const callNext = one("[data-call-next]");
    callNext.hidden = false;
    callNext.disabled = true;

    let help = "";
    if (counter.status === "closed") {
        actions.open.hidden = false;
        help = "Open the counter to begin serving customers.";
    } else if (counter.status === "open") {
        actions.pause.hidden = false;
        actions.close.hidden = false;
        actions.close.disabled = Boolean(currentTicket);
        callNext.disabled = Boolean(currentTicket);
        help = currentTicket
            ? "Finish the current customer before closing or calling another. You may pause while service is in progress."
            : "Your counter is open. You can call the next customer, pause, or close the free counter.";
    } else if (counter.status === "paused") {
        actions.resume.hidden = false;
        actions.close.hidden = false;
        actions.close.disabled = Boolean(currentTicket);
        help = currentTicket
            ? "Paused stops new calls, but you can still complete or no-show the current customer."
            : "Resume to call another customer, or close the free paused counter.";
    }

    one("[data-lifecycle-help]").textContent = help;
}

async function getCurrentTicket() {
    try {
        return await apiRequest(`/api/v1/queues/counters/${counter.id}/current/`);
    } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
    }
}

async function refreshOperationalState({ quiet = false } = {}) {
    if (!counter) return;
    const sequence = ++refreshSequence;
    if (!quiet) one("[data-waiting-loading]").hidden = false;

    try {
        const [freshCounter, ticket, waiting] = await Promise.all([
            apiRequest("/api/v1/counters/my/"),
            getCurrentTicket(),
            apiRequest(`/api/v1/queues/branches/${counter.branch}/waiting/?queue_type=${encodeURIComponent(counter.queue_type)}`),
        ]);
        if (sequence !== refreshSequence) return;
        counter = freshCounter;
        renderAssignment();
        renderCurrent(ticket);
        renderWaiting(waiting);
    } catch (error) {
        if (sequence !== refreshSequence) return;
        one("[data-waiting-loading]").hidden = true;
        setMessage(errorMessage(error, "Smart Q could not refresh the counter workspace."), "error");
    }
}

async function runCounterAction(action, button) {
    const restore = setBusy(button, `${label(action)}...`);
    setMessage("");
    try {
        counter = await apiRequest(`/api/v1/counters/${counter.id}/${action}/`, { method: "POST" });
        setMessage(`Counter ${counter.counter_number} is now ${label(counter.status).toLowerCase()}.`, "success");
        await refreshOperationalState({ quiet: true });
    } catch (error) {
        setMessage(errorMessage(error, `Smart Q could not ${action} this counter.`), "error");
    } finally {
        restore();
        renderLifecycleActions();
    }
}

async function callNext(button) {
    const restore = setBusy(button, "Calling...");
    setMessage("");
    try {
        const ticket = await apiRequest(`/api/v1/queues/counters/${counter.id}/call-next/`, { method: "POST" });
        setMessage(`${ticket.queue_number} · ${ticket.customer_name} is now being served at Counter ${counter.counter_number}.`, "success");
        await refreshOperationalState({ quiet: true });
    } catch (error) {
        setMessage(errorMessage(error, "Smart Q could not call the next customer."), "error");
    } finally {
        restore();
        renderLifecycleActions();
    }
}

async function resolveCurrent(action, button) {
    const busyText = action === "complete" ? "Completing..." : "Updating...";
    const restore = setBusy(button, busyText);
    setMessage("");
    try {
        const ticket = await apiRequest(`/api/v1/queues/counters/${counter.id}/${action}/`, { method: "POST" });
        const verb = action === "complete" ? "completed" : "marked as no-show";
        setMessage(`${ticket.queue_number} · ${ticket.customer_name} ${verb}. Counter ${counter.counter_number} is ready for the next customer.`, "success");
        await refreshOperationalState({ quiet: true });
    } catch (error) {
        setMessage(errorMessage(error, "Smart Q could not update the current customer."), "error");
    } finally {
        restore();
        renderLifecycleActions();
    }
}

function bindEvents() {
    one("[data-retry-assignment]")?.addEventListener("click", bootstrapCounter);
    one("[data-refresh-workspace]")?.addEventListener("click", async (event) => {
        const restore = setBusy(event.currentTarget, "Refreshing...");
        setMessage("");
        await refreshOperationalState();
        restore();
    });

    for (const button of root.querySelectorAll("[data-counter-action]")) {
        button.addEventListener("click", () => runCounterAction(button.dataset.counterAction, button));
    }

    one("[data-call-next]")?.addEventListener("click", (event) => callNext(event.currentTarget));
    one("[data-complete-current]")?.addEventListener("click", (event) => resolveCurrent("complete", event.currentTarget));
    one("[data-no-show-current]")?.addEventListener("click", (event) => resolveCurrent("no-show", event.currentTarget));
}

async function bootstrapCounter() {
    if (!root) return;
    one("[data-counter-loading]").hidden = false;
    one("[data-unassigned-state]").hidden = true;
    one("[data-counter-content]").hidden = true;
    setMessage("");

    try {
        account = await getCurrentAccount();
        if (!account) {
            const next = encodeURIComponent(window.location.pathname);
            window.location.replace(`/login/?next=${next}`);
            return;
        }
        if (account.role !== "counter_staff") {
            window.location.replace(routeForRole(account.role));
            return;
        }

        try {
            counter = await apiRequest("/api/v1/counters/my/");
        } catch (error) {
            if (error instanceof ApiError && error.status === 404) {
                one("[data-counter-loading]").hidden = true;
                one("[data-counter-chip]").textContent = "No counter assigned";
                one("[data-unassigned-state]").hidden = false;
                return;
            }
            throw error;
        }

        one("[data-counter-loading]").hidden = true;
        one("[data-counter-content]").hidden = false;
        renderAssignment();
        await refreshOperationalState();
    } catch (error) {
        one("[data-counter-loading]").hidden = true;
        setMessage(errorMessage(error, "Smart Q could not load your assigned counter."), "error");
    }
}

if (root) {
    bindEvents();
    bootstrapCounter();
}
