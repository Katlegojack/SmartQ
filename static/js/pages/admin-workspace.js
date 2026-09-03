import { ApiError, apiRequest, fieldErrors } from "../api/client.js";
import { getCurrentAccount, routeForRole } from "../auth/session.js";

const root = document.querySelector("[data-admin-workspace]");
const one = (selector, scope = root) => scope?.querySelector(selector) || null;

const state = {
    account: null,
    staff: [],
    branches: [],
    services: [],
    mappings: [],
    staffEditId: null,
    branchEditId: null,
    serviceEditId: null,
    mappingEditId: null,
    refreshSequence: 0,
};

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

function formatClock(value) {
    return value ? String(value).slice(0, 5) : "—";
}

function errorText(error, fallback = "The request could not be completed.") {
    if (!(error instanceof ApiError)) return fallback;
    const fields = fieldErrors(error.data);
    if (fields.length) return fields.map(({ field, message }) => `${titleCase(field)}: ${message}`).join(" ");
    return error.message || fallback;
}

function setMessage(text = "", kind = "error") {
    const node = one("[data-admin-message]");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setFormMessage(formName, text = "", kind = "error") {
    const node = one(`[data-${formName}-message]`);
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
    node.hidden = !text;
}

function setBusy(button, busyText = "Saving...") {
    if (!button) return () => {};
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    return () => {
        button.disabled = false;
        button.textContent = original;
    };
}

function statusBadge(active) {
    const badge = document.createElement("span");
    badge.className = `admin-status admin-status--${active ? "active" : "inactive"}`;
    badge.textContent = active ? "Active" : "Inactive";
    return badge;
}

function primaryCell(primary, secondary = "") {
    const cell = document.createElement("td");
    const first = document.createElement("span");
    first.className = "table-primary";
    first.textContent = primary || "—";
    cell.append(first);
    if (secondary) {
        const second = document.createElement("span");
        second.className = "table-secondary";
        second.textContent = secondary;
        cell.append(second);
    }
    return cell;
}

function textCell(value) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "—";
    return cell;
}

function actionButton(label, datasetName, id, className = "btn btn--secondary btn--sm") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.dataset[datasetName] = String(id);
    return button;
}

function actionCell(buttons) {
    const cell = document.createElement("td");
    const wrapper = document.createElement("div");
    wrapper.className = "table-actions";
    buttons.forEach((button) => wrapper.append(button));
    cell.append(wrapper);
    return cell;
}

function renderMetrics() {
    const activeStaff = state.staff.filter((item) => item.is_active).length;
    const activeBranches = state.branches.filter((item) => item.is_active).length;
    const activeServices = state.services.filter((item) => item.is_active).length;
    const activeMappings = state.mappings.filter((item) => item.is_active).length;

    one("[data-metric-staff]").textContent = activeStaff;
    one("[data-metric-staff-total]").textContent = `${state.staff.length} total staff accounts`;
    one("[data-metric-branches]").textContent = activeBranches;
    one("[data-metric-branches-total]").textContent = `${state.branches.length} configured branches`;
    one("[data-metric-services]").textContent = activeServices;
    one("[data-metric-services-total]").textContent = `${state.services.length} catalogue services`;
    one("[data-metric-mappings]").textContent = activeMappings;
    one("[data-metric-mappings-total]").textContent = `${state.mappings.length} branch/service mappings`;
}

function renderStaff() {
    const body = one("[data-staff-body]");
    body.replaceChildren();
    for (const staff of state.staff) {
        const row = document.createElement("tr");
        const name = [staff.first_name, staff.last_name].filter(Boolean).join(" ") || staff.username;
        row.append(primaryCell(name, `@${staff.username}${staff.email ? ` · ${staff.email}` : ""}`));
        row.append(textCell(titleCase(staff.role)));
        row.append(textCell(staff.branch_name || "Global"));
        const status = document.createElement("td");
        status.append(statusBadge(staff.is_active));
        row.append(status);

        const buttons = [actionButton("Edit", "editStaff", staff.id)];
        if (staff.id === state.account?.id && staff.is_active) {
            const current = actionButton("Current admin", "noop", staff.id);
            current.disabled = true;
            buttons.push(current);
        } else {
            buttons.push(
                actionButton(
                    staff.is_active ? "Deactivate" : "Activate",
                    "activateStaff",
                    staff.id,
                    staff.is_active ? "btn btn--danger-soft btn--sm" : "btn btn--success-soft btn--sm",
                ),
            );
        }
        row.append(actionCell(buttons));
        body.append(row);
    }
    if (!state.staff.length) {
        const row = document.createElement("tr");
        const cell = textCell("No operational staff accounts found.");
        cell.colSpan = 5;
        row.append(cell);
        body.append(row);
    }
}

