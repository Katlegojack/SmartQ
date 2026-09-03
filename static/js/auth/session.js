import { ApiError, apiRequest, clearCsrfToken } from "../api/client.js";

export const ROLE_ROUTES = Object.freeze({
    customer: "/app/customer/",
    receptionist: "/app/reception/",
    counter_staff: "/app/counter/",
    branch_manager: "/app/manager/",
    system_admin: "/app/admin/",
});

export const ROLE_LABELS = Object.freeze({
    customer: "Customer",
    receptionist: "Receptionist",
    counter_staff: "Counter Staff",
    branch_manager: "Branch Manager",
    system_admin: "System Administrator",
});

let currentAccountPromise = null;

export function routeForRole(role) {
    return ROLE_ROUTES[role] || "/";
}

export function roleLabel(role) {
    return ROLE_LABELS[role] || "Smart Q user";
}

export function clearCurrentAccountCache() {
    currentAccountPromise = null;
}

export function getCurrentAccount({ refresh = false } = {}) {
    if (refresh || !currentAccountPromise) {
        currentAccountPromise = apiRequest("/api/v1/accounts/me/").catch(error => {
            if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
                return null;
            }
            currentAccountPromise = null;
            throw error;
        });
    }
    return currentAccountPromise;
}

export async function loginAccount(username, password) {
    const data = await apiRequest("/api/v1/accounts/login/", {
        method: "POST",
        body: { username, password },
    });
    clearCsrfToken();
    currentAccountPromise = Promise.resolve(data.user);
    return data.user;
}

export async function registerCustomer(payload) {
    return apiRequest("/api/v1/accounts/register/", {
        method: "POST",
        body: payload,
    });
}

export async function logoutAccount() {
    try {
        await apiRequest("/api/v1/accounts/logout/", { method: "POST" });
    } finally {
        clearCurrentAccountCache();
        clearCsrfToken();
    }
}

export async function changePassword(currentPassword, newPassword) {
    return apiRequest("/api/v1/accounts/change-password/", {
        method: "POST",
        body: {
            current_password: currentPassword,
            new_password: newPassword,
        },
    });
}

export function redirectToWorkspace(user, { replace = false } = {}) {
    const path = routeForRole(user?.role);
    if (replace) {
        window.location.replace(path);
        return;
    }
    window.location.assign(path);
}
