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

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, `Cannot reach the Amber API at ${API_BASE_URL}`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, detailOf(body));
  return body as T;
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
