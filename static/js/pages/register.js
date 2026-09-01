import { ApiError, fieldErrors } from "../api/client.js";
import {
    getCurrentAccount,
    loginAccount,
    redirectToWorkspace,
    registerCustomer,
} from "../auth/session.js";

const form = document.querySelector("[data-register-form]");
const message = document.querySelector("[data-form-message]");
const submitButton = form?.querySelector("button[type='submit']");

function setMessage(text, kind = "error") {
    if (!message) return;
    message.textContent = text;
    message.dataset.kind = kind;
    message.hidden = !text;
}

function clearFieldErrors() {
    for (const node of document.querySelectorAll("[data-field-error]")) {
        node.textContent = "";
        node.hidden = true;
    }
}

function applyFieldErrors(data) {
    for (const { field, message: text } of fieldErrors(data)) {
        const node = document.querySelector(`[data-field-error='${CSS.escape(field)}']`);
        if (node) {
            node.textContent = text;
            node.hidden = false;
        }
    }
}

function setBusy(isBusy) {
    if (!submitButton) return;
    submitButton.disabled = isBusy;
    submitButton.textContent = isBusy ? "Creating account..." : "Create account";
}

async function restoreExistingSession() {
    try {
        const user = await getCurrentAccount();
        if (user) redirectToWorkspace(user, { replace: true });
    } catch (error) {
        setMessage("Smart Q could not verify the current session. Please try again.");
    }
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFieldErrors();
    setMessage("");

    const formData = new FormData(form);
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (password !== confirmPassword) {
        const node = document.querySelector("[data-field-error='confirm_password']");
        if (node) {
            node.textContent = "Passwords do not match.";
            node.hidden = false;
        }
        return;
    }

    const payload = {
        username: String(formData.get("username") || "").trim(),
        password,
        first_name: String(formData.get("first_name") || "").trim(),
        last_name: String(formData.get("last_name") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        date_of_birth: String(formData.get("date_of_birth") || ""),
        gender: String(formData.get("gender") || ""),
        disability_status: formData.get("disability_status") === "on",
    };

    setBusy(true);
    try {
        await registerCustomer(payload);
        const user = await loginAccount(payload.username, payload.password);
        setMessage("Account created. Opening your workspace.", "success");
        redirectToWorkspace(user, { replace: true });
    } catch (error) {
        if (error instanceof ApiError) {
            applyFieldErrors(error.data);
            setMessage(error.message === "The request could not be completed."
                ? "Review the highlighted registration details."
                : error.message);
        } else {
            setMessage("Smart Q could not create the account. Please try again.");
        }
    } finally {
        setBusy(false);
    }
});

restoreExistingSession();
