import { ApiError, apiRequest, fieldErrors } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-customer-recovery]");
const one = (selector, scope = root) => scope?.querySelector(selector) || null;

const state = {
    account: null,
    recommendations: [],
    bookings: new Map(),
    refreshSequence: 0,
};

function titleCase(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function errorText(error, fallback = "The request could not be completed.") {
    if (!(error instanceof ApiError)) return fallback;
    const fields = fieldErrors(error.data);
    if (fields.length) return fields.map(({ field, message }) => `${titleCase(field)}: ${message}`).join(" ");
    return error.message || fallback;
}

function setMessage(text = "", kind = "error") {
    const node = one("[data-recovery-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setBusy(button, label = "Applying...") {
    if (!button) return () => {};
    const original = button.textContent;
    button.disabled = true;
    button.textContent = label;
    return () => {
        button.disabled = false;
        button.textContent = original;
    };
}

function appointmentBlock(label, date, time) {
    const block = document.createElement("div");
    block.className = "recovery-card__appointment";
    const small = document.createElement("span");
    small.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = `${formatDate(date)} · ${formatTime(time)}`;
    block.append(small, strong);
    return block;
}

function statusBadge(status) {
    const badge = document.createElement("span");
    badge.className = "recovery-status";
    badge.dataset.status = status || "pending";
    badge.textContent = titleCase(status || "pending");
    return badge;
}

function bookingLabel(recommendation) {
    const booking = state.bookings.get(Number(recommendation.booking_id));
    if (!booking) return { title: `Booking #${recommendation.booking_id}`, subtitle: "Affected appointment" };
    return {
        title: booking.service_name || `Booking #${booking.id}`,
        subtitle: booking.branch_name || "Smart Q branch",
    };
}

function createOption(recommendation, option) {
    const row = document.createElement("div");
    row.className = "recovery-option";
    row.dataset.selected = option.is_selected ? "true" : "false";

    const content = document.createElement("div");
    const main = document.createElement("div");
    main.className = "recovery-option__main";
    const time = document.createElement("strong");
    time.textContent = `${formatDate(option.option_date)} · ${formatTime(option.option_time)}`;
    main.append(time);

    if (option.is_recommended) {
        const recommended = document.createElement("span");
        recommended.className = "recovery-option__badge";
        recommended.textContent = "Recommended";
        main.append(recommended);
    }
    if (option.is_selected) {
        const selected = document.createElement("span");
        selected.className = "recovery-option__badge";
        selected.textContent = "Selected";
        main.append(selected);
    }

    const meta = document.createElement("div");
    meta.className = "recovery-option__meta";
    const available = document.createElement("span");
    available.textContent = `${option.available_count ?? 0} available`;
    const capacity = document.createElement("span");
    capacity.textContent = `${option.booked_count ?? 0}/${option.capacity ?? 0} booked`;
    meta.append(available, capacity);
    content.append(main, meta);
    row.append(content);

    const actionable = new Set(["pending", "approved"]).has(recommendation.status);
    if (actionable && !option.is_selected) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn--primary btn--sm";
        button.textContent = option.available_count > 0 ? "Choose this slot" : "Currently full";
        button.disabled = option.available_count <= 0;
        button.dataset.recoveryOption = String(option.id);
        button.dataset.recommendationId = String(recommendation.id);
        row.append(button);
    }

    return row;
}

function renderRecommendation(recommendation) {
    const card = document.createElement("article");
    card.className = "panel recovery-card";
    card.dataset.recommendationId = String(recommendation.id);

    const heading = document.createElement("div");
    heading.className = "recovery-card__heading";
    const copy = document.createElement("div");
    const kicker = document.createElement("p");
    kicker.className = "kicker";
    kicker.textContent = `Recovery recommendation #${recommendation.id}`;
    const labels = bookingLabel(recommendation);
    const title = document.createElement("h3");
    title.textContent = labels.title;
    const subtitle = document.createElement("p");
    subtitle.textContent = labels.subtitle;
    copy.append(kicker, title, subtitle);
    heading.append(copy, statusBadge(recommendation.status));
    card.append(heading);

    const route = document.createElement("div");
    route.className = "recovery-card__route";
    route.append(appointmentBlock("Original appointment", recommendation.old_booking_date, recommendation.old_booking_time));
    const arrow = document.createElement("span");
    arrow.className = "recovery-card__arrow";
    arrow.textContent = "→";
    route.append(arrow);
    route.append(appointmentBlock("Current recommendation", recommendation.suggested_booking_date, recommendation.suggested_booking_time));
    card.append(route);

    const reason = document.createElement("div");
    reason.className = "recovery-reason";
    const reasonLabel = document.createElement("span");
    reasonLabel.textContent = "Why Smart Q offered recovery";
    const reasonText = document.createElement("p");
    reasonText.textContent = recommendation.reason || "Your visit was at risk because service capacity was lost during a disruption.";
    reason.append(reasonLabel, reasonText);
    card.append(reason);

    const options = document.createElement("div");
    options.className = "recovery-options";
    const optionTitle = document.createElement("span");
    optionTitle.className = "recovery-options__title";
    optionTitle.textContent = recommendation.status === "applied" ? "Recovery result" : "Available replacement options";
    options.append(optionTitle);

    const optionList = Array.isArray(recommendation.options) ? recommendation.options : [];
    if (optionList.length) {
        for (const option of optionList) options.append(createOption(recommendation, option));
    } else {
        const empty = document.createElement("p");
        empty.className = "day49-footnote";
        empty.textContent = "No replacement slots are currently attached to this recommendation.";
        options.append(empty);
    }
    card.append(options);

    const note = document.createElement("p");
    note.className = "recovery-priority-note";
    if (recommendation.status === "applied") {
        note.textContent = "Recovery applied. Your booking now uses the selected replacement slot, your queue ticket returns to SCHEDULED, and a fresh check-in is required when the new check-in window opens.";
    } else if (recommendation.priority_on_reschedule) {
        note.textContent = "If you accept a replacement slot, Smart Q applies Priority to the replacement queue ticket. The backend revalidates capacity at the moment you choose.";
    } else {
        note.textContent = "Smart Q will revalidate the replacement slot at the moment you choose it.";
    }
    card.append(note);

    return card;
}

function render() {
    const list = one("[data-recovery-list]");
    const empty = one("[data-recovery-empty]");
    list.replaceChildren();

    const pending = state.recommendations.filter((item) => new Set(["pending", "approved"]).has(item.status)).length;
    const applied = state.recommendations.filter((item) => item.status === "applied").length;
    one("[data-recovery-pending]").textContent = pending;
    one("[data-recovery-applied]").textContent = applied;
    one("[data-recovery-total]").textContent = state.recommendations.length;

    empty.hidden = state.recommendations.length > 0;
    for (const recommendation of state.recommendations) list.append(renderRecommendation(recommendation));
}

async function refresh({ firstLoad = false } = {}) {
    const sequence = ++state.refreshSequence;
    const loading = one("[data-recovery-loading]");
    const content = one("[data-recovery-content]");
    const refreshButton = one("[data-recovery-refresh]");
    refreshButton.disabled = true;
    if (firstLoad) {
        loading.hidden = false;
        content.hidden = true;
    }
    setMessage("");

    try {
        const [recommendations, bookings] = await Promise.all([
            apiRequest("/api/v1/rescheduling/recommendations/my/"),
            apiRequest("/api/v1/bookings/my/"),
        ]);
        if (sequence !== state.refreshSequence) return;
        state.recommendations = Array.isArray(recommendations) ? recommendations : [];
        state.bookings = new Map((Array.isArray(bookings) ? bookings : []).map((booking) => [Number(booking.id), booking]));
        render();
        loading.hidden = true;
        content.hidden = false;
    } catch (error) {
        if (sequence !== state.refreshSequence) return;
        loading.hidden = true;
        setMessage(errorText(error, "Smart Q could not load your recovery options."));
    } finally {
        if (sequence === state.refreshSequence) refreshButton.disabled = false;
    }
}

async function chooseOption(optionId, button) {
    const restore = setBusy(button);
    setMessage("");
    try {
        await apiRequest(`/api/v1/rescheduling/options/${optionId}/select/`, { method: "POST" });
        setMessage("Replacement appointment applied. Smart Q revalidated the slot and refreshed your booking.", "success");
        await refresh();
    } catch (error) {
        setMessage(errorText(error, "This replacement option could not be applied. Refresh and choose another available option."));
        await refresh();
    } finally {
        restore();
    }
}

function bindEvents() {
    one("[data-recovery-refresh]")?.addEventListener("click", () => refresh());
    root?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-recovery-option]");
        if (button) chooseOption(Number(button.dataset.recoveryOption), button);
    });
}

async function bootstrap() {
    if (!root) return;
    bindEvents();
    try {
        state.account = await getCurrentAccount();
        if (!state.account) {
            window.location.replace(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
            return;
        }
        if (state.account.role !== "customer") {
            window.location.replace(routeForRole(state.account.role));
            return;
        }
        await refresh({ firstLoad: true });
    } catch (error) {
        one("[data-recovery-loading]").hidden = true;
        setMessage(errorText(error, "Smart Q could not open service recovery."));
    }
}

bootstrap();
