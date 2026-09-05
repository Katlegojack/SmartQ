const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
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

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  const text = await response.text();
  return text ? { detail: text } : null;
}

export function clearCsrfToken() {
  csrfToken = null;
}

export async function ensureCsrfToken(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  const response = await fetch("/api/v1/accounts/csrf/", {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  const data = (await parseResponse(response)) as { csrfToken?: string; detail?: string } | null;
  if (!response.ok || !data?.csrfToken) {
    throw new ApiError(data?.detail || "Unable to establish a secure browser session.", response.status, data);
  }
  csrfToken = data.csrfToken;
  return csrfToken;
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  if (!SAFE_METHODS.has(method)) headers.set("X-CSRFToken", await ensureCsrfToken());

  let body: BodyInit | undefined;
  if (options.body instanceof FormData || typeof options.body === "string") {
    body = options.body;
  } else if (options.body !== undefined && options.body !== null) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
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
    const detail = typeof data === "object" && data && "detail" in data ? String((data as { detail?: unknown }).detail || "") : "";
    if (response.status === 403 && detail === "Authentication credentials were not provided.") {
      clearCsrfToken();
      window.dispatchEvent(new CustomEvent("smartq:session-expired"));
    }
    throw new ApiError(detail || "The request could not be completed.", response.status, data);
  }

  return data as T;
}

export function errorMessage(error: unknown, fallback = "The request could not be completed."): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.data && typeof error.data === "object") {
    for (const [field, value] of Object.entries(error.data as Record<string, unknown>)) {
      if (field === "detail") continue;
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }
  return error.message || fallback;
}
