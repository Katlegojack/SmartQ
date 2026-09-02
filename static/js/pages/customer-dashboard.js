import { ApiError, apiRequest } from "../api/client.js";
import { getCurrentAccount, logoutAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-customer-dashboard]");
const FINAL = new Set(["completed", "cancelled", "no_show"]);
const labels = {
    pending: "Pending", confirmed: "Confirmed", completed: "Completed",
    cancelled: "Cancelled", no_show: "No show", scheduled: "Scheduled",
    waiting: "Waiting", serving: "Serving", general: "General", priority: "Priority",
};
const eventLabels = {
    ticket_scheduled: "Appointment entered the queue system",
    checked_in: "Checked in",
    called: "Called to a counter",
    completed: "Service completed",
    no_show: "Marked as no show",
    cancelled: "Appointment cancelled",
    rescheduled: "Appointment rescheduled",
    disruption_rescheduled: "Rescheduled after a service disruption",
};

let bookings = [];
let account = null;
let branches = [];
let branchServices = [];
let bookingMode = { kind: "create", booking: null };
let selectedSlot = "";
let availabilityRequest = 0;

function one(selector, context = document) { return context.querySelector(selector); }
function all(selector, context = document) { return [...context.querySelectorAll(selector)]; }
function setText(selector, value, context = document) {
    const element = one(selector, context);
    if (element) element.textContent = value ?? "—";
}
function label(value) { return labels[value] || String(value || "Unknown").replaceAll("_", " "); }
function badge(status) {
    if (["completed", "serving"].includes(status)) return "badge badge--success";
    if (["waiting", "pending"].includes(status)) return "badge badge--info";
    if (["cancelled", "no_show"].includes(status)) return "badge badge--danger";
    return "badge badge--neutral";
}
function appointment(booking) {
    const [year, month, day] = booking.booking_date.split("-").map(Number);
    const [hour = 0, minute = 0, second = 0] = booking.booking_time.split(":").map(Number);
    return new Date(year, month - 1, day, hour, minute, second);
}
function fmtDate(value) {
    return new Intl.DateTimeFormat(undefined, { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).format(value);
}
function fmtTime(value) {
    return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(value);
}
function fmtDateTime(value) {
    const date = value instanceof Date ? value : new Date(value);
    return `${fmtDate(date)}, ${fmtTime(date)}`;
}
function fmtSlotTime(value) {
    const [hour = 0, minute = 0] = String(value).split(":").map(Number);
    const date = new Date(2000, 0, 1, hour, minute);
    return fmtTime(date);
}
function localDateString(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}
function queueNumber(booking) { return booking.queue_ticket?.queue_number || "Not assigned"; }
function displayStatus(booking) { return booking.is_checked_in ? (booking.queue_ticket?.status || booking.status) : booking.status; }
function message(text = "", kind = "info") {
    const element = one("[data-dashboard-message]");
    if (!element) return;
    element.textContent = text;
    element.dataset.kind = kind;
    element.hidden = !text;
}
function showError(text = "") {
    const element = one("[data-dashboard-error]");
    if (!element) return;
    element.textContent = text;
    element.hidden = !text;
}
function setLoading(value) {
    one("[data-dashboard-loading]").hidden = !value;
    one("[data-dashboard-content]").hidden = value;
}
function firstApiError(error, fallback) {
    if (!(error instanceof ApiError)) return fallback;
    if (error.data && typeof error.data === "object") {
        for (const value of Object.values(error.data)) {
            if (Array.isArray(value) && typeof value[0] === "string") return value[0];
            if (typeof value === "string") return value;
        }
    }
    return error.message || fallback;
}

async function myBookings() {
    const data = await apiRequest("/api/v1/bookings/my/");
    return Array.isArray(data) ? data : [];
}
async function currentQueue() {
    try {
        return await apiRequest("/api/v1/queues/my-current/");
    } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
    }
}
async function loadBranches() {
    const data = await apiRequest("/api/v1/branches/");
    branches = Array.isArray(data) ? data : [];
    const select = one("[data-booking-branch]");
    select.replaceChildren(new Option("Select a branch", ""));
    for (const branch of branches) select.add(new Option(`${branch.name} — ${branch.city}`, branch.id));
}
async function loadServices(branchId) {
    const select = one("[data-booking-service]");
    branchServices = [];
    select.replaceChildren(new Option("Loading services...", ""));
    select.disabled = true;
    if (!branchId) {
        select.replaceChildren(new Option("Select a branch first", ""));
        return;
    }
    const data = await apiRequest(`/api/v1/services/branches/${branchId}/`);
    branchServices = Array.isArray(data) ? data : [];
    select.replaceChildren(new Option(branchServices.length ? "Select a service" : "No services available", ""));
    for (const item of branchServices) {
        select.add(new Option(`${item.service_name} — about ${item.average_service_time} min`, item.service_id));
    }
    select.disabled = bookingMode.kind === "reschedule" || !branchServices.length;
}

