import { REPO_BLOB_MAIN, REPO_TREE } from "./types";

export function normalizeFilter(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return (value[0] || "").trim();
  return (value || "").trim();
}

export function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  return `${REPO_BLOB_MAIN}/${pathOrUrl.replace(/^\/+/, "")}`;
}

export function toBranchHref(branch: string): string {
  return `${REPO_TREE}/${encodeURIComponent(branch)}`;
}

export function statLabel(value: boolean): string {
  return value ? "tracked" : "missing";
}
