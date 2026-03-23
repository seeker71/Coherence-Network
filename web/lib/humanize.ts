const CC_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const DECIMAL_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

export function formatUsd(value: number): string {
  return `${CC_FORMAT.format(Number.isFinite(value) ? value : 0)} CC`;
}

export function formatDecimal(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "0";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function formatCount(value: number): string {
  return DECIMAL_FORMAT.format(Number.isFinite(value) ? value : 0);
}

export function formatConfidence(value: number): string {
  const normalized = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  return `${Math.round(normalized * 100)}%`;
}

export function humanizeManifestationStatus(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "none") return "Not proven yet";
  if (normalized === "partial") return "Partly proven";
  if (normalized === "validated") return "Proven in real use";
  if (!normalized) return "Unknown";
  return normalized
    .split("_")
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function humanizeStatus(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "none" || normalized === "partial" || normalized === "validated") {
    return humanizeManifestationStatus(normalized);
  }
  if (!normalized) return "Unknown";
  return normalized
    .split("_")
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function humanizeIdeaPriority(value: number): string {
  const normalized = Number.isFinite(value) ? value : 0;
  if (normalized >= 6) return "Best time to act";
  if (normalized >= 3) return "Good next step";
  if (normalized >= 1.5) return "Worth exploring";
  return "Keep watching";
}

export function explainIdeaPriority(value: number): string {
  const normalized = Number.isFinite(value) ? value : 0;
  if (normalized >= 6) return "High upside and enough proof to move now.";
  if (normalized >= 3) return "Promising, but not the very first thing to do.";
  if (normalized >= 1.5) return "Useful to explore after the stronger bets are moving.";
  return "Probably wait until the idea has clearer proof or a stronger upside.";
}

export function shortRef(value: string, head = 8): string {
  const trimmed = value.trim();
  if (trimmed.length <= head + 3) return trimmed;
  return `${trimmed.slice(0, head)}...`;
}