function renderQueue(data) {
    const panel = one("[data-queue-panel]");
    const empty = one("[data-queue-empty]");
    if (!data) {
        panel.hidden = true;
        empty.hidden = false;
        return;
    }
    panel.hidden = false;
    empty.hidden = true;
    const { ticket, prediction } = data;
    setText("[data-queue-number]", ticket.queue_number);
    setText("[data-queue-service]", ticket.service_name);
    setText("[data-queue-branch]", ticket.branch_name);
    setText("[data-queue-position]", prediction.queue_position);
    setText("[data-queue-ahead]", prediction.people_ahead);
    setText("[data-queue-wait]", `${prediction.estimated_wait_time} min`);
    setText("[data-queue-counter]", ticket.assigned_counter ? `Counter ${ticket.assigned_counter}` : "Waiting for assignment");
    setText("[data-queue-heading]", ticket.status === "serving" ? "You are being served" : "Your live queue");
    const status = one("[data-queue-status]");
    status.className = badge(ticket.status);
    status.textContent = label(ticket.status);
}

function renderNext(booking) {
    const panel = one("[data-next-panel]");
    const empty = one("[data-next-empty]");
    if (!booking) {
        panel.hidden = true;
        empty.hidden = false;
        return;
    }
    panel.hidden = false;
    empty.hidden = true;
    const date = appointment(booking);
    setText("[data-next-service]", booking.service_name);
    setText("[data-next-branch]", booking.branch_name);
    setText("[data-next-date]", fmtDate(date));
    setText("[data-next-time]", fmtTime(date));
    setText("[data-next-queue]", queueNumber(booking));
    const status = one("[data-next-status]");
    status.className = badge(displayStatus(booking));
    status.textContent = label(displayStatus(booking));
    for (const button of all("[data-next-action]")) button.dataset.bookingId = booking.id;
    one('[data-next-action="check-in"]').hidden = booking.is_checked_in || FINAL.has(booking.status);
    one('[data-next-action="reschedule"]').hidden = booking.is_checked_in || FINAL.has(booking.status);
    one('[data-next-action="cancel"]').hidden = FINAL.has(booking.status);
}

