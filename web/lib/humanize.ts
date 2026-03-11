const USD_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const DECIMAL_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

export function formatUsd(value: number): string {
  return USD_FORMAT.format(Number.isFinite(value) ? value : 0);
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

export function humanizeStatus(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "none") return "Not validated";
  if (normalized === "partial") return "Partially validated";
  if (normalized === "validated") return "Validated";
  if (!normalized) return "Unknown";
  return normalized
    .split("_")
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function shortRef(value: string, head = 8): string {
  const trimmed = value.trim();
  if (trimmed.length <= head + 3) return trimmed;
  return `${trimmed.slice(0, head)}...`;
}
