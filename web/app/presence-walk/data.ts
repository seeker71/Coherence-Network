import {
  CalendarDays,
  CircleDot,
  HeartHandshake,
  MapPin,
  Route,
  Sparkles,
  UserRound,
  Waypoints,
} from "lucide-react";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";
import { unstable_noStore as noStore } from "next/cache";
import type { ComponentType } from "react";

import { loadMergedAppConfig } from "@/lib/app-config";
import { DEFAULT_LOCALE, type LocaleCode } from "@/lib/locales";

export type PresenceKind = "person" | "place" | "practice" | "community" | "event";

export type PresenceCopyTokens = Record<string, string | number>;

export type PresenceWalkRecord = {
  kind: PresenceKind;
  label: string;
  nodeType: string;
  title: string;
  voice: string;
  story: string;
  path: string;
  vision: string;
  visualWhy: string;
  image: string;
  conceptHref: string;
  directoryHref: string;
  accent: string;
  secondary: string;
  icon: "calendar-days" | "circle-dot" | "heart-handshake" | "map-pin" | "user-round";
};

export type PresenceWalk = PresenceWalkRecord & {
  Icon: ComponentType<{ className?: string }>;
};

export type PresenceWalkSupportingSection = {
  key: "story" | "path" | "vision";
  label: string;
  field: "story" | "path" | "vision";
  icon: "story" | "path" | "vision";
  color: "accent" | "secondary" | "neutral";
};

export type PeopleDirectorySection = {
  key: string;
  title: string;
  types: string[];
  lede: string;
};

export type PresenceContent = {
  presenceWalk: {
    index: {
      metadataTitle: string;
      metadataDescription: string;
      redirectKind: PresenceKind;
    };
    page: {
      metadataFallbackTitle: string;
      metadataTitleTemplate: string;
      navAriaLabel: string;
      presenceEyebrowTemplate: string;
      nodeTypeTemplate: string;
      directoryCta: string;
      conceptCta: string;
      visualWhyLabel: string;
      namedPresencesLabelTemplate: string;
      namedPresencesHeading: string;
      namedPresencesDescription: string;
      nodeCardMetaTemplate: string;
    };
    kindOrder: PresenceKind[];
    walks: Record<PresenceKind, PresenceWalkRecord>;
    supportingSections: PresenceWalkSupportingSection[];
  };
  people: {
    page: {
      metadataTitle: string;
      metadataDescription: string;
      eyebrow: string;
      title: string;
      totalDescriptionTemplate: string;
      presenceWalkCta: string;
      presenceWalkHref: string;
    };
    filterRules: {
      ignoredIdIncludes: string[];
      excludedContributorTypes: string[];
      initialFallback: string;
    };
    directorySectionOrder: string[];
    directorySections: Record<
      string,
      {
        key: string;
        title: string;
        types: string[];
        lede: string;
      }
    >;
  };
  nodePage: unknown;
  presenceNodes: unknown;
};

const WALK_ICONS: Record<PresenceWalkRecord["icon"], ComponentType<{ className?: string }>> = {
  "calendar-days": CalendarDays,
  "circle-dot": CircleDot,
  "heart-handshake": HeartHandshake,
  "map-pin": MapPin,
  "user-round": UserRound,
};

export const SUPPORTING_ICONS = {
  story: Sparkles,
  path: Route,
  vision: Waypoints,
};

export function getPresenceContent(lang: LocaleCode = DEFAULT_LOCALE): PresenceContent {
  noStore();
  return deepMerge(loadEnglishPresenceContent(), loadLocalePresenceOverrides(lang)) as PresenceContent;
}

export function getPresenceWalkIndexCopy(lang: LocaleCode = DEFAULT_LOCALE) {
  return getPresenceContent(lang).presenceWalk.index;
}

export function getPresenceWalkPageCopy(lang: LocaleCode = DEFAULT_LOCALE) {
  return getPresenceContent(lang).presenceWalk.page;
}

export function getPresenceKindOrder(lang: LocaleCode = DEFAULT_LOCALE): PresenceKind[] {
  return getPresenceContent(lang).presenceWalk.kindOrder;
}

