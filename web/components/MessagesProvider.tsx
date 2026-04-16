"use client";

import React, { createContext, useContext, useMemo } from "react";
import { DEFAULT_LOCALE, type LocaleCode } from "@/lib/locales";

type MessageTree = Record<string, unknown>;

type Ctx = {
  lang: LocaleCode;
  messages: MessageTree;
  fallback: MessageTree;
};

const MessagesContext = createContext<Ctx | null>(null);

function lookup(tree: MessageTree, key: string): string | undefined {
  const parts = key.split(".");
  let current: unknown = tree;
  for (const part of parts) {
    if (typeof current !== "object" || current === null) return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => {
    const v = params[k];
    return v === undefined ? `{${k}}` : String(v);
  });
}

type Props = {
  lang: LocaleCode;
  messages: MessageTree;
  fallback: MessageTree;
  children: React.ReactNode;
};

export function MessagesProvider({ lang, messages, fallback, children }: Props) {
  const value = useMemo<Ctx>(() => ({ lang, messages, fallback }), [lang, messages, fallback]);
  return <MessagesContext.Provider value={value}>{children}</MessagesContext.Provider>;
}

export function useT(): (key: string, params?: Record<string, string | number>) => string {
  const ctx = useContext(MessagesContext);
  return (key: string, params?: Record<string, string | number>) => {
    if (!ctx) return key;
    const hit = lookup(ctx.messages, key) ?? lookup(ctx.fallback, key);
    if (hit === undefined) {
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.warn(`[i18n] missing key: ${key} (lang=${ctx.lang})`);
      }
      return key;
    }
    return interpolate(hit, params);
  };
}

export function useLocale(): LocaleCode {
  const ctx = useContext(MessagesContext);
  return ctx?.lang ?? DEFAULT_LOCALE;
}
