const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const SESSION_EXPIRED_DETAIL = "Authentication credentials were not provided.";
const CSRF_FAILURE_MARKERS = [
    "CSRF verification failed",
    "CSRF token from the 'X-Csrftoken' HTTP header incorrect",
    'CSRF token from the "X-Csrftoken" HTTP header incorrect',
    "CSRF cookie not set",
];
let csrfToken = null;

export class ApiError extends Error {
    constructor(message, status, data = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.data = data;
    }
}

async function parseResponse(response) {
    if (response.status === 204) return null;

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        return response.json();
    }

    const text = await response.text();
    if (!text) return null;

    if (contentType.includes("text/html")) {
        const csrfFailure = response.status === 403 && CSRF_FAILURE_MARKERS.some(marker => text.includes(marker));
        return {
            detail: csrfFailure
                ? "Your secure session changed. Smart Q is refreshing it; please try again."
                : "The request could not be completed.",
            csrfFailure,
        };
    }

    return { detail: text };
}

function signalExpiredSession(response, data) {
    if (response.status !== 403 || data?.detail !== SESSION_EXPIRED_DETAIL) return;
    clearCsrfToken();
    if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("smartq:session-expired"));
    }
}

export function clearCsrfToken() {
    csrfToken = null;
}

export async function ensureCsrfToken({ force = false } = {}) {
    if (csrfToken && !force) return csrfToken;

    const response = await fetch("/api/v1/accounts/csrf/", {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });
    const data = await parseResponse(response);

    if (!response.ok || !data?.csrfToken) {
        throw new ApiError(
            data?.detail || "Unable to establish a secure browser session.",
            response.status,
            data,
        );
    }

    csrfToken = data.csrfToken;
    return csrfToken;
}

export async function apiRequest(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");

    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(body);
    }

    async function send() {
        if (!SAFE_METHODS.has(method)) {
            headers.set("X-CSRFToken", await ensureCsrfToken());
        }

        const response = await fetch(path, {
            ...options,
            method,
            headers,
            body,
            credentials: "same-origin",
        });
        const data = await parseResponse(response);
        return { response, data };
    }

    let result = await send();

    if (!SAFE_METHODS.has(method) && result.response.status === 403 && result.data?.csrfFailure) {
        clearCsrfToken();
        await ensureCsrfToken({ force: true });
        result = await send();
    }

    if (!result.response.ok) {
        signalExpiredSession(result.response, result.data);
        const message = result.data?.detail || "The request could not be completed.";
        throw new ApiError(message, result.response.status, result.data);
    }

    return result.data;
}

export function fieldErrors(errorData) {
    if (!errorData || typeof errorData !== "object") return [];

    const messages = [];
    for (const [field, value] of Object.entries(errorData)) {
        if (field === "detail" || field === "csrfFailure") continue;
        const values = Array.isArray(value) ? value : [value];
        for (const message of values) {
            if (typeof message === "string") {
                messages.push({ field, message });
            }
        }
    }
    return messages;
}