export function getPresenceWalks(lang: LocaleCode = DEFAULT_LOCALE): PresenceWalk[] {
  const content = getPresenceContent(lang).presenceWalk;
  return content.kindOrder.map((kind) => withIcon(content.walks[kind]));
}

export function getPresenceWalk(
  kind: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceWalk | undefined {
  const walk = getPresenceContent(lang).presenceWalk.walks[kind as PresenceKind];
  return walk ? withIcon(walk) : undefined;
}

export function getPresenceWalkSupportingSections(
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceWalkSupportingSection[] {
  return getPresenceContent(lang).presenceWalk.supportingSections;
}

export function getPeoplePageCopy(lang: LocaleCode = DEFAULT_LOCALE) {
  return getPresenceContent(lang).people.page;
}

export function getPeopleFilterRules(lang: LocaleCode = DEFAULT_LOCALE) {
  return getPresenceContent(lang).people.filterRules;
}

export function getPeopleDirectorySections(
  lang: LocaleCode = DEFAULT_LOCALE,
): PeopleDirectorySection[] {
  const people = getPresenceContent(lang).people;
  return people.directorySectionOrder.map((key) => people.directorySections[key]);
}

export function formatPresenceCopy(template: string, tokens: PresenceCopyTokens): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) =>
    String(tokens[key] ?? ""),
  );
}

function withIcon(walk: PresenceWalkRecord): PresenceWalk {
  return {
    ...walk,
    Icon: WALK_ICONS[walk.icon],
  };
}

function deepMerge<T>(base: T, override: unknown): T {
  if (!override) return base;
  if (Array.isArray(base)) return override as T;
  if (!isPlainObject(base) || !isPlainObject(override)) {
    return (override === undefined ? base : override) as T;
  }

  const merged: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(override)) {
    if (value === undefined) continue;
    merged[key] = deepMerge((base as Record<string, unknown>)[key], value);
  }
  return merged as T;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function loadEnglishPresenceContent(): PresenceContent {
  return loadPresenceJson(DEFAULT_LOCALE) as PresenceContent;
}

function loadLocalePresenceOverrides(lang: LocaleCode): Record<string, unknown> {
  if (lang === DEFAULT_LOCALE) return {};
  return loadPresenceJson(lang);
}

function loadPresenceJson(lang: LocaleCode): Record<string, unknown> {
  const merged: Record<string, unknown> = {};
  for (const file of presenceContentCandidates(lang)) {
    const parsed = readJsonObject(file);
    if (parsed) Object.assign(merged, deepMerge(merged, parsed));
  }
  return merged;
}

function presenceContentCandidates(lang: LocaleCode): string[] {
  const filename = `${lang}.json`;
  return [
    resolve(repoPresenceContentDir(), filename),
    resolve(defaultRuntimePresenceContentDir(), filename),
    resolve(configuredRuntimePresenceContentDir(), filename),
  ];
}

function repoPresenceContentDir(): string {
  return resolve(process.cwd(), "content", "presence-walk");
}

function defaultRuntimePresenceContentDir(): string {
  return resolve(homedir(), ".coherence-network", "content", "presence-walk");
}

function configuredRuntimePresenceContentDir(): string {
  const config = loadMergedAppConfig();
  const configured =
    getNestedString(config, ["web", "presence_content_dir"]) ||
    getNestedString(config, ["content", "presence_walk_dir"]);
  return configured ? resolve(configured) : defaultRuntimePresenceContentDir();
}

function readJsonObject(file: string): Record<string, unknown> | null {
  if (!existsSync(file)) return null;
  try {
    const parsed: unknown = JSON.parse(readFileSync(file, "utf-8"));
    return isPlainObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function getNestedString(config: Record<string, unknown>, path: string[]): string | null {
  let current: unknown = config;
  for (const key of path) {
    if (!isPlainObject(current)) return null;
    current = current[key];
  }
  return typeof current === "string" && current.trim() ? current : null;
}
