const DEFAULT_FETCH_TIMEOUT_MS = 5000;
const DEFAULT_RETRY_COUNT = 2;
const RETRY_DELAY_MS = 500;

type FetchInput = Parameters<typeof fetch>[0];
type FetchOptions = Omit<Parameters<typeof fetch>[1], "signal"> & {
  signal?: AbortSignal;
  cache?: RequestCache;
};

function withTimeout(signal: AbortSignal | null, timeoutMs: number): AbortSignal {
  if (!timeoutMs || timeoutMs <= 0) {
    return signal ?? new AbortController().signal;
  }
  const controller = new AbortController();
  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
  }
  const timer = setTimeout(() => controller.abort(new DOMException("Request timed out", "TimeoutError")), timeoutMs);
  controller.signal.addEventListener(
    "abort",
    () => {
      clearTimeout(timer);
    },
    { once: true },
  );
  return controller.signal;
}

function isRetryable(status: number): boolean {
  return status === 408 || status === 429 || status === 502 || status === 503 || status === 504;
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchJsonOrNull<T>(
  input: FetchInput,
  options: FetchOptions = {},
  timeoutMs = DEFAULT_FETCH_TIMEOUT_MS,
  retries = DEFAULT_RETRY_COUNT,
): Promise<T | null> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : "(Request)";

  for (let attempt = 0; attempt <= retries; attempt++) {
    const timeout = withTimeout(options.signal ?? null, timeoutMs);
    try {
      const response = await fetch(input, {
        ...options,
        signal: timeout,
        cache: options.cache ?? "no-store",
      });
      if (!response.ok) {
        if (attempt < retries && isRetryable(response.status)) {
          console.warn(`[fetch] ${url} returned ${response.status}, retrying (${attempt + 1}/${retries})`);
          await delay(RETRY_DELAY_MS * (attempt + 1));
          continue;
        }
        console.error(`[fetch] ${url} failed with status ${response.status}`);
        return null;
      }
      try {
        return (await response.json()) as T;
      } catch (parseErr) {
        console.error(`[fetch] ${url} returned invalid JSON`, parseErr);
        return null;
      }
    } catch (err) {
      const isTimeout = err instanceof DOMException && err.name === "TimeoutError";
      if (attempt < retries && (isTimeout || (err instanceof TypeError))) {
        console.warn(`[fetch] ${url} ${isTimeout ? "timed out" : "network error"}, retrying (${attempt + 1}/${retries})`);
        await delay(RETRY_DELAY_MS * (attempt + 1));
        continue;
      }
      console.error(`[fetch] ${url} failed after ${attempt + 1} attempt(s)`, err);
      return null;
    }
  }
  return null;
}
