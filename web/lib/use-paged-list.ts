// Reusable hook for surfaces that read a paginated list endpoint
// (`{items, total, limit, offset}` envelope). Accumulates items as
// pages arrive, exposes loadMore + loadedAll so the page can render
// either an explicit "show more" or an intersection-observer sentinel
// without inventing pagination state each time.
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchJsonOrNull } from "@/lib/fetch";

type PagedEnvelope<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

type Options = {
  pageSize?: number;
  timeoutMs?: number;
  retries?: number;
  // When buildUrl changes (e.g. filter changed), the hook resets and
  // refetches from offset 0. The function is identity-tracked, so memoize
  // it with useCallback in the caller.
  buildUrl: (offset: number, limit: number) => string;
};

type State<T> = {
  items: T[];
  total: number | null;
  loading: boolean;
  error: string | null;
};

export type PagedList<T> = State<T> & {
  loadedAll: boolean;
  loadMore: () => void;
  reload: () => void;
};

const DEFAULT_PAGE_SIZE = 100;

export function usePagedList<T>({
  buildUrl,
  pageSize = DEFAULT_PAGE_SIZE,
  timeoutMs = 8000,
  retries = 3,
}: Options): PagedList<T> {
  const [state, setState] = useState<State<T>>({
    items: [],
    total: null,
    loading: false,
    error: null,
  });
  const inFlight = useRef(false);
  const offsetRef = useRef(0);

  const fetchPage = useCallback(
    async (offset: number, replace: boolean) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setState((prev) => ({ ...prev, loading: true, error: null }));
      const url = buildUrl(offset, pageSize);
      const json = await fetchJsonOrNull<PagedEnvelope<T> | T[]>(
        url,
        { cache: "no-store" },
        timeoutMs,
        retries,
      );
      inFlight.current = false;
      if (json === null) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "could not reach api",
        }));
        return;
      }
      const items = Array.isArray(json) ? json : json.items ?? [];
      const total = Array.isArray(json)
        ? items.length + offset
        : typeof json.total === "number"
          ? json.total
          : items.length + offset;
      offsetRef.current = offset + items.length;
      setState((prev) => ({
        items: replace ? items : [...prev.items, ...items],
        total,
        loading: false,
        error: null,
      }));
    },
    [buildUrl, pageSize, timeoutMs, retries],
  );

  // Reset + load first page whenever the URL builder identity changes
  // (typically because a filter changed in the caller).
  useEffect(() => {
    offsetRef.current = 0;
    setState({ items: [], total: null, loading: false, error: null });
    void fetchPage(0, true);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    if (inFlight.current) return;
    if (state.total !== null && offsetRef.current >= state.total) return;
    void fetchPage(offsetRef.current, false);
  }, [fetchPage, state.total]);

  const reload = useCallback(() => {
    offsetRef.current = 0;
    void fetchPage(0, true);
  }, [fetchPage]);

  const loadedAll =
    state.total !== null && state.items.length >= state.total;

  return { ...state, loadedAll, loadMore, reload };
}
