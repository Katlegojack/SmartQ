import { ApiError } from "../api/client.js";
import {
    getCurrentAccount,
    loginAccount,
    redirectToWorkspace,
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
    setMessage("");

    const formData = new FormData(form);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");

    if (!username || !password) {
        setMessage("Enter both your username and password.");
        return;
    }

    setBusy(true);
    try {
        const user = await loginAccount(username, password);
        setMessage("Sign-in successful. Opening your workspace.", "success");
        redirectToWorkspace(user, { replace: true });
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

restoreExistingSession();
