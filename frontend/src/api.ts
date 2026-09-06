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
let csrfToken: string | null = null;

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

type ParsedErrorPayload = {
  detail?: string;
  csrfFailure?: boolean;
  [key: string]: unknown;
};

function detailFrom(data: unknown): string {
  if (!data || typeof data !== "object" || !("detail" in data)) return "";
  return String((data as ParsedErrorPayload).detail || "");
}

function isCsrfFailure(data: unknown): boolean {
  if (!data || typeof data !== "object") return false;
  const parsed = data as ParsedErrorPayload;
  if (parsed.csrfFailure) return true;
  const detail = detailFrom(parsed);
  return CSRF_FAILURE_MARKERS.some((marker) => detail.includes(marker));
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();

  const text = await response.text();
  if (!text) return null;

  if (contentType.includes("text/html")) {
    const csrfFailure = response.status === 403 && CSRF_FAILURE_MARKERS.some((marker) => text.includes(marker));
    return {
      detail: csrfFailure
        ? "Smart Q is refreshing your secure session."
        : "The request could not be completed.",
      csrfFailure,
    } satisfies ParsedErrorPayload;
  }

  return { detail: text } satisfies ParsedErrorPayload;
}

export function clearCsrfToken() {
  csrfToken = null;
}

export async function ensureCsrfToken(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  const response = await fetch("/api/v1/accounts/csrf/", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json", "Cache-Control": "no-cache" },
  });
  const data = (await parseResponse(response)) as ParsedErrorPayload | null;
  if (!response.ok || !data?.csrfToken) {
    throw new ApiError(detailFrom(data) || "Unable to establish a secure browser session.", response.status, data);
  }
  csrfToken = String(data.csrfToken);
  return csrfToken;
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (options.body instanceof FormData || typeof options.body === "string") {
    body = options.body;
  } else if (options.body !== undefined && options.body !== null) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  async function send() {
    if (!SAFE_METHODS.has(method)) headers.set("X-CSRFToken", await ensureCsrfToken());

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

  // Django middleware can return HTML CSRF failures while DRF's
  // SessionAuthentication returns JSON with a "CSRF Failed:" detail. Treat
  // both as the same recoverable browser-state problem. Retry immediately
  // with a forced, non-cached token so the user never has to resubmit a form.
  for (let retry = 0; retry < 2; retry += 1) {
    if (SAFE_METHODS.has(method) || result.response.status !== 403 || !isCsrfFailure(result.data)) break;
    clearCsrfToken();
    await ensureCsrfToken(true);
    result = await send();
  }

  if (!result.response.ok) {
    const csrfFailure = isCsrfFailure(result.data);
    const detail = csrfFailure
      ? "Smart Q could not refresh the secure session. Reload the page once and try again."
      : detailFrom(result.data);

    if (!csrfFailure && result.response.status === 403 && detail === SESSION_EXPIRED_DETAIL) {
      clearCsrfToken();

      // Logout is idempotent: if the server session is already gone, the user
      // is already in the desired logged-out state. Do not convert that into a
      // fake "session expired" redirect/error.
      if (path === LOGOUT_PATH) return null as T;

      window.dispatchEvent(new CustomEvent("smartq:session-expired"));
    }
    throw new ApiError(detail || "The request could not be completed.", result.response.status, result.data);
  }

  return result.data as T;
}

export function errorMessage(error: unknown, fallback = "The request could not be completed."): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.data && typeof error.data === "object") {
    for (const [field, value] of Object.entries(error.data as Record<string, unknown>)) {
      if (field === "detail" || field === "csrfFailure") continue;
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }
  return error.message || fallback;
}
