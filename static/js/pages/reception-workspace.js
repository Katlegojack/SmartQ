import { ApiError, apiRequest, fieldErrors } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-reception-workspace]");
const one = (selector, scope = root) => scope?.querySelector(selector) || null;
const all = (selector, scope = root) => [...(scope?.querySelectorAll(selector) || [])];

const AUTO_REFRESH_MS = 15000;

let account = null;
let branchId = null;
let workloadRequestSequence = 0;
let queueRequestSequence = 0;
let searchMode = false;

function label(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function timeLabel(value) {
    if (!value) return "—";
    return String(value).slice(0, 5);
}

function dateLabel(value) {
    if (!value) return "";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function dateTimeLabel(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function setMessage(text = "", kind = "info") {
    const node = one("[data-reception-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setWalkInMessage(text = "", kind = "error") {
    const node = one("[data-walkin-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function errorMessage(error, fallback = "The request could not be completed.") {
    if (!(error instanceof ApiError)) return fallback;
    const fields = fieldErrors(error.data);
    if (fields.length) return fields.map(({ message }) => message).join(" ");
    return error.message || fallback;
}

function createTextCell(primaryText, secondaryText = "") {
    const cell = document.createElement("td");
    const primary = document.createElement("span");
    primary.className = "table-primary";
    primary.textContent = primaryText || "—";
    cell.append(primary);
    if (secondaryText) {
        const secondary = document.createElement("span");
        secondary.className = "table-secondary";
        secondary.textContent = secondaryText;
        cell.append(secondary);
    }
    return cell;
}

function bookingStatus(booking) {
    const ticket = booking.queue_ticket || {};
    if (ticket.status === "waiting") {
        return { text: ticket.queue_number ? `Waiting · ${ticket.queue_number}` : "Waiting", className: "badge badge--waiting" };
    }
    if (ticket.status === "serving") {
        return { text: ticket.queue_number ? `Serving · ${ticket.queue_number}` : "Serving", className: "badge badge--serving" };
    }
    return { text: "Booked", className: "badge badge--booked" };
}

function canCheckIn(booking) {
    const finalStates = new Set(["cancelled", "completed", "no_show"]);
    return !booking.is_checked_in && !finalStates.has(booking.status);
}

function setWorkloadState({ loading = false, empty = false, emptyText = "No customers yet today." } = {}) {
    const loadingNode = one("[data-today-loading]");
    const emptyNode = one("[data-today-empty]");
    const table = one("[data-today-table]");
    loadingNode.hidden = !loading;
    emptyNode.hidden = !empty;
    emptyNode.textContent = emptyText;
    if (loading || empty) table.hidden = true;
}

function renderBookings(bookings, { searched = false } = {}) {
    const body = one("[data-today-body]");
    const table = one("[data-today-table]");
    body.replaceChildren();

    if (!bookings.length) {
        setWorkloadState({
            empty: true,
            emptyText: searched ? "No matching customers." : "No customers yet today.",
        });
        return;
    }

    for (const booking of bookings) {
        const row = document.createElement("tr");
        const sourceLabel = booking.source === "walk_in" ? "Walk-in" : "";
        const customerCell = createTextCell(booking.customer_name || "Customer", sourceLabel);
        const serviceCell = createTextCell(booking.service_name || "—");
        const timeCell = createTextCell(
            timeLabel(booking.booking_time),
            searched ? dateLabel(booking.booking_date) : "",
        );

        const statusInfo = bookingStatus(booking);
        const statusCell = document.createElement("td");
        const statusNode = document.createElement("span");
        statusNode.className = statusInfo.className;
        statusNode.textContent = statusInfo.text;
        statusCell.append(statusNode);

        const actionCell = document.createElement("td");
        if (canCheckIn(booking)) {
            const button = document.createElement("button");
            button.className = "btn btn--primary btn--sm";
            button.type = "button";
            button.dataset.checkIn = String(booking.id);
            button.textContent = "Check in";
            actionCell.append(button);
        } else {
            actionCell.textContent = "—";
        }

        row.append(customerCell, serviceCell, timeCell, statusCell, actionCell);
        body.append(row);
    }

    one("[data-today-loading]").hidden = true;
    one("[data-today-empty]").hidden = true;
    table.hidden = false;
}

async function loadToday({ silent = false } = {}) {
    const sequence = ++workloadRequestSequence;
    if (!silent) setWorkloadState({ loading: true });

    try {
        const bookings = await apiRequest("/api/v1/bookings/reception/today/");
        if (sequence !== workloadRequestSequence || searchMode) return;
        renderBookings(bookings);
    } catch (error) {
        if (sequence !== workloadRequestSequence) return;
        if (!silent) {
            setWorkloadState({ empty: true, emptyText: "Today's customers could not be loaded." });
            setMessage(errorMessage(error, "Smart Q could not load today's customers."), "error");
        }
    }
}

async function searchBookings(query) {
    const sequence = ++workloadRequestSequence;
    searchMode = true;
    one("[data-search-clear]").hidden = false;
    setWorkloadState({ loading: true });
    setMessage("");

    try {
        const bookings = await apiRequest(`/api/v1/bookings/reception/search/?q=${encodeURIComponent(query)}`);
        if (sequence !== workloadRequestSequence || !searchMode) return;
        renderBookings(bookings, { searched: true });
    } catch (error) {
        if (sequence !== workloadRequestSequence) return;
        setWorkloadState({ empty: true, emptyText: "Search could not be completed." });
        setMessage(errorMessage(error, "Smart Q could not search customers."), "error");
    }
}

async function checkInBooking(bookingId, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Checking in...";
    setMessage("");

    try {
        const booking = await apiRequest(`/api/v1/bookings/${bookingId}/staff-check-in/`, { method: "POST" });
        const queueNumber = booking.queue_ticket?.queue_number || "";
        setMessage(`${booking.customer_name} checked in${queueNumber ? ` · ${queueNumber}` : ""}.`, "success");

        if (searchMode) {
            const query = one("[data-search-input]").value.trim();
            if (query.length >= 2) await searchBookings(query);
        } else {
            await loadToday();
        }
        await refreshQueue();
    } catch (error) {
        let message = errorMessage(error, "Smart Q could not check in this customer.");
        if (error instanceof ApiError && error.data?.check_in_opens_at) {
            message = `${message} Opens ${dateTimeLabel(error.data.check_in_opens_at)}.`;
        }
        setMessage(message, "error");
        button.disabled = false;
        button.textContent = original;
    }
}

function renderQueue(tickets) {
    const table = one("[data-queue-table]");
    const loading = one("[data-queue-loading]");
    const empty = one("[data-queue-empty]");
    const body = one("[data-queue-body]");

    loading.hidden = true;
    body.replaceChildren();

    if (!tickets.length) {
        table.hidden = true;
        empty.hidden = false;
        return;
    }

    empty.hidden = true;
    for (const ticket of tickets) {
        const row = document.createElement("tr");
        const queueCell = createTextCell(ticket.queue_number || "—");
        const customerCell = createTextCell(ticket.customer_name || "Customer");
        const serviceCell = createTextCell(ticket.service_name || "—");
        const statusCell = document.createElement("td");
        const statusNode = document.createElement("span");
        statusNode.className = "badge badge--waiting";
        statusNode.textContent = label(ticket.status || "waiting");
        statusCell.append(statusNode);
        row.append(queueCell, customerCell, serviceCell, statusCell);
        body.append(row);
    }
    table.hidden = false;
}

async function refreshQueue({ silent = false } = {}) {
    if (!branchId) return;
    const sequence = ++queueRequestSequence;
    if (!silent) {
        one("[data-queue-loading]").hidden = false;
        one("[data-queue-empty]").hidden = true;
    }

    try {
        const tickets = await apiRequest(`/api/v1/queues/branches/${branchId}/waiting/`);
        if (sequence !== queueRequestSequence) return;
        renderQueue(tickets);
    } catch (error) {
        if (sequence !== queueRequestSequence) return;
        one("[data-queue-loading]").hidden = true;
        if (!silent) setMessage(errorMessage(error, "Smart Q could not load the live queue."), "error");
    }
}

async function loadBranchServices() {
    const select = one("[data-walkin-service]");
    select.disabled = true;
    select.replaceChildren(new Option("Loading services...", ""));

    try {
        const services = await apiRequest(`/api/v1/services/branches/${branchId}/`);
        select.replaceChildren(new Option("Select service", ""));
        for (const item of services) {
            const service = item.service || item;
            const id = service.id ?? item.service_id;
            const name = service.name ?? item.service_name;
            if (id == null || !name) continue;
            select.append(new Option(name, String(id)));
        }
        select.disabled = select.options.length === 1;
        if (select.disabled) select.options[0].textContent = "No services available";
    } catch (error) {
        select.replaceChildren(new Option("Services unavailable", ""));
        setWalkInMessage(errorMessage(error, "Smart Q could not load services."));
    }
}

function resetWalkInForm(form) {
    form.reset();
    one("[data-walkin-pregnancy]").hidden = true;
    one('[name="full_name"]', form)?.focus();
}

async function createWalkIn(form) {
    const submit = one("[data-walkin-submit]");
    const data = new FormData(form);
    const payload = {
        full_name: String(data.get("full_name") || "").trim(),
        phone_number: String(data.get("phone_number") || "").trim(),
        date_of_birth: String(data.get("date_of_birth") || ""),
        gender: String(data.get("gender") || ""),
        disability_status: data.get("disability_status") === "on",
        is_pregnant: data.get("is_pregnant") === "on",
        service: Number(data.get("service")),
    };

    setWalkInMessage("");
    submit.disabled = true;
    submit.textContent = "Adding...";

    try {
        const booking = await apiRequest("/api/v1/bookings/reception/walk-ins/", {
            method: "POST",
            body: payload,
        });
        const queueNumber = booking.queue_ticket?.queue_number || "";
        setWalkInMessage(`${booking.customer_name} added to queue${queueNumber ? ` · ${queueNumber}` : ""}.`, "success");
        resetWalkInForm(form);
        if (!searchMode) await loadToday();
        await refreshQueue();
    } catch (error) {
        setWalkInMessage(errorMessage(error, "Smart Q could not add this walk-in."), "error");
    } finally {
        submit.disabled = false;
        submit.textContent = "Add to queue";
    }
}

function clearSearch() {
    searchMode = false;
    one("[data-search-input]").value = "";
    one("[data-search-clear]").hidden = true;
    setMessage("");
    loadToday();
}

function bindEvents() {
    one("[data-search-form]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = one("[data-search-input]").value.trim();
        if (!query) {
            clearSearch();
            return;
        }
        if (query.length < 2) {
            setMessage("Enter at least two characters.", "error");
            return;
        }
        searchBookings(query);
    });

    one("[data-search-clear]")?.addEventListener("click", clearSearch);

    one("[data-today-body]")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-check-in]");
        if (!button) return;
        checkInBooking(button.dataset.checkIn, button);
    });

    one("[data-queue-refresh]")?.addEventListener("click", async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        button.textContent = "Refreshing...";
        await refreshQueue();
        button.disabled = false;
        button.textContent = "Refresh";
    });

    one("[data-walkin-gender]")?.addEventListener("change", (event) => {
        const pregnancy = one("[data-walkin-pregnancy]");
        const checkbox = one('[name="is_pregnant"]', pregnancy);
        const isFemale = event.target.value === "female";
        pregnancy.hidden = !isFemale;
        if (!isFemale && checkbox) checkbox.checked = false;
    });

    one("[data-walkin-form]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!event.currentTarget.reportValidity()) return;
        createWalkIn(event.currentTarget);
    });

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState !== "visible") return;
        refreshQueue({ silent: true });
        if (!searchMode) loadToday({ silent: true });
    });
}