function renderBranches() {
    const body = one("[data-branch-body]");
    body.replaceChildren();
    for (const branch of state.branches) {
        const row = document.createElement("tr");
        row.append(primaryCell(branch.name, branch.branch_code));
        row.append(textCell(branch.city));
        row.append(textCell(`${formatClock(branch.opening_time)}–${formatClock(branch.closing_time)}`));
        const status = document.createElement("td");
        status.append(statusBadge(branch.is_active));
        row.append(status);
        row.append(actionCell([actionButton("Edit", "editBranch", branch.id)]));
        body.append(row);
    }
}

function renderServices() {
    const body = one("[data-service-body]");
    body.replaceChildren();
    for (const service of state.services) {
        const row = document.createElement("tr");
        row.append(primaryCell(service.name, service.service_code));
        row.append(textCell(`${service.average_service_time} min`));
        const status = document.createElement("td");
        status.append(statusBadge(service.is_active));
        row.append(status);
        row.append(actionCell([actionButton("Edit", "editService", service.id)]));
        body.append(row);
    }
}

function renderMappings() {
    const body = one("[data-mapping-body]");
    body.replaceChildren();
    for (const mapping of state.mappings) {
        const row = document.createElement("tr");
        row.append(primaryCell(mapping.branch_name, `Branch #${mapping.branch}`));
        row.append(primaryCell(mapping.service_name, `Service #${mapping.service}`));
        row.append(textCell(`${mapping.max_bookings_per_slot} / slot`));
        const status = document.createElement("td");
        status.append(statusBadge(mapping.is_active));
        row.append(status);
        row.append(actionCell([actionButton("Edit", "editMapping", mapping.id)]));
        body.append(row);
    }
}

