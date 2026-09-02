import { ApiError, apiRequest } from "../api/client.js";
import { getCurrentAccount } from "../auth/session.js";

const root = document.querySelector("[data-reception-dashboard]");
const loading = root?.querySelector("[data-reception-loading]");
const content = root?.querySelector("[data-reception-content]");
const errorBox = root?.querySelector("[data-reception-error]");
const globalMessage = root?.querySelector("[data-reception-message]");
const searchForm = root?.querySelector("[data-reception-search-form]");
const searchInput = root?.querySelector("[data-reception-search-input]");
const searchSubmit = root?.querySelector("[data-reception-search-submit]");
const searchMessage = root?.querySelector("[data-search-message]");
const searchResults = root?.querySelector("[data-search-results]");
const searchBody = root?.querySelector("[data-search-results-body]");
const searchEmpty = root?.querySelector("[data-search-empty]");
const walkInForm = root?.querySelector("[data-walk-in-form]");
const walkInMessage = root?.querySelector("[data-walk-in-message]");
const walkInSubmit = root?.querySelector("[data-walk-in-submit]");
const walkInService = root?.querySelector("[data-walk-in-service]");
const walkInDob = root?.querySelector("[data-walk-in-dob]");
const walkInGender = root?.querySelector("[data-walk-in-gender]");
const pregnancyField = root?.querySelector("[data-walk-in-pregnancy]");
const queueBody = root?.querySelector("[data-queue-body]");
const queueTable = root?.querySelector("[data-queue-table]");
const queueEmpty = root?.querySelector("[data-queue-empty]");
const queueMessage = root?.querySelector("[data-queue-message]");
const refreshQueueButton = root?.querySelector("[data-refresh-queue]");

let account = null;
let branchServices = [];
let queueFilter = "";
let waitingTickets = [];
let queueRequest = 0;
let searchRequest = 0;

function setText(selector, value) {
    const node = root?.querySelector(selector);
    if (node) node.textContent = value ?? "—";
}

function setMessage(node, text, kind = "error") {
    if (!node) return;
    node.textContent = text || "";
    node.dataset.kind = kind;
    node.hidden = !text;
}

function showFatal(text) {
    if (errorBox) {
        errorBox.textContent = text;
        errorBox.hidden = false;
    }
    if (loading) loading.hidden = true;
}