function startAutoRefresh() {
    window.setInterval(() => {
        if (document.visibilityState !== "visible") return;
        refreshQueue({ silent: true });
        if (!searchMode) loadToday({ silent: true });
    }, AUTO_REFRESH_MS);
}

async function bootstrapReception() {
    if (!root) return;
    const loading = one("[data-reception-loading]");
    const content = one("[data-reception-content]");

    try {
        account = await getCurrentAccount();
        if (!account) {
            window.location.replace(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
            return;
        }
        if (account.role !== "receptionist") {
            window.location.replace(routeForRole(account.role));
            return;
        }
        if (!account.branch_id) throw new Error("Receptionist account has no assigned branch.");

        branchId = account.branch_id;
        for (const node of all("[data-reception-branch]")) node.textContent = account.branch_name || `Branch ${branchId}`;
        one("[data-branch-chip]").textContent = account.branch_name || `Branch ${branchId}`;
        one("[data-walkin-dob]").max = new Date().toISOString().slice(0, 10);

        bindEvents();
        await Promise.all([loadBranchServices(), loadToday(), refreshQueue()]);
        loading.hidden = true;
        content.hidden = false;
        startAutoRefresh();
    } catch (error) {
        loading.hidden = true;
        const shellError = one("[data-shell-error]");
        shellError.hidden = false;
        shellError.textContent = errorMessage(error, "Smart Q could not load reception.");
    }
}

bootstrapReception();
