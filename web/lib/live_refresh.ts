"use client";

import { useEffect, useRef } from "react";

export const LIVE_REFRESH_EVENT = "coherence:live-refresh";

type LiveRefreshOptions = {
  runOnMount?: boolean;
};

export function useLiveRefresh(load: () => void | Promise<void>, options: LiveRefreshOptions = {}) {
  const { runOnMount = true } = options;
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  }, [load]);

  useEffect(() => {
    const invoke = () => {
      void loadRef.current();
    };

    if (runOnMount) {
      invoke();
    }

    const onRefresh = () => invoke();
    window.addEventListener(LIVE_REFRESH_EVENT, onRefresh);
    return () => {
      window.removeEventListener(LIVE_REFRESH_EVENT, onRefresh);
    };
  }, [runOnMount]);
}
