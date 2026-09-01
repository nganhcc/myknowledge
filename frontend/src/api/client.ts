import { getAccessToken } from "./token";

/**
 * Base URL for the backend API. Centralized in one place.
 *
 * In development this is empty: the Vite dev server proxies `/api/*` to the
 * FastAPI backend (see vite.config.ts), which sidesteps the backend's lack of
 * CORS. Set VITE_API_BASE_URL to an absolute origin to call the API directly.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "";

export type ApiErrorKind = "network" | "unauthorized" | "forbidden" | "not_found" | "validation" | "server" | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  /** HTTP status code, or 0 for network errors. */
  readonly status: number;
  /** Raw parsed error body when available. */
  readonly detail: unknown;

  constructor(kind: ApiErrorKind, status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiRequestInit {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  /** JSON-serializable body payload. Do not combine with `form` or `rawBody`. */
  body?: unknown;
  /** Already-serialized request body (e.g. URLSearchParams for login). */
  rawBody?: BodyInit;
  /** FormData to send as multipart/form-data (document upload). */
  form?: FormData;
  /** Additional headers (e.g. content-type overrides). */
  headers?: Record<string, string>;
}

function responseKind(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 422) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

export { responseKind };

function messageFor(kind: ApiErrorKind, detail: unknown): string {
  if (kind === "network") return "Cannot reach the server. Is the backend running?";
  if (kind === "unauthorized") return "Your session has expired. Please sign in again.";
  if (kind === "forbidden") return "You do not have permission to perform this action.";
  if (kind === "not_found") return "The requested resource was not found.";
  if (kind === "validation") {
    return formatValidationDetail(detail);
  }
  if (kind === "server") return "The server encountered an error. Please try again later.";
  return "An unexpected error occurred.";
}

export { messageFor };

function formatValidationDetail(detail: unknown): string {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = item.loc ?? [];
          const field = loc.slice(1).join(".");
          const msg = String(item.msg);
          return field ? `${field}: ${msg}` : msg;
        }
        return String(item);
      })
      .join("; ");
  }
  return "The submitted data is invalid.";
}

export async function apiRequest<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const { method = "GET", body, rawBody, form } = init;
  const headers: Record<string, string> = {
    ...init.headers,
  };

  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let requestBody: BodyInit | undefined;
  if (form) {
    requestBody = form;
  } else if (rawBody !== undefined) {
    requestBody = rawBody;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: requestBody,
    });
  } catch {
    throw new ApiError("network", 0, null, messageFor("network", null));
  }

  // 204 No Content and empty bodies.
  if (response.status === 204) {
    return undefined as T;
  }

  let detail: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      detail = await response.json();
    } catch {
      detail = null;
    }
  }

  if (!response.ok) {
    const kind = responseKind(response.status);
    throw new ApiError(kind, response.status, detail, messageFor(kind, detail));
  }

  if (contentType.includes("application/json")) {
    return detail as T;
  }

  // Non-JSON successful responses (e.g. SSE handled separately).
  return undefined as T;
}

export const http = {
  get: <T>(path: string, init: ApiRequestInit = {}) =>
    apiRequest<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init: ApiRequestInit = {}) =>
    apiRequest<T>(path, { ...init, method: "POST", body }),
  postForm: <T>(path: string, form: FormData) =>
    apiRequest<T>(path, { method: "POST", form }),
  patch: <T>(path: string, body?: unknown, init: ApiRequestInit = {}) =>
    apiRequest<T>(path, { ...init, method: "PATCH", body }),
  delete: <T>(path: string, init: ApiRequestInit = {}) =>
    apiRequest<T>(path, { ...init, method: "DELETE" }),
};