function fillSelect(select, items, placeholder, valueKey = "id", labelFn = (item) => item.name, activeOnly = true) {
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = placeholder;
    select.append(blank);
    for (const item of items) {
        if (activeOnly && !item.is_active) continue;
        const option = document.createElement("option");
        option.value = String(item[valueKey]);
        option.textContent = labelFn(item);
        select.append(option);
    }
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function refreshSelects() {
    fillSelect(one("[data-staff-branch]"), state.branches, "No branch", "id", (item) => `${item.name} (${item.branch_code})`);
    fillSelect(one("[data-mapping-branch]"), state.branches, "Choose active branch", "id", (item) => `${item.name} (${item.branch_code})`);
    fillSelect(one("[data-mapping-service]"), state.services, "Choose active service", "id", (item) => `${item.name} (${item.service_code})`);
    fillSelect(one("[data-inspection-branch]"), state.branches, "Choose active branch", "id", (item) => `${item.name} (${item.branch_code})`);
    syncStaffRoleBranch();
}

function renderAll() {
    renderMetrics();
    renderStaff();
    renderBranches();
    renderServices();
    renderMappings();
    refreshSelects();
}

async function refreshCatalogues({ silent = false } = {}) {
    const sequence = ++state.refreshSequence;
    const loading = one("[data-admin-loading]");
    const content = one("[data-admin-content]");
    const refresh = one("[data-refresh-admin]");
    if (!silent) {
        loading.hidden = false;
        content.hidden = true;
    }
    refresh.disabled = true;
    setMessage("");

    try {
        const [staff, branches, services, mappings] = await Promise.all([
            apiRequest("/api/v1/accounts/admin/staff/"),
            apiRequest("/api/v1/branches/admin/"),
            apiRequest("/api/v1/services/admin/"),
            apiRequest("/api/v1/services/admin/branch-services/"),
        ]);
        if (sequence !== state.refreshSequence) return;
        state.staff = staff || [];
        state.branches = branches || [];
        state.services = services || [];
        state.mappings = mappings || [];
        renderAll();
        loading.hidden = true;
        content.hidden = false;
    } catch (error) {
        if (sequence !== state.refreshSequence) return;
        loading.hidden = true;
        setMessage(errorText(error, "Smart Q could not load the administration catalogues."));
    } finally {
        if (sequence === state.refreshSequence) refresh.disabled = false;
    }
}

function syncStaffRoleBranch() {
    const role = one("[data-staff-role]");
    const branch = one("[data-staff-branch]");
    if (!role || !branch) return;
    const isAdmin = role.value === "system_admin";
    if (isAdmin) branch.value = "";
    branch.disabled = isAdmin;
    branch.required = !isAdmin;
}

function resetStaffForm() {
    const form = one("[data-staff-form]");
    state.staffEditId = null;
    form.reset();
    form.elements.username.readOnly = false;
    for (const node of root.querySelectorAll("[data-staff-create-only]")) node.hidden = false;
    form.elements.date_of_birth.disabled = false;
    form.elements.gender.disabled = false;
    form.elements.disability_status.disabled = false;
    form.elements.password.disabled = false;
    one("[data-staff-form-mode]").textContent = "Create";
    one("[data-staff-form-title]").textContent = "New staff account";
    one("[data-staff-submit]").textContent = "Create staff";
    setFormMessage("staff", "");
    syncStaffRoleBranch();
}

function editStaff(id) {
    const staff = state.staff.find((item) => item.id === Number(id));
    if (!staff) return;
    resetStaffForm();
    state.staffEditId = staff.id;
    const form = one("[data-staff-form]");
    form.elements.username.value = staff.username;
    form.elements.username.readOnly = true;
    form.elements.first_name.value = staff.first_name || "";
    form.elements.last_name.value = staff.last_name || "";
    form.elements.email.value = staff.email || "";
    form.elements.role.value = staff.role;
    form.elements.branch.value = staff.branch_id ? String(staff.branch_id) : "";
    for (const node of root.querySelectorAll("[data-staff-create-only]")) node.hidden = true;
    form.elements.date_of_birth.disabled = true;
    form.elements.gender.disabled = true;
    form.elements.disability_status.disabled = true;
    form.elements.password.disabled = true;
    one("[data-staff-form-mode]").textContent = "Edit";
    one("[data-staff-form-title]").textContent = `Edit ${staff.username}`;
    one("[data-staff-submit]").textContent = "Save staff";
    syncStaffRoleBranch();
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitStaff(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = one("[data-staff-submit]");
    const restore = setBusy(submit);
    setFormMessage("staff", "");

    const editingId = state.staffEditId;
    const branchValue = form.elements.branch.value;
    const payload = {
        first_name: form.elements.first_name.value.trim(),
        last_name: form.elements.last_name.value.trim(),
        email: form.elements.email.value.trim(),
        role: form.elements.role.value,
        branch: branchValue ? Number(branchValue) : null,
    };
    if (!editingId) {
        Object.assign(payload, {
            username: form.elements.username.value.trim(),
            password: form.elements.password.value,
            date_of_birth: form.elements.date_of_birth.value,
            gender: form.elements.gender.value,
            disability_status: form.elements.disability_status.checked,
        });
    }

    try {
        await apiRequest(
            editingId ? `/api/v1/accounts/admin/staff/${editingId}/` : "/api/v1/accounts/admin/staff/",
            { method: editingId ? "PATCH" : "POST", body: payload },
        );

        if (editingId && editingId === state.account?.id) {
            const refreshedAccount = await getCurrentAccount({ refresh: true });
            state.account = refreshedAccount;
            if (!refreshedAccount || refreshedAccount.role !== "system_admin") {
                window.location.replace(routeForRole(refreshedAccount?.role));
                return;
            }
        }

        setMessage(editingId ? "Staff account updated." : "Staff account created.", "success");
        resetStaffForm();
        await refreshCatalogues({ silent: true });
    } catch (error) {
        setFormMessage("staff", errorText(error, "Smart Q could not save this staff account."));
    } finally {
        restore();
    }
}

async function toggleStaffActivation(id, button) {
    const staff = state.staff.find((item) => item.id === Number(id));
    if (!staff) return;
    const nextState = !staff.is_active;
    const restore = setBusy(button, nextState ? "Activating..." : "Deactivating...");
    setMessage("");
    try {
        await apiRequest(`/api/v1/accounts/admin/staff/${staff.id}/activation/`, {
            method: "PATCH",
            body: { is_active: nextState },
        });
        setMessage(`${staff.username} ${nextState ? "activated" : "deactivated"}.`, "success");
        await refreshCatalogues({ silent: true });
    } catch (error) {
        setMessage(errorText(error, "Smart Q could not change this account's activation state."));
    } finally {
        restore();
    }
}

function resetBranchForm() {
    const form = one("[data-branch-form]");
    state.branchEditId = null;
    form.reset();
    form.elements.is_active.checked = true;
    one("[data-branch-form-mode]").textContent = "Create";
    one("[data-branch-form-title]").textContent = "New branch";
    setFormMessage("branch", "");
}

function editBranch(id) {
    const branch = state.branches.find((item) => item.id === Number(id));
    if (!branch) return;
    resetBranchForm();
    state.branchEditId = branch.id;
    const form = one("[data-branch-form]");
    for (const field of ["branch_code", "name", "address", "city"]) form.elements[field].value = branch[field] || "";
    form.elements.opening_time.value = formatClock(branch.opening_time);
    form.elements.closing_time.value = formatClock(branch.closing_time);
    form.elements.is_active.checked = Boolean(branch.is_active);
    one("[data-branch-form-mode]").textContent = "Edit";
    one("[data-branch-form-title]").textContent = `Edit ${branch.name}`;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitBranch(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = one("[data-branch-submit]");
    const restore = setBusy(submit);
    setFormMessage("branch", "");
    const payload = {
        branch_code: form.elements.branch_code.value.trim(),
        name: form.elements.name.value.trim(),
        address: form.elements.address.value.trim(),
        city: form.elements.city.value.trim(),
        opening_time: form.elements.opening_time.value,
        closing_time: form.elements.closing_time.value,
        is_active: form.elements.is_active.checked,
    };
    try {
        await apiRequest(
            state.branchEditId ? `/api/v1/branches/admin/${state.branchEditId}/` : "/api/v1/branches/admin/",
            { method: state.branchEditId ? "PATCH" : "POST", body: payload },
        );
        setMessage(state.branchEditId ? "Branch updated." : "Branch created.", "success");
        resetBranchForm();
        await refreshCatalogues({ silent: true });
    } catch (error) {
        setFormMessage("branch", errorText(error, "Smart Q could not save this branch."));
    } finally {
        restore();
    }
}

function resetServiceForm() {
    const form = one("[data-service-form]");
    state.serviceEditId = null;
    form.reset();
    form.elements.is_active.checked = true;
    one("[data-service-form-mode]").textContent = "Create";
    one("[data-service-form-title]").textContent = "New service";
    setFormMessage("service", "");
}

function editService(id) {
    const service = state.services.find((item) => item.id === Number(id));
    if (!service) return;
    resetServiceForm();
    state.serviceEditId = service.id;
    const form = one("[data-service-form]");
    form.elements.service_code.value = service.service_code || "";
    form.elements.name.value = service.name || "";
    form.elements.description.value = service.description || "";
    form.elements.average_service_time.value = service.average_service_time;
    form.elements.is_active.checked = Boolean(service.is_active);
    one("[data-service-form-mode]").textContent = "Edit";
    one("[data-service-form-title]").textContent = `Edit ${service.name}`;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitService(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = one("[data-service-submit]");
    const restore = setBusy(submit);
    setFormMessage("service", "");
    const payload = {
        service_code: form.elements.service_code.value.trim(),
        name: form.elements.name.value.trim(),
        description: form.elements.description.value.trim(),
        average_service_time: Number(form.elements.average_service_time.value),
        is_active: form.elements.is_active.checked,
    };
    try {
        await apiRequest(
            state.serviceEditId ? `/api/v1/services/admin/${state.serviceEditId}/` : "/api/v1/services/admin/",
            { method: state.serviceEditId ? "PATCH" : "POST", body: payload },
        );
        setMessage(state.serviceEditId ? "Service updated." : "Service created.", "success");
        resetServiceForm();
        await refreshCatalogues({ silent: true });
    } catch (error) {
        setFormMessage("service", errorText(error, "Smart Q could not save this service."));
    } finally {
        restore();
    }
}

function resetMappingForm() {
    const form = one("[data-mapping-form]");
    state.mappingEditId = null;
    form.reset();
    form.elements.is_active.checked = true;
    form.elements.branch.disabled = false;
    form.elements.service.disabled = false;
    one("[data-mapping-form-mode]").textContent = "Create";
    one("[data-mapping-form-title]").textContent = "New branch/service mapping";
    setFormMessage("mapping", "");
}

function editMapping(id) {
    const mapping = state.mappings.find((item) => item.id === Number(id));
    if (!mapping) return;
    resetMappingForm();
    state.mappingEditId = mapping.id;
    const form = one("[data-mapping-form]");
    // Inactive branch/service options may no longer be in active-only selects. Add their current values when needed.
    const branch = state.branches.find((item) => item.id === mapping.branch);
    const service = state.services.find((item) => item.id === mapping.service);
    if (branch && ![...form.elements.branch.options].some((o) => Number(o.value) === branch.id)) {
        const option = document.createElement("option");
        option.value = String(branch.id);
        option.textContent = `${branch.name} (${branch.branch_code}) · inactive`;
        form.elements.branch.append(option);
    }
    if (service && ![...form.elements.service.options].some((o) => Number(o.value) === service.id)) {
        const option = document.createElement("option");
        option.value = String(service.id);
        option.textContent = `${service.name} (${service.service_code}) · inactive`;
        form.elements.service.append(option);
    }
    form.elements.branch.value = String(mapping.branch);
    form.elements.service.value = String(mapping.service);
    form.elements.branch.disabled = true;
    form.elements.service.disabled = true;
    form.elements.max_bookings_per_slot.value = mapping.max_bookings_per_slot;
    form.elements.is_active.checked = Boolean(mapping.is_active);
    one("[data-mapping-form-mode]").textContent = "Edit";
    one("[data-mapping-form-title]").textContent = `${mapping.branch_name} · ${mapping.service_name}`;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitMapping(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = one("[data-mapping-submit]");
    const restore = setBusy(submit);
    setFormMessage("mapping", "");
    const payload = {
        max_bookings_per_slot: Number(form.elements.max_bookings_per_slot.value),
        is_active: form.elements.is_active.checked,
    };
    if (!state.mappingEditId) {
        payload.branch = Number(form.elements.branch.value);
        payload.service = Number(form.elements.service.value);
    }
    try {
        await apiRequest(
            state.mappingEditId ? `/api/v1/services/admin/branch-services/${state.mappingEditId}/` : "/api/v1/services/admin/branch-services/",
            { method: state.mappingEditId ? "PATCH" : "POST", body: payload },
        );
        setMessage(state.mappingEditId ? "Branch capacity updated." : "Branch/service mapping created.", "success");
        resetMappingForm();
        await refreshCatalogues({ silent: true });
    } catch (error) {
        setFormMessage("mapping", errorText(error, "Smart Q could not save this branch/service mapping."));
    } finally {
        restore();
    }
}

async function inspectBranch(button) {
    const branchId = one("[data-inspection-branch]").value;
    const date = one("[data-inspection-date]").value || localDateValue();
    if (!branchId) {
        setMessage("Choose an active branch before loading operational data.");
        return;
    }
    const restore = setBusy(button, "Loading...");
    setMessage("");
    try {
        const dashboard = await apiRequest(`/api/v1/dashboard/branches/${branchId}/?date=${encodeURIComponent(date)}`);
        const totals = dashboard.lifecycle_totals || {};
        const counters = dashboard.counters || {};
        one("[data-inspection-empty]").hidden = true;
        one("[data-inspection-result]").hidden = false;
        one("[data-inspect-total]").textContent = dashboard.customers?.total_customers ?? 0;
        one("[data-inspect-date]").textContent = dashboard.date || date;
        one("[data-inspect-waiting]").textContent = totals.waiting ?? 0;
        one("[data-inspect-serving]").textContent = totals.serving ?? 0;
        one("[data-inspect-counters]").textContent = counters.summary?.total ?? 0;
        one("[data-inspect-counter-note]").textContent = "Live current state";
        one("[data-inspect-branch-name]").textContent = dashboard.branch?.name || "Branch";
        one("[data-inspect-city]").textContent = dashboard.branch?.city || "—";
        one("[data-inspect-open]").textContent = `${counters.summary?.open ?? 0} open`;
        one("[data-inspect-busy]").textContent = `${counters.summary?.busy ?? 0} busy`;
        one("[data-inspect-unstaffed]").textContent = `${counters.summary?.unstaffed ?? 0} unstaffed`;
    } catch (error) {
        setMessage(errorText(error, "Smart Q could not inspect this branch."));
    } finally {
        restore();
    }
}

function bindEvents() {
    one("[data-refresh-admin]")?.addEventListener("click", () => refreshCatalogues());
    one("[data-staff-role]")?.addEventListener("change", syncStaffRoleBranch);
    one("[data-staff-form]")?.addEventListener("submit", submitStaff);
    one("[data-branch-form]")?.addEventListener("submit", submitBranch);
    one("[data-service-form]")?.addEventListener("submit", submitService);
    one("[data-mapping-form]")?.addEventListener("submit", submitMapping);
    one("[data-inspect-branch]")?.addEventListener("click", (event) => inspectBranch(event.currentTarget));

    for (const button of root.querySelectorAll("[data-reset-staff-form]")) button.addEventListener("click", resetStaffForm);
    for (const button of root.querySelectorAll("[data-reset-branch-form]")) button.addEventListener("click", resetBranchForm);
    for (const button of root.querySelectorAll("[data-reset-service-form]")) button.addEventListener("click", resetServiceForm);
    for (const button of root.querySelectorAll("[data-reset-mapping-form]")) button.addEventListener("click", resetMappingForm);

    one("[data-staff-body]")?.addEventListener("click", async (event) => {
        const edit = event.target.closest("[data-edit-staff]");
        if (edit) return editStaff(edit.dataset.editStaff);
        const activation = event.target.closest("[data-activate-staff]");
        if (activation) await toggleStaffActivation(activation.dataset.activateStaff, activation);
    });
    one("[data-branch-body]")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-edit-branch]");
        if (button) editBranch(button.dataset.editBranch);
    });
    one("[data-service-body]")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-edit-service]");
        if (button) editService(button.dataset.editService);
    });
    one("[data-mapping-body]")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-edit-mapping]");
        if (button) editMapping(button.dataset.editMapping);
    });
}

async function bootstrap() {
    if (!root) return;
    one("[data-inspection-date]").value = localDateValue();
    bindEvents();
    resetStaffForm();
    resetBranchForm();
    resetServiceForm();
    resetMappingForm();

    try {
        const account = await getCurrentAccount();
        if (!account) {
            const next = encodeURIComponent(window.location.pathname);
            window.location.replace(`/login/?next=${next}`);
            return;
        }
        if (account.role !== "system_admin") {
            window.location.replace(routeForRole(account.role));
            return;
        }
        state.account = account;
        await refreshCatalogues();
    } catch (error) {
        one("[data-admin-loading]").hidden = true;
        setMessage(errorText(error, "Smart Q could not initialise the System Admin workspace."));
    }
}

bootstrap();