function actionButton(action, text, id, klass = "btn btn--quiet btn--sm") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = klass;
    button.dataset.bookingAction = action;
    button.dataset.bookingId = id;
    button.textContent = text;
    return button;
}
function renderRows(selector, items, history = false) {
    const body = one(selector);
    body.replaceChildren();
    for (const booking of items) {
        const row = document.createElement("tr");
        const date = appointment(booking);
        const appointmentCell = document.createElement("td");
        const primary = document.createElement("strong");
        primary.className = "table-primary";
        primary.textContent = fmtDate(date);
        const secondary = document.createElement("span");
        secondary.className = "table-secondary";
        secondary.textContent = fmtTime(date);
        appointmentCell.append(primary, secondary);
        const service = document.createElement("td");
        service.textContent = booking.service_name;
        const branch = document.createElement("td");
        branch.textContent = booking.branch_name;
        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = badge(displayStatus(booking));
        status.textContent = label(displayStatus(booking));
        statusCell.append(status);
        const queue = document.createElement("td");
        queue.textContent = queueNumber(booking);
        const actions = document.createElement("td");
        actions.className = "table-actions";
        actions.append(actionButton("details", "Details", booking.id));
        if (!history && !booking.is_checked_in && !FINAL.has(booking.status)) {
            actions.append(actionButton("check-in", "Check in", booking.id, "btn btn--secondary btn--sm"));
            actions.append(actionButton("reschedule", "Reschedule", booking.id));
        }
        if (!history && !FINAL.has(booking.status)) {
            actions.append(actionButton("cancel", "Cancel", booking.id, "btn btn--quiet btn--sm btn--danger-text"));
        }
        row.append(appointmentCell, service, branch, statusCell, queue, actions);
        body.append(row);
    }
}
function renderBookings() {
    const ordered = [...bookings].sort((a, b) => appointment(a) - appointment(b));
    const upcoming = ordered.filter(item => !FINAL.has(item.status));
    const history = ordered.filter(item => FINAL.has(item.status)).reverse();
    setText("[data-upcoming-count]", upcoming.length);
    setText("[data-history-count]", history.length);
    renderNext(upcoming[0] || null);
    renderRows("[data-upcoming-body]", upcoming);
    renderRows("[data-history-body]", history, true);
    one("[data-upcoming-table]").hidden = !upcoming.length;
    one("[data-upcoming-empty]").hidden = Boolean(upcoming.length);
    one("[data-history-table]").hidden = !history.length;
    one("[data-history-empty]").hidden = Boolean(history.length);
}

async function refresh() {
    message();
    showError();
    setLoading(true);
    try {
        const [items, queue] = await Promise.all([myBookings(), currentQueue()]);
        bookings = items;
        renderQueue(queue);
        renderBookings();
        setLoading(false);
    } catch (error) {
        setLoading(false);
        showError(firstApiError(error, "Smart Q could not load your customer dashboard. Refresh the page and try again."));
    }
}

