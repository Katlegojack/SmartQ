const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const SESSION_EXPIRED_DETAIL = "Authentication credentials were not provided.";
const LOGOUT_PATH = "/api/v1/accounts/logout/";
const CURRENT_ACCOUNT_PATH = "/api/v1/accounts/me/";
const CSRF_COOKIE_NAME = "csrftoken";
const CSRF_FAILURE_MARKERS = [
  "CSRF verification failed",
  "CSRF Failed:",
  "CSRF token from the 'X-Csrftoken' HTTP header incorrect",
  'CSRF token from the "X-Csrftoken" HTTP header incorrect',
  "CSRF cookie not set",
];
let csrfToken: string | null = null;
let authEpoch = 0;
let sessionValidationPromise: Promise<boolean> | null = null;

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

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const cookie = part.trim();
    if (!cookie.startsWith(prefix)) continue;
    try {
      return decodeURIComponent(cookie.slice(prefix.length));
    } catch {
      return cookie.slice(prefix.length);
    }
  }
  return "";
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

export function markAuthTransition() {
  authEpoch += 1;
  clearCsrfToken();
}

async function confirmAuthenticatedSession(): Promise<boolean> {
  if (sessionValidationPromise) return sessionValidationPromise;

  sessionValidationPromise = (async () => {
    try {
      const response = await fetch(CURRENT_ACCOUNT_PATH, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json", "Cache-Control": "no-cache" },
      });
      if (response.ok) return true;
      if (response.status === 401 || response.status === 403) return false;
      // A server/network-side problem must not be misrepresented as logout.
      return true;
    } catch {
      return true;
    }
  })().finally(() => {
    sessionValidationPromise = null;
  });

  return sessionValidationPromise;
}

export async function ensureCsrfToken(force = false): Promise<string> {
  // Django's default CSRF cookie is readable by browser JavaScript. Prefer the
  // live cookie on every mutation so a login in this tab never leaves us using
  // an in-memory token that Django has already rotated.
  const cookieToken = readCookie(CSRF_COOKIE_NAME);
  if (cookieToken && !force) {
    csrfToken = cookieToken;
    return cookieToken;
  }
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

  csrfToken = readCookie(CSRF_COOKIE_NAME) || String(data.csrfToken);
  return csrfToken;
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  suppressSessionExpiry?: boolean;
}

export async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const { suppressSessionExpiry = false, ...requestOptions } = options;
  const requestEpoch = authEpoch;
  const method = (requestOptions.method || "GET").toUpperCase();
  const headers = new Headers(requestOptions.headers || {});
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
      ...requestOptions,
      method,
      headers,
      body,
      credentials: "same-origin",
    });
    const data = await parseResponse(response);
    return { response, data };
  }

  let result = await send();

  // A request that started under an older login/logout transition must never
  // revive itself under the new account. This removes a race where an old
  // polling request could kick a freshly logged-in user back to Sign in.
  for (let retry = 0; retry < 2; retry += 1) {
    if (
      requestEpoch !== authEpoch
      || SAFE_METHODS.has(method)
      || result.response.status !== 403
      || !isCsrfFailure(result.data)
    ) break;
    clearCsrfToken();
    await ensureCsrfToken(true);
    result = await send();
  }

  let confirmedAuthenticated: boolean | null = null;
  const missingSession = () => (
    result.response.status === 403
    && !isCsrfFailure(result.data)
    && detailFrom(result.data) === SESSION_EXPIRED_DETAIL
  );

  // Before declaring a session dead, confirm the browser's CURRENT cookie with
  // /me/. If the original response belonged to an old request, retry once and
  // keep the valid new session instead of redirecting the user.
  if (
    !suppressSessionExpiry
    && path !== LOGOUT_PATH
    && missingSession()
    && requestEpoch === authEpoch
  ) {
    confirmedAuthenticated = await confirmAuthenticatedSession();
    if (confirmedAuthenticated && requestEpoch === authEpoch) {
      result = await send();
    }
  }

  if (!result.response.ok) {
    const csrfFailure = isCsrfFailure(result.data);
    const detail = csrfFailure
      ? "Smart Q could not refresh the secure session. Reload the page once and try again."
      : detailFrom(result.data);

    if (!csrfFailure && result.response.status === 403 && detail === SESSION_EXPIRED_DETAIL) {
      clearCsrfToken();

      // Logout is idempotent: if the server session is already gone, the user
      // is already in the desired logged-out state.
      if (path === LOGOUT_PATH) return null as T;

      if (!suppressSessionExpiry && requestEpoch === authEpoch) {
        if (confirmedAuthenticated === null) {
          confirmedAuthenticated = await confirmAuthenticatedSession();
        }
        if (!confirmedAuthenticated && requestEpoch === authEpoch) {
          window.dispatchEvent(new CustomEvent("smartq:session-expired"));
        }
      }
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