function formatDate(value) {
    if (!value) return "—";
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function formatTime(value) {
    if (!value) return "—";
    const [hour, minute] = String(value).split(":").map(Number);
    const date = new Date();
    date.setHours(hour, minute, 0, 0);
    return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatDateTime(value) {
    if (!value) return "—";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function firstApiError(error, fallback) {
    if (!(error instanceof ApiError)) return fallback;
    const data = error.data;
    if (!data || typeof data !== "object") return error.message || fallback;
    if (typeof data.detail === "string") return data.detail;
    for (const value of Object.values(data)) {
        if (Array.isArray(value) && value[0]) return String(value[0]);
        if (typeof value === "string") return value;
    }
    return error.message || fallback;
}

function badgeClass(status) {
    const normalized = String(status || "").toLowerCase();
    if (["waiting", "confirmed", "pending", "scheduled"].includes(normalized)) return "badge badge--info";
    if (["completed", "serving"].includes(normalized)) return "badge badge--success";
    if (["cancelled", "no_show"].includes(normalized)) return "badge badge--danger";
    return "badge badge--neutral";
}

function canStaffCheckIn(booking) {
    if (!booking || booking.is_checked_in) return false;
    if (["completed", "cancelled", "no_show"].includes(String(booking.status).toLowerCase())) return false;
    return booking.source !== "walk_in";
}

function renderSearchResults(bookings) {
    if (!searchBody || !searchResults || !searchEmpty) return;
    searchBody.innerHTML = "";
    const rows = Array.isArray(bookings) ? bookings : [];
    searchResults.hidden = rows.length === 0;
    searchEmpty.hidden = rows.length > 0;

    if (!rows.length) {
        searchEmpty.innerHTML = "<strong>No matching bookings</strong><p>Try a different booking ID, name, username, email or guest phone number.</p>";
        return;
    }

    for (const booking of rows) {
        const tr = document.createElement("tr");
        const ticket = booking.queue_ticket || null;
        const action = canStaffCheckIn(booking)
            ? `<button class="btn btn--primary btn--sm" type="button" data-staff-check-in="${booking.id}">Check in</button>`
            : `<span class="table-secondary">${booking.is_checked_in ? "Already active" : "No action"}</span>`;
        tr.innerHTML = `
            <td><span class="table-primary">${booking.customer_name || "Customer"}</span><span class="table-secondary">Booking #${booking.id}</span></td>
            <td><span class="table-primary">${formatDate(booking.booking_date)}</span><span class="table-secondary">${formatTime(booking.booking_time)}</span></td>
            <td><span class="table-primary">${booking.service_name || "—"}</span><span class="table-secondary">${booking.branch_name || "—"}</span></td>
            <td><span class="${badgeClass(booking.status)}">${String(booking.status || "unknown").replaceAll("_", " ")}</span></td>
            <td><span class="table-primary">${ticket?.queue_number || "—"}</span><span class="table-secondary">${ticket?.status || "Not queued"}</span></td>
            <td>${action}</td>`;
        searchBody.appendChild(tr);
    }
}

async function runSearch(query) {
    const trimmed = String(query || "").trim();
    if (trimmed.length < 2) {
        setMessage(searchMessage, "Enter at least 2 characters to search this branch.");
        return;
    }
    const requestId = ++searchRequest;
    setMessage(searchMessage, "Searching branch bookings...", "info");
    if (searchSubmit) searchSubmit.disabled = true;
    try {
        const data = await apiRequest(`/api/v1/bookings/reception/search/?q=${encodeURIComponent(trimmed)}`);
        if (requestId !== searchRequest) return;
        renderSearchResults(data);
        setMessage(searchMessage, data.length ? `${data.length} matching booking${data.length === 1 ? "" : "s"} found.` : "No matching bookings found.", "success");
    } catch (error) {
        if (requestId !== searchRequest) return;
        renderSearchResults([]);
        setMessage(searchMessage, firstApiError(error, "Smart Q could not search branch bookings."));
    } finally {
        if (requestId === searchRequest && searchSubmit) searchSubmit.disabled = false;
    }
}

async function staffCheckIn(bookingId) {
    const button = root?.querySelector(`[data-staff-check-in="${bookingId}"]`);
    if (button) {
        button.disabled = true;
        button.textContent = "Checking in...";
    }
    setMessage(searchMessage, "");
    try {
        const booking = await apiRequest(`/api/v1/bookings/${bookingId}/staff-check-in/`, { method: "POST" });
        setMessage(globalMessage, `${booking.customer_name || "Customer"} is now in the live waiting queue.`, "success");
        await Promise.all([runSearch(searchInput?.value || ""), loadWaitingQueue()]);
    } catch (error) {
        setMessage(searchMessage, firstApiError(error, "This booking could not be checked in."));
        if (button) {
            button.disabled = false;
            button.textContent = "Check in";
        }
    }
}

function renderServiceOptions() {
    if (!walkInService) return;
    walkInService.innerHTML = '<option value="">Select service</option>';
    for (const offering of branchServices) {
        const option = document.createElement("option");
        option.value = String(offering.service_id);
        option.textContent = offering.service_name;
        walkInService.appendChild(option);
    }
    walkInService.disabled = branchServices.length === 0;
}

async function loadBranchServices() {
    branchServices = await apiRequest(`/api/v1/services/branches/${account.branch_id}/`);
    renderServiceOptions();
}

function updatePregnancyVisibility() {
    if (!pregnancyField || !walkInGender) return;
    const visible = walkInGender.value === "female";
    pregnancyField.hidden = !visible;
    if (!visible) {
        const checkbox = pregnancyField.querySelector('input[name="is_pregnant"]');
        if (checkbox) checkbox.checked = false;
    }
}

function renderWaitingQueue(tickets) {
    waitingTickets = Array.isArray(tickets) ? tickets : [];
    const priority = waitingTickets.filter((ticket) => ticket.queue_type === "priority").length;
    const general = waitingTickets.filter((ticket) => ticket.queue_type === "general").length;
    setText("[data-waiting-count]", waitingTickets.length);
    setText("[data-priority-count]", priority);
    setText("[data-general-count]", general);

    if (!queueBody || !queueTable || !queueEmpty) return;
    queueBody.innerHTML = "";
    queueTable.hidden = waitingTickets.length === 0;
    queueEmpty.hidden = waitingTickets.length > 0;
    for (const ticket of waitingTickets) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><span class="queue-number">${ticket.queue_number || "—"}</span></td>
            <td><span class="table-primary">${ticket.customer_name || "Customer"}</span><span class="table-secondary">Booking #${ticket.booking_id}</span></td>
            <td>${ticket.service_name || "—"}</td>
            <td><span class="${ticket.queue_type === "priority" ? "badge badge--success" : "badge badge--neutral"}">${ticket.queue_type || "—"}</span></td>
            <td>${formatDateTime(ticket.checked_in_at)}</td>
            <td><span class="badge badge--info">${ticket.status || "waiting"}</span></td>`;
        queueBody.appendChild(tr);
    }
}

async function loadWaitingQueue() {
    if (!account?.branch_id) return;
    const requestId = ++queueRequest;
    if (refreshQueueButton) {
        refreshQueueButton.disabled = true;
        refreshQueueButton.textContent = "Refreshing...";
    }
    try {
        const suffix = queueFilter ? `?queue_type=${encodeURIComponent(queueFilter)}` : "";
        const tickets = await apiRequest(`/api/v1/queues/branches/${account.branch_id}/waiting/${suffix}`);
        if (requestId !== queueRequest) return;
        renderWaitingQueue(tickets);
        setMessage(queueMessage, "");
    } catch (error) {
        if (requestId !== queueRequest) return;
        setMessage(queueMessage, firstApiError(error, "Smart Q could not load the branch waiting queue."));
    } finally {
        if (requestId === queueRequest && refreshQueueButton) {
            refreshQueueButton.disabled = false;
            refreshQueueButton.textContent = "Refresh queue";
        }
    }
}

async function submitWalkIn() {
    if (!walkInForm || !walkInSubmit) return;
    const data = new FormData(walkInForm);
    const payload = {
        full_name: String(data.get("full_name") || "").trim(),
        phone_number: String(data.get("phone_number") || "").trim(),
        date_of_birth: String(data.get("date_of_birth") || ""),
        gender: String(data.get("gender") || ""),
        disability_status: data.get("disability_status") === "on",
        is_pregnant: data.get("is_pregnant") === "on",
        service: Number(data.get("service")),
    };
    if (!payload.full_name || !payload.date_of_birth || !payload.gender || !payload.service) {
        setMessage(walkInMessage, "Complete the guest name, date of birth, gender and service.");
        return;
    }

    walkInSubmit.disabled = true;
    walkInSubmit.textContent = "Registering...";
    setMessage(walkInMessage, "");
    try {
        const booking = await apiRequest("/api/v1/bookings/reception/walk-ins/", { method: "POST", body: payload });
        const queueNumber = booking.queue_ticket?.queue_number || "allocated queue ticket";
        setMessage(globalMessage, `${booking.customer_name || payload.full_name} registered successfully as ${queueNumber}.`, "success");
        setMessage(walkInMessage, "Guest walk-in created and added to the live waiting queue.", "success");
        walkInForm.reset();
        updatePregnancyVisibility();
        await loadWaitingQueue();
    } catch (error) {
        setMessage(walkInMessage, firstApiError(error, "Smart Q could not register this guest walk-in."));
    } finally {
        walkInSubmit.disabled = false;
        walkInSubmit.textContent = "Register and join queue";
    }
}

async function bootstrapReception() {
    if (!root) return;
    try {
        account = await getCurrentAccount();
        if (!account) return;
        if (account.role !== "receptionist") return;
        if (!account.branch_id) {
            showFatal("Reception requires an assigned branch before this workspace can operate.");
            return;
        }
        setText("[data-reception-branch]", account.branch_name || `Branch ${account.branch_id}`);
        setText("[data-metric-branch]", account.branch_name || `Branch ${account.branch_id}`);
        if (walkInDob) walkInDob.max = new Date().toISOString().slice(0, 10);
        await Promise.all([loadBranchServices(), loadWaitingQueue()]);
        if (loading) loading.hidden = true;
        if (content) content.hidden = false;
    } catch (error) {
        showFatal(firstApiError(error, "Smart Q could not load the reception workspace."));
    }
}

searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch(searchInput?.value || "");
});

searchBody?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-staff-check-in]");
    if (button) staffCheckIn(button.dataset.staffCheckIn);
});

walkInGender?.addEventListener("change", updatePregnancyVisibility);
walkInForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitWalkIn();
});
refreshQueueButton?.addEventListener("click", loadWaitingQueue);
for (const button of root?.querySelectorAll("[data-queue-filter]") || []) {
    button.addEventListener("click", () => {
        queueFilter = button.dataset.queueFilter || "";
        for (const item of root.querySelectorAll("[data-queue-filter]")) item.classList.toggle("is-active", item === button);
        loadWaitingQueue();
    });
}

bootstrapReception();
