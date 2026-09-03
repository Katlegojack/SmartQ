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
const logoutButton = shell?.querySelector("[data-logout]") || null;
const securityForm = shell?.querySelector("[data-security-form]") || null;
const securityMessage = shell?.querySelector("[data-security-message]") || null;

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

function renderRoleNavigation(role) {
    for (const node of shell?.querySelectorAll("[data-role-nav]") || []) {
        node.hidden = node.dataset.roleNav !== role;
    }
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
    nav.append(link);
}

function renderWorkspaceCopy(role) {
    const copy = {
        customer: {
            title: "Customer workspace",
            text: "Your authenticated Smart Q workspace is ready. Booking and live queue modules are connected next.",
        },
        receptionist: {
            title: "Reception workspace",
            text: "Your branch-scoped reception shell is ready for customer search, assisted check-in and walk-in operations.",
        },
        counter_staff: {
            title: "Counter workspace",
            text: "Your assigned-counter shell is ready for the focused serving workflow that follows in the frontend roadmap.",
        },
        branch_manager: {
            title: "Branch management workspace",
            text: "Your branch-scoped management shell is ready for operational dashboard and reporting integration.",
        },
        system_admin: {
            title: "System administration workspace",
            text: "Your system-wide administration shell is ready for staff, branch, service and capacity management screens.",
        },
    }[role];

    if (!copy) return;
    setText("[data-workspace-title]", copy.title);
    setText("[data-workspace-copy]", copy.text);
}

function setSecurityMessage(text, kind = "error") {
    if (!securityMessage) return;
    securityMessage.textContent = text;
    securityMessage.dataset.kind = kind;
    securityMessage.hidden = !text;
}

async function bootstrapShell() {
    ensureCustomerRecoveryNavigation();
    if (!shell) return;

    try {
        const user = await getCurrentAccount();
        if (!user) {
            const next = encodeURIComponent(window.location.pathname);
            window.location.replace(`/login/?next=${next}`);
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
        renderRoleNavigation(user.role);
        renderWorkspaceCopy(user.role);
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
