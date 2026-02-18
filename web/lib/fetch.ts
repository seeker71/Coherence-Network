const DEFAULT_FETCH_TIMEOUT_MS = 5000;

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

export async function fetchJsonOrNull<T>(
  input: FetchInput,
  options: FetchOptions = {},
  timeoutMs = DEFAULT_FETCH_TIMEOUT_MS,
): Promise<T | null> {
  const timeout = withTimeout(options.signal ?? null, timeoutMs);
  try {
    const response = await fetch(input, {
      ...options,
      signal: timeout,
      cache: options.cache ?? "no-store",
    });
    if (!response.ok) {
      return null;
    }
    try {
      return (await response.json()) as T;
    } catch {
      return null;
    }
  } catch {
    return null;
  }
}
