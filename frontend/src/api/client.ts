import type {
  CounterfactualResponse,
  IndexResponse,
  Meta,
  PanelResponse,
  ScenariosResponse,
  SimulateRequest,
  SimulateResponse,
} from "./types";

/** Where the API lives: VITE_API_BASE_URL at build time, the local dev server otherwise. */
export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

/**
 * How long one attempt may hang before it is abandoned and retried. A sleeping
 * free-tier host can hold the first connection open while it boots.
 */
export const ATTEMPT_TIMEOUT_MS = 30_000;

/**
 * What went wrong, by what the reader can do about it:
 * - network: nothing answered (offline, wrong URL, or the server is waking)
 * - timeout: it did not answer in time
 * - waking: the host answered 502/503/504 - a gateway with the app not up yet
 * - input: the request was rejected (422) - the message says why
 * - server: the API failed (other 5xx)
 * - unknown: anything else
 */
export type ApiErrorKind = "network" | "timeout" | "waking" | "input" | "server" | "unknown";

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;

  constructor(status: number, message: string, kind?: ApiErrorKind) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind ?? kindOf(status);
  }
}

function kindOf(status: number): ApiErrorKind {
  if (status === 0) return "network";
  if (status === 502 || status === 503 || status === 504) return "waking";
  if (status === 422 || status === 400) return "input";
  if (status >= 500) return "server";
  return "unknown";
}

/** Errors worth retrying on their own: the server may simply be waking up. */
export function isTransient(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.kind === "network" || error.kind === "timeout" || error.kind === "waking")
  );
}

/** A reader-facing title and next step for an error - never a stack trace. */
export function describeError(error: Error): { title: string; detail: string } {
  if (!(error instanceof ApiError)) {
    return {
      title: "Something went wrong",
      detail: "The app hit an unexpected problem. Retrying usually fixes it.",
    };
  }
  switch (error.kind) {
    case "network":
    case "timeout":
    case "waking":
      return {
        title: "The Amber API is not responding",
        detail: `It may still be waking up, or be offline. Check your connection and retry. (API: ${API_BASE_URL})`,
      };
    case "input":
      return { title: "That request was rejected", detail: error.message };
    case "server":
      return {
        title: "The Amber API had a problem",
        detail: "The server failed to answer this request. Retrying may help; the other views still work.",
      };
    default:
      return { title: "Unexpected response from the Amber API", detail: error.message };
  }
}

function detailOf(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
        .filter(Boolean)
        .join("; ");
    }
  }
  return "Unexpected response from the Amber API";
}

/**
 * One request. An abort from the caller propagates as an AbortError; an attempt
 * that outlives ATTEMPT_TIMEOUT_MS becomes a "timeout" ApiError instead.
 */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const outer = init.signal;
  const forward = () => controller.abort();
  if (outer?.aborted) controller.abort();
  outer?.addEventListener("abort", forward, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, ATTEMPT_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
    } catch (error) {
      if (timedOut) {
        throw new ApiError(0, `No answer from ${API_BASE_URL} within ${ATTEMPT_TIMEOUT_MS / 1000} s`, "timeout");
      }
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new ApiError(0, `Cannot reach the Amber API at ${API_BASE_URL}`);
    }
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status, detailOf(body));
    return body as T;
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener("abort", forward);
  }
}

export const api = {
  meta: (signal?: AbortSignal) => request<Meta>("/meta", { signal }),
  panel: (params: { indicators?: string[]; countries?: string[] }, signal?: AbortSignal) => {
    const query = new URLSearchParams();
    if (params.indicators) query.set("indicators", params.indicators.join(","));
    if (params.countries) query.set("countries", params.countries.join(","));
    const suffix = query.toString() ? `?${query}` : "";
    return request<PanelResponse>(`/panel${suffix}`, { signal });
  },
  index: (weights: Record<string, number>, signal?: AbortSignal) => {
    const encoded = Object.entries(weights)
      .map(([pillar, weight]) => `${pillar}=${weight}`)
      .join(",");
    return request<IndexResponse>(`/index?weights=${encodeURIComponent(encoded)}`, { signal });
  },
  counterfactual: (signal?: AbortSignal) =>
    request<CounterfactualResponse>("/counterfactual", { signal }),
  scenarios: (signal?: AbortSignal) => request<ScenariosResponse>("/scenarios", { signal }),
  simulate: (body: SimulateRequest, signal?: AbortSignal) =>
    request<SimulateResponse>("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
};
