import { ApiError } from "../api/client.js";
import {
    loginAccount,
    redirectToWorkspace,
    safeNextRoute,
} from "../auth/session.js";

const form = document.querySelector("[data-login-form]");
const message = document.querySelector("[data-form-message]");
const submitButton = form?.querySelector("button[type='submit']");

function setMessage(text, kind = "error") {
    if (!message) return;
    message.textContent = text;
    message.dataset.kind = kind;
    message.hidden = !text;
}

function setBusy(isBusy) {
    if (!submitButton) return;
    submitButton.disabled = isBusy;
    submitButton.textContent = isBusy ? "Signing in..." : "Sign in";
}

function openRequestedWorkspace(user) {
    const requested = new URLSearchParams(window.location.search).get("next") || "";
    const safeRoute = safeNextRoute(user?.role, requested);
    if (safeRoute) {
        window.location.replace(safeRoute);
        return;
    }
    redirectToWorkspace(user, { replace: true });
}

const params = new URLSearchParams(window.location.search);
if (params.get("created") === "1") {
    setMessage("Account created. Sign in with your new username and password.", "success");
}

const requestedRole = params.get("role");
if (requestedRole && form?.elements?.role) {
    const option = form.querySelector(`input[name="role"][value="${CSS.escape(requestedRole)}"]`);
    if (option) option.checked = true;
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setMessage("");

    const formData = new FormData(form);
    const role = String(formData.get("role") || "").trim();
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");

    if (!role) {
        setMessage("Choose the role you are signing in as.");
        return;
    }
    if (!username || !password) {
        setMessage("Enter both your username and password.");
        return;
    }

    setBusy(true);
    try {
        const user = await loginAccount(username, password, role);
        openRequestedWorkspace(user);
    } catch (error) {
        if (error instanceof ApiError && error.status === 429) {
            setMessage("Too many sign-in attempts. Wait a moment and try again.");
        } else if (error instanceof ApiError) {
            setMessage(error.message);
        } else {
            setMessage("Smart Q could not complete sign-in. Please try again.");
        }
    } finally {
        setBusy(false);
    }
});