function setBookingMessage(text = "", kind = "error") {
    const element = one("[data-booking-message]");
    element.textContent = text;
    element.dataset.kind = kind;
    element.hidden = !text;
}
function setBookingStep(step) {
    for (const element of all("[data-step-indicator]")) {
        const value = Number(element.dataset.stepIndicator);
        element.classList.toggle("is-active", value === step);
        element.classList.toggle("is-complete", value < step);
    }
}
function branchById(id) { return branches.find(item => String(item.id) === String(id)); }
function serviceById(id) { return branchServices.find(item => String(item.service_id) === String(id)); }
function resetSlots(help = "Select a branch, service and date to load backend-generated availability.") {
    selectedSlot = "";
    one("[data-slot-grid]").replaceChildren();
    setText("[data-slot-help]", help);
    one("[data-slot-fieldset]").disabled = true;
    one("[data-booking-submit]").disabled = true;
    one("[data-booking-review]").hidden = true;
}
function renderAvailability(data) {
    const grid = one("[data-slot-grid]");
    grid.replaceChildren();
    const slots = Array.isArray(data?.slots) ? data.slots : [];
    const available = slots.filter(slot => slot.is_available);
    if (!available.length) {
        setText("[data-slot-help]", "No appointment times are available for this date. Choose another date.");
        one("[data-slot-fieldset]").disabled = false;
        return;
    }
    setText("[data-slot-help]", `Choose from ${available.length} available time${available.length === 1 ? "" : "s"}. Capacity is revalidated when you confirm.`);
    for (const slot of slots) {
        const labelElement = document.createElement("label");
        labelElement.className = `slot-option${slot.is_available ? "" : " is-full"}`;
        const input = document.createElement("input");
        input.type = "radio";
        input.name = "booking_time";
        input.value = slot.time;
        input.disabled = !slot.is_available;
        input.dataset.slotChoice = "";
        const main = document.createElement("strong");
        main.textContent = fmtSlotTime(slot.time);
        const detail = document.createElement("small");
        detail.textContent = slot.is_available ? `${slot.remaining} place${slot.remaining === 1 ? "" : "s"} left` : "Full";
        labelElement.append(input, main, detail);
        grid.append(labelElement);
    }
    one("[data-slot-fieldset]").disabled = false;
    setBookingStep(4);
}
async function loadAvailability() {
    const branchId = one("[data-booking-branch]").value;
    const serviceId = one("[data-booking-service]").value;
    const bookingDate = one("[data-booking-date]").value;
    resetSlots("Loading backend availability...");
    if (!branchId || !serviceId || !bookingDate) return;
    const requestId = ++availabilityRequest;
    try {
        const data = await apiRequest(`/api/v1/services/branches/${branchId}/${serviceId}/availability/?date=${encodeURIComponent(bookingDate)}`);
        if (requestId !== availabilityRequest) return;
        renderAvailability(data);
    } catch (error) {
        if (requestId !== availabilityRequest) return;
        setText("[data-slot-help]", firstApiError(error, "Smart Q could not load availability for this date."));
        one("[data-slot-fieldset]").disabled = false;
    }
}
function updateReview() {
    const branch = branchById(one("[data-booking-branch]").value);
    const service = serviceById(one("[data-booking-service]").value);
    const dateValue = one("[data-booking-date]").value;
    if (!branch || !service || !dateValue || !selectedSlot) {
        one("[data-booking-review]").hidden = true;
        one("[data-booking-submit]").disabled = true;
        return;
    }
    const [year, month, day] = dateValue.split("-").map(Number);
    setText("[data-review-branch]", branch.name);
    setText("[data-review-service]", service.service_name);
    setText("[data-review-date]", fmtDate(new Date(year, month - 1, day)));
    setText("[data-review-time]", fmtSlotTime(selectedSlot));
    one("[data-booking-review]").hidden = false;
    one("[data-booking-submit]").disabled = false;
    setBookingStep(5);
}
function configurePregnancyField() {
    const field = one("[data-pregnancy-field]");
    const checkbox = one("[data-booking-pregnant]");
    const show = bookingMode.kind === "create" && account?.gender === "female";
    field.hidden = !show;
    if (!show) checkbox.checked = false;
}
async function resetBookingForm({ keepMessage = false } = {}) {
    bookingMode = { kind: "create", booking: null };
    selectedSlot = "";
    const form = one("[data-booking-form]");
    form.reset();
    one("[data-booking-branch]").disabled = false;
    one("[data-booking-service]").disabled = true;
    one("[data-booking-service]").replaceChildren(new Option("Select a branch first", ""));
    one("[data-booking-date]").disabled = true;
    one("[data-booking-date]").min = localDateString();
    resetSlots();
    setText("[data-booking-kicker]", "New appointment");
    setText("[data-booking-heading]", "Book an appointment");
    setText("[data-booking-submit]", "Confirm appointment");
    one("[data-booking-reset]").hidden = true;
    setBookingStep(1);
    configurePregnancyField();
    if (!keepMessage) setBookingMessage();
}
async function beginReschedule(booking) {
    if (!booking || booking.is_checked_in || FINAL.has(booking.status)) return;
    bookingMode = { kind: "reschedule", booking };
    setBookingMessage();
    setText("[data-booking-kicker]", "Reschedule appointment");
    setText("[data-booking-heading]", booking.service_name);
    setText("[data-booking-submit]", "Confirm new time");
    one("[data-booking-reset]").hidden = false;
    one("[data-booking-branch]").value = booking.branch;
    one("[data-booking-branch]").disabled = true;
    await loadServices(booking.branch);
    one("[data-booking-service]").value = booking.service;
    one("[data-booking-service]").disabled = true;
    const dateInput = one("[data-booking-date]");
    dateInput.disabled = false;
    dateInput.min = localDateString();
    dateInput.value = booking.booking_date;
    configurePregnancyField();
    setBookingStep(3);
    await loadAvailability();
    one("[data-booking-workflow]").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function submitBooking(event) {
    event.preventDefault();
    const submit = one("[data-booking-submit]");
    if (submit.disabled || !selectedSlot) return;
    const original = submit.textContent;
    submit.disabled = true;
    submit.textContent = bookingMode.kind === "create" ? "Booking..." : "Rescheduling...";
    setBookingMessage();
    const payload = {
        booking_date: one("[data-booking-date]").value,
        booking_time: selectedSlot,
    };
    let createdId = null;
    try {
        if (bookingMode.kind === "create") {
            payload.branch = Number(one("[data-booking-branch]").value);
            payload.service = Number(one("[data-booking-service]").value);
            payload.is_pregnant = account?.gender === "female" && one("[data-booking-pregnant]").checked;
            const created = await apiRequest("/api/v1/bookings/", { method: "POST", body: payload });
            createdId = created?.id;
        } else {
            createdId = bookingMode.booking.id;
            await apiRequest(`/api/v1/bookings/${createdId}/reschedule/`, { method: "PATCH", body: payload });
        }
        const successKind = bookingMode.kind;
        await refresh();
        const saved = bookings.find(item => String(item.id) === String(createdId));
        await resetBookingForm({ keepMessage: true });
        setBookingMessage(
            successKind === "create"
                ? `Appointment booked${saved?.queue_ticket?.queue_number ? ` with queue reference ${saved.queue_ticket.queue_number}` : ""}. Check in when the six-hour window opens.`
                : `Appointment rescheduled${saved ? ` to ${fmtDateTime(appointment(saved))}` : ""}. A fresh check-in will be required.`,
            "success",
        );
        one("[data-booking-workflow]").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        setBookingMessage(firstApiError(error, "Smart Q could not save this appointment. Review the selection and try again."), "error");
        if (error instanceof ApiError && [400, 409].includes(error.status)) await loadAvailability();
    } finally {
        submit.textContent = original;
        if (selectedSlot) submit.disabled = false;
    }
}

function bookingFor(id) { return bookings.find(item => String(item.id) === String(id)); }
async function checkIn(id, button) {
    const old = button.textContent;
    button.disabled = true;
    button.textContent = "Checking in...";
    message();
    try {
        await apiRequest(`/api/v1/bookings/${id}/check-in/`, { method: "POST" });
        await refresh();
        message("Check-in completed. Your live queue information is now available.", "success");
    } catch (error) {
        if (error instanceof ApiError) {
            if (error.status === 409) await refresh();
            const opens = error.data?.check_in_opens_at;
            message(opens ? `${error.message} Check-in opens at ${fmtDateTime(opens)}.` : firstApiError(error, error.message), "error");
        } else {
            message("Smart Q could not complete check-in.", "error");
        }
    } finally {
        button.disabled = false;
        button.textContent = old;
    }
}
async function cancel(id, button) {
    const booking = bookingFor(id);
    if (!booking) return;
    if (!window.confirm(`Cancel your ${booking.service_name} appointment at ${booking.branch_name} on ${fmtDateTime(appointment(booking))}?`)) return;
    const old = button.textContent;
    button.disabled = true;
    button.textContent = "Cancelling...";
    try {
        await apiRequest(`/api/v1/bookings/${id}/cancel/`, { method: "PATCH" });
        await refresh();
        message("Appointment cancelled.", "success");
    } catch (error) {
        message(firstApiError(error, "Smart Q could not cancel this appointment."), "error");
    } finally {
        button.disabled = false;
        button.textContent = old;
    }
}
async function details(id) {
    const booking = bookingFor(id);
    const dialog = one("[data-booking-dialog]");
    if (!booking || !dialog) return;
    one("[data-dialog-loading]", dialog).hidden = false;
    one("[data-dialog-content]", dialog).hidden = true;
    one("[data-dialog-error]", dialog).hidden = true;
    dialog.showModal();
    try {
        const data = await apiRequest(`/api/v1/queues/bookings/${id}/timeline/`);
        setText("[data-dialog-service]", booking.service_name, dialog);
        setText("[data-dialog-branch]", booking.branch_name, dialog);
        setText("[data-dialog-appointment]", fmtDateTime(appointment(booking)), dialog);
        setText("[data-dialog-status]", label(booking.status), dialog);
        setText("[data-dialog-queue]", queueNumber(booking), dialog);
        const list = one("[data-dialog-timeline]", dialog);
        list.replaceChildren();
        for (const event of data.events || []) {
            const item = document.createElement("li");
            item.className = "timeline__item";
            const marker = document.createElement("span");
            marker.className = "timeline__marker";
            const content = document.createElement("div");
            content.className = "timeline__content";
            const title = document.createElement("strong");
            title.textContent = eventLabels[event.event_type] || label(event.event_type);
            const time = document.createElement("span");
            time.textContent = fmtDateTime(event.occurred_at);
            content.append(title, time);
            if (event.counter_id) {
                const small = document.createElement("small");
                small.textContent = `Counter ${event.counter_id}`;
                content.append(small);
            }
            item.append(marker, content);
            list.append(item);
        }
        if (!list.children.length) {
            const item = document.createElement("li");
            item.className = "timeline__empty";
            item.textContent = "No lifecycle events are available yet.";
            list.append(item);
        }
        one("[data-dialog-content]", dialog).hidden = false;
    } catch (error) {
        const target = one("[data-dialog-error]", dialog);
        target.textContent = firstApiError(error, "Smart Q could not load this booking history.");
        target.hidden = false;
    } finally {
        one("[data-dialog-loading]", dialog).hidden = true;
    }
}

function bindBookingWorkflow() {
    const branchSelect = one("[data-booking-branch]");
    const serviceSelect = one("[data-booking-service]");
    const dateInput = one("[data-booking-date]");

    branchSelect.addEventListener("change", async () => {
        setBookingMessage();
        serviceSelect.value = "";
        dateInput.value = "";
        dateInput.disabled = true;
        resetSlots();
        if (!branchSelect.value) {
            await loadServices("");
            setBookingStep(1);
            return;
        }
        try {
            await loadServices(branchSelect.value);
            setBookingStep(2);
        } catch (error) {
            setBookingMessage(firstApiError(error, "Smart Q could not load services for this branch."));
        }
    });

    serviceSelect.addEventListener("change", () => {
        dateInput.value = "";
        resetSlots();
        dateInput.disabled = !serviceSelect.value;
        setBookingStep(serviceSelect.value ? 3 : 2);
        const service = serviceById(serviceSelect.value);
        setText("[data-service-help]", service ? `${service.service_name} normally takes about ${service.average_service_time} minutes. Slot duration follows that backend service time.` : "Services are loaded from the selected branch.");
    });

    dateInput.addEventListener("change", loadAvailability);
    one("[data-slot-grid]").addEventListener("change", event => {
        const input = event.target.closest("[data-slot-choice]");
        if (!input) return;
        selectedSlot = input.value;
        updateReview();
    });
    one("[data-booking-form]").addEventListener("submit", submitBooking);
    one("[data-booking-reset]").addEventListener("click", () => resetBookingForm());
}

async function bootstrap() {
    if (!root) return;
    account = await getCurrentAccount();
    if (!account) {
        window.location.replace(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
        return;
    }
    if (account.role !== "customer") {
        window.location.replace(routeForRole(account.role));
        return;
    }
    setText("[data-customer-identity]", account.username);
    setText("[data-greeting]", account.first_name ? `Welcome, ${account.first_name}` : "Your Smart Q overview");
    bindBookingWorkflow();
    await Promise.all([loadBranches(), refresh()]);
    await resetBookingForm();
}

document.addEventListener("click", event => {
    const button = event.target.closest("[data-booking-action],[data-next-action]");
    if (!button) return;
    const id = button.dataset.bookingId;
    const action = button.dataset.bookingAction || button.dataset.nextAction;
    if (action === "check-in") checkIn(id, button);
    if (action === "cancel") cancel(id, button);
    if (action === "details") details(id);
    if (action === "reschedule") beginReschedule(bookingFor(id));
});
one("[data-dialog-close]")?.addEventListener("click", () => one("[data-booking-dialog]").close());
one("[data-logout]")?.addEventListener("click", async () => {
    try { await logoutAccount(); } finally { window.location.replace("/login/"); }
});
bootstrap().catch(error => showError(firstApiError(error, "Smart Q could not restore this customer session. Sign in again.")));
