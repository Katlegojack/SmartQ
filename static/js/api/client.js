const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const SESSION_EXPIRED_DETAIL = "Authentication credentials were not provided.";
const LOGOUT_PATH = "/api/v1/accounts/logout/";
const CSRF_FAILURE_MARKERS = [
    "CSRF verification failed",
    "CSRF Failed:",
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

function detailFrom(data) {
    if (!data || typeof data !== "object") return "";
    return typeof data.detail === "string" ? data.detail : "";
}

function isCsrfFailure(data) {
    if (!data || typeof data !== "object") return false;
    if (data.csrfFailure) return true;
    const detail = detailFrom(data);
    return CSRF_FAILURE_MARKERS.some(marker => detail.includes(marker));
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
                ? "Smart Q is refreshing your secure session."
                : "The request could not be completed.",
            csrfFailure,
        };
    }

    return { detail: text };
}

function signalExpiredSession(response, data) {
    if (response.status !== 403 || isCsrfFailure(data) || data?.detail !== SESSION_EXPIRED_DETAIL) return;
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
        cache: "no-store",
        headers: { Accept: "application/json", "Cache-Control": "no-cache" },
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

    // Django's csrf_protect can return an HTML 403 while DRF session
    // authentication returns JSON beginning with "CSRF Failed:". Both mean the
    // browser has a stale token, not that the user's Smart Q session is dead.
    // Refresh immediately and retry so forms and logout remain one-click.
    for (let retry = 0; retry < 2; retry += 1) {
        if (SAFE_METHODS.has(method) || result.response.status !== 403 || !isCsrfFailure(result.data)) break;
        clearCsrfToken();
        await ensureCsrfToken({ force: true });
        result = await send();
    }

    if (!result.response.ok) {
        const message = isCsrfFailure(result.data)
            ? "Smart Q could not refresh the secure session. Reload the page once and try again."
            : result.data?.detail || "The request could not be completed.";

        if (result.response.status === 403 && result.data?.detail === SESSION_EXPIRED_DETAIL) {
            clearCsrfToken();

            // If logout reaches an already-ended session, logout has already
            // achieved its goal. Do not surface a fake session-expired error.
            if (path === LOGOUT_PATH) return null;
        }

        signalExpiredSession(result.response, result.data);
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
