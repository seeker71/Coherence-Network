"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Mode = "novice" | "expert";

interface ExpertModeContextValue {
  mode: Mode;
  isExpert: boolean;
  toggle: () => void;
  setMode: (m: Mode) => void;
}

const ExpertModeContext = createContext<ExpertModeContextValue>({
  mode: "novice",
  isExpert: false,
  toggle: () => {},
  setMode: () => {},
});

const STORAGE_KEY = "coherence-ui-mode";

export function ExpertModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<Mode>("novice");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Mode | null;
      if (saved === "expert" || saved === "novice") {
        setModeState(saved);
      }
    } catch {
      // localStorage may be unavailable (SSR or privacy mode)
    }
  }, []);

  function setMode(m: Mode) {
    setModeState(m);
    try {
      localStorage.setItem(STORAGE_KEY, m);
    } catch {}
  }

  function toggle() {
    setMode(mode === "expert" ? "novice" : "expert");
  }

  return (
    <ExpertModeContext.Provider value={{ mode, isExpert: mode === "expert", toggle, setMode }}>
      {children}
    </ExpertModeContext.Provider>
  );
}

export function useExpertMode() {
  return useContext(ExpertModeContext);
}
