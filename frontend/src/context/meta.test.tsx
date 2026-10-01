import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { MetaProvider } from "./meta";

// The cold-start guard: a sleeping free-tier API must never look like a broken
// app. Slow or failing first requests show "waking the server", retry on their
// own, and only after the budget fall back to a friendly error with a retry.

const META = { framing: { project: "ready" } };

function ok(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function renderProvider() {
  return render(
    <MetaProvider>
      <p>App loaded</p>
    </MetaProvider>,
  );
}

describe("MetaProvider cold start", () => {
  it("says the server is waking while it retries, then loads", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(new Response("", { status: 503 }))
      .mockResolvedValueOnce(ok(META));
    renderProvider();

    expect(screen.getByText("Loading Amber…")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(100));
    expect(screen.getByText(/Waking the server/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry now" })).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.getByText("App loaded")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("treats a request that is merely slow as a waking server", async () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => {}));
    renderProvider();

    await act(() => vi.advanceTimersByTimeAsync(1_000));
    expect(screen.queryByText(/Waking the server/)).not.toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(4_000));
    expect(screen.getByText(/Waking the server/)).toBeInTheDocument();
  });

  it("gives up after the budget with a friendly, retryable error - no stack trace", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    renderProvider();

    await act(() => vi.advanceTimersByTimeAsync(100_000));
    expect(screen.getByRole("alert")).toHaveTextContent("The Amber API is not responding");
    expect(screen.queryByText(/TypeError|Failed to fetch/)).not.toBeInTheDocument();

    fetchMock.mockResolvedValue(ok(META));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await act(() => vi.advanceTimersByTimeAsync(100));
    expect(screen.getByText("App loaded")).toBeInTheDocument();
  });

  it("does not retry a request the API rejected", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "bad" }), { status: 422, headers: { "Content-Type": "application/json" } }),
    );
    renderProvider();

    await act(() => vi.advanceTimersByTimeAsync(20_000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("bad");
  });
});
