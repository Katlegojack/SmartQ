const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const SESSION_EXPIRED_DETAIL = "Authentication credentials were not provided.";
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
    return text ? { detail: text } : null;
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

    if (!SAFE_METHODS.has(method)) {
        headers.set("X-CSRFToken", await ensureCsrfToken());
    }

    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(body);
    }

    const response = await fetch(path, {
        ...options,
        method,
        headers,
        body,
        credentials: "same-origin",
    });

    const data = await parseResponse(response);
    if (!response.ok) {
        signalExpiredSession(response, data);
        const message = data?.detail || "The request could not be completed.";
        throw new ApiError(message, response.status, data);
    }

    return data;
}

export function fieldErrors(errorData) {
    if (!errorData || typeof errorData !== "object") return [];

    const messages = [];
    for (const [field, value] of Object.entries(errorData)) {
        if (field === "detail") continue;
        const values = Array.isArray(value) ? value : [value];
        for (const message of values) {
            if (typeof message === "string") {
                messages.push({ field, message });
            }
        }
    }
    return messages;
}
