import { ApiError } from "../api/client.js";
import {
    changePassword,
    getCurrentAccount,
    logoutAccount,
    roleLabel,
    routeForRole,
} from "../auth/session.js";

const shell = document.querySelector("[data-app-shell]");
const expectedRole = shell?.dataset.expectedRole || "";
const customerDashboardOwnsLogout = shell?.matches("[data-customer-dashboard]") || false;
const logoutButton = customerDashboardOwnsLogout ? null : shell?.querySelector("[data-logout]") || null;
const securityForm = shell?.querySelector("[data-security-form]") || null;
const securityMessage = shell?.querySelector("[data-security-message]") || null;
let sessionRedirecting = false;

function setText(selector, value) {
    const node = shell?.querySelector(selector);
    if (node) node.textContent = value || "—";
}

function renderAccount(user) {
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");
    setText("[data-user-name]", fullName || user.username);
    setText("[data-user-username]", user.username);
    setText("[data-user-role]", roleLabel(user.role));
    setText("[data-user-branch]", user.branch_name || "System-wide");
    setText("[data-shell-role]", roleLabel(user.role));
    setText("[data-shell-branch]", user.branch_name || "Smart Q");
}

function insertBeforeDivider(nav, link) {
    const divider = nav?.querySelector(".side-nav__divider");
    if (divider) nav.insertBefore(link, divider);
    else nav?.append(link);
}

function ensureDay49Navigation(role) {
    if (window.location.pathname === "/app/history/") return;
    const nav = shell?.querySelector(".side-nav");
    if (!nav || nav.querySelector("[data-day49-nav]")) return;
    if (!new Set(["branch_manager", "system_admin"]).has(role)) return;

    const link = document.createElement("a");
    link.className = "side-nav__item";
    link.href = "/app/history/";
    link.dataset.day49Nav = "history";
    link.textContent = role === "branch_manager" ? "History & disruptions" : "History & reporting";
    insertBeforeDivider(nav, link);
}

function ensureCustomerRecoveryNavigation() {
    const customerRoot = document.querySelector("[data-customer-dashboard]");
    const nav = customerRoot?.querySelector(".side-nav");
    if (!nav || nav.querySelector("[data-day49-recovery-nav]")) return;

    const link = document.createElement("a");
    link.className = "side-nav__item";
    link.href = "/app/recovery/";
    link.dataset.day49RecoveryNav = "recovery";
    link.textContent = "Service recovery";
    insertBeforeDivider(nav, link);
}

function setSecurityMessage(text, kind = "error") {
    if (!securityMessage) return;
    securityMessage.textContent = text;
    securityMessage.dataset.kind = kind;
    securityMessage.hidden = !text;
}

function redirectExpiredSession() {
    if (!shell || sessionRedirecting) return;
    sessionRedirecting = true;
    const next = encodeURIComponent(window.location.pathname);
    window.location.replace(`/login/?next=${next}`);
}

window.addEventListener("smartq:session-expired", redirectExpiredSession);

async function bootstrapShell() {
    ensureCustomerRecoveryNavigation();
    if (!shell) return;

    try {
        const user = await getCurrentAccount();
        if (!user) {
            redirectExpiredSession();
            return;
        }

        const correctRoute = routeForRole(user.role);
        if (expectedRole && user.role !== expectedRole) {
            window.location.replace(correctRoute);
            return;
        }
        if (!expectedRole && window.location.pathname === "/app/") {
            window.location.replace(correctRoute);
            return;
        }

        renderAccount(user);
        ensureDay49Navigation(user.role);
        shell.dataset.ready = "true";
    } catch (error) {
        const main = shell.querySelector("[data-shell-error]");
        if (main) {
            main.hidden = false;
            main.textContent = "Smart Q could not restore this session. Refresh the page or sign in again.";
        }
    }
}

logoutButton?.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
        await logoutAccount();
    } catch (error) {
        if (!(error instanceof ApiError && (error.status === 401 || error.status === 403))) {
            logoutButton.disabled = false;
            return;
        }
    }
    window.location.replace("/login/");
});

securityForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setSecurityMessage("");

    const formData = new FormData(securityForm);
    const currentPassword = String(formData.get("current_password") || "");
    const newPassword = String(formData.get("new_password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const submit = securityForm.querySelector("button[type='submit']");

    if (newPassword !== confirmPassword) {
        setSecurityMessage("New password and confirmation must match.");
        return;
    }

    submit.disabled = true;
    submit.textContent = "Updating...";
    try {
        await changePassword(currentPassword, newPassword);
        securityForm.reset();
        setSecurityMessage("Password updated. Your current session remains active.", "success");
    } catch (error) {
        if (error instanceof ApiError) {
            const currentError = error.data?.current_password?.[0];
            const newError = error.data?.new_password?.[0];
            setSecurityMessage(currentError || newError || error.message);
        } else {
            setSecurityMessage("Smart Q could not update the password. Please try again.");
        }
    } finally {
        submit.disabled = false;
        submit.textContent = "Change password";
    }
});

bootstrapShell();
