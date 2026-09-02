import { ApiError, apiRequest, fieldErrors } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-reception-workspace]");

const one = (selector, scope = root) => scope?.querySelector(selector) || null;
const all = (selector, scope = root) => [...(scope?.querySelectorAll(selector) || [])];

let account = null;
let branchId = null;
let queueRequestSequence = 0;
let searchRequestSequence = 0;

function label(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateLabel(value) {
    if (!value) return "—";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function timeLabel(value) {
    if (!value) return "—";
    return String(value).slice(0, 5);
}

function dateTimeLabel(value) {
    if (!value) return "—";
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

function badge(status, queueType = "") {
    const normalized = String(status || "").toLowerCase();
    if (queueType === "priority") return "badge badge--priority";
    if (queueType === "general") return "badge badge--general";
    if (normalized === "waiting") return "badge badge--waiting";
    if (normalized === "scheduled") return "badge badge--scheduled";
    if (["cancelled", "no_show"].includes(normalized)) return "badge badge--danger";
    if (["completed", "confirmed"].includes(normalized)) return "badge badge--success";
    return "badge badge--neutral";
}

function clearSearchStates() {
    one("[data-search-idle]").hidden = true;
    one("[data-search-loading]").hidden = true;
    one("[data-search-empty]").hidden = true;
    one("[data-search-results]").hidden = true;
}

function canCheckIn(booking) {
    const finalStates = new Set(["cancelled", "completed", "no_show"]);
    return !booking.is_checked_in && !finalStates.has(booking.status);
}

function renderSearchResults(bookings) {
    clearSearchStates();
    if (!bookings.length) {
        one("[data-search-empty]").hidden = false;
        return;
    }

    const body = one("[data-search-body]");
    body.replaceChildren();

    for (const booking of bookings) {
        const ticket = booking.queue_ticket || {};
        const row = document.createElement("tr");

        const customerCell = document.createElement("td");
        customerCell.innerHTML = `<span class="table-primary"></span><span class="table-secondary"></span>`;
        customerCell.querySelector(".table-primary").textContent = booking.customer_name || "Unnamed customer";
        customerCell.querySelector(".table-secondary").textContent = booking.source === "walk_in" ? "Guest walk-in" : "Registered customer";

        const appointmentCell = document.createElement("td");
        appointmentCell.innerHTML = `<span class="table-primary"></span><span class="table-secondary"></span>`;
        appointmentCell.querySelector(".table-primary").textContent = dateLabel(booking.booking_date);
        appointmentCell.querySelector(".table-secondary").textContent = timeLabel(booking.booking_time);

        const serviceCell = document.createElement("td");
        serviceCell.innerHTML = `<span class="table-primary"></span><span class="table-secondary"></span>`;
        serviceCell.querySelector(".table-primary").textContent = booking.service_name || "—";
        serviceCell.querySelector(".table-secondary").textContent = booking.branch_name || account?.branch_name || "—";

        const bookingCell = document.createElement("td");
        bookingCell.innerHTML = `<span class="table-primary"></span><span class="table-secondary"></span>`;
        bookingCell.querySelector(".table-primary").textContent = `#${booking.id}`;
        bookingCell.querySelector(".table-secondary").textContent = label(booking.status);

        const queueCell = document.createElement("td");
        const queueNumber = document.createElement("span");
        queueNumber.className = "table-primary";
        queueNumber.textContent = ticket.queue_number || "Not created";
        const queueStatus = document.createElement("span");
        queueStatus.className = badge(ticket.status, ticket.queue_type);
        queueStatus.textContent = ticket.queue_type ? `${label(ticket.queue_type)} · ${label(ticket.status)}` : "—";
        queueCell.append(queueNumber, queueStatus);

        const actionCell = document.createElement("td");
        if (canCheckIn(booking)) {
            const button = document.createElement("button");
            button.className = "btn btn--primary btn--sm";
            button.type = "button";
            button.dataset.checkIn = String(booking.id);
            button.textContent = "Check in";
            actionCell.append(button);
        } else {
            const state = document.createElement("span");
            state.className = badge(ticket.status || booking.status);
            state.textContent = booking.is_checked_in ? "Checked in" : label(booking.status);
            actionCell.append(state);
        }

        row.append(customerCell, appointmentCell, serviceCell, bookingCell, queueCell, actionCell);
        body.append(row);
    }

    one("[data-search-results]").hidden = false;
}

async function searchBookings(query) {
    const sequence = ++searchRequestSequence;
    clearSearchStates();
    one("[data-search-loading]").hidden = false;
    setMessage("");

    try {
        const bookings = await apiRequest(`/api/v1/bookings/reception/search/?q=${encodeURIComponent(query)}`);
        if (sequence !== searchRequestSequence) return;
        renderSearchResults(bookings);
    } catch (error) {
        if (sequence !== searchRequestSequence) return;
        clearSearchStates();
        one("[data-search-idle]").hidden = false;
        setMessage(errorMessage(error, "Smart Q could not search branch bookings."), "error");
    }
}

async function checkInBooking(bookingId, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Checking in...";
    setMessage("");

    try {
        const booking = await apiRequest(`/api/v1/bookings/${bookingId}/staff-check-in/`, { method: "POST" });
        const queueNumber = booking.queue_ticket?.queue_number || "the live queue";
        setMessage(`${booking.customer_name} checked in successfully. Queue number ${queueNumber}.`, "success");
        const query = one("[data-search-input]").value.trim();
        if (query.length >= 2) await searchBookings(query);
        await refreshQueue();
    } catch (error) {
        let message = errorMessage(error, "Smart Q could not check in this booking.");
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
    one("[data-queue-count]").textContent = tickets.length;
    one("[data-priority-count]").textContent = tickets.filter((ticket) => ticket.queue_type === "priority").length;
    one("[data-general-count]").textContent = tickets.filter((ticket) => ticket.queue_type === "general").length;

    body.replaceChildren();
    if (!tickets.length) {
        table.hidden = true;
        empty.hidden = false;
        return;
    }

    empty.hidden = true;
    for (const ticket of tickets) {
        const row = document.createElement("tr");
        const cells = [
            ticket.queue_number || "—",
            ticket.customer_name || "—",
            ticket.service_name || "—",
            dateTimeLabel(ticket.checked_in_at),
            label(ticket.queue_type),
            label(ticket.status),
        ];
        cells.forEach((value, index) => {
            const cell = document.createElement("td");
            if (index === 0 || index === 1 || index === 2) {
                const primary = document.createElement("span");
                primary.className = "table-primary";
                primary.textContent = value;
                cell.append(primary);
            } else if (index === 4 || index === 5) {
                const state = document.createElement("span");
                state.className = badge(index === 5 ? ticket.status : "", index === 4 ? ticket.queue_type : "");
                state.textContent = value;
                cell.append(state);
            } else {
                cell.textContent = value;
            }
            row.append(cell);
        });
        body.append(row);
    }
    table.hidden = false;
}

async function refreshQueue() {
    if (!branchId) return;
    const sequence = ++queueRequestSequence;
    one("[data-queue-loading]").hidden = false;
    one("[data-queue-empty]").hidden = true;

    try {
        const tickets = await apiRequest(`/api/v1/queues/branches/${branchId}/waiting/`);
        if (sequence !== queueRequestSequence) return;
        renderQueue(tickets);
    } catch (error) {
        if (sequence !== queueRequestSequence) return;
        one("[data-queue-loading]").hidden = true;
        setMessage(errorMessage(error, "Smart Q could not load the branch queue."), "error");
    }
}

async function loadBranchServices() {
    const select = one("[data-walkin-service]");
    select.disabled = true;
    select.innerHTML = '<option value="">Loading branch services...</option>';

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
        select.disabled = false;
        if (select.options.length === 1) {
            select.options[0].textContent = "No active services at this branch";
            select.disabled = true;
        }
    } catch (error) {
        select.replaceChildren(new Option("Services unavailable", ""));
        setWalkInMessage(errorMessage(error, "Smart Q could not load branch services."));
    }
}

function renderWalkInConfirmation(booking) {
    const confirmation = one("[data-walkin-confirmation]");
    const ticket = booking.queue_ticket || {};
    one("[data-confirmation-number]").textContent = ticket.queue_number || "—";
    one("[data-confirmation-customer]").textContent = booking.customer_name || "—";
    one("[data-confirmation-service]").textContent = booking.service_name || "—";
    one("[data-confirmation-type]").textContent = label(ticket.queue_type);
    one("[data-confirmation-status]").textContent = label(ticket.status);
    confirmation.hidden = false;
    confirmation.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    submit.textContent = "Creating ticket...";
    try {
        const booking = await apiRequest("/api/v1/bookings/reception/walk-ins/", {
            method: "POST",
            body: payload,
        });
        setWalkInMessage("Guest walk-in created and added to the live queue.", "success");
        renderWalkInConfirmation(booking);
        await refreshQueue();
    } catch (error) {
        setWalkInMessage(errorMessage(error, "Smart Q could not create the guest walk-in."), "error");
    } finally {
        submit.disabled = false;
        submit.textContent = "Create walk-in ticket";
    }
}

function resetWalkIn() {
    const form = one("[data-walkin-form]");
    form.reset();
    one("[data-walkin-confirmation]").hidden = true;
    one("[data-walkin-pregnancy]").hidden = true;
    setWalkInMessage("");
    one('[name="full_name"]', form)?.focus();
}

function bindEvents() {
    one("[data-search-form]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = one("[data-search-input]").value.trim();
        if (query.length < 2) {
            setMessage("Enter at least two characters before searching.", "error");
            return;
        }
        searchBookings(query);
    });

    one("[data-search-body]")?.addEventListener("click", (event) => {
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
        button.textContent = "Refresh queue";
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

    one("[data-new-walkin]")?.addEventListener("click", resetWalkIn);

    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            one("[data-search-input]")?.focus();
        }
    });
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
        if (!account.branch_id) {
            throw new Error("Receptionist account has no assigned branch.");
        }

        branchId = account.branch_id;
        for (const node of all("[data-reception-branch]")) node.textContent = account.branch_name || `Branch ${branchId}`;
        one("[data-branch-chip]").textContent = account.branch_name || `Branch ${branchId}`;
        one("[data-walkin-dob]").max = new Date().toISOString().slice(0, 10);

        bindEvents();
        await Promise.all([loadBranchServices(), refreshQueue()]);
        loading.hidden = true;
        content.hidden = false;
        one("[data-search-input]")?.focus();
    } catch (error) {
        loading.hidden = true;
        const shellError = one("[data-shell-error]");
        shellError.hidden = false;
        shellError.textContent = errorMessage(error, "Smart Q could not load the reception workspace.");
    }
}

bootstrapReception();
