/**
 * ANSI escape sequence helpers — zero dependencies.
 *
 * Provides cursor control, colors, progress bars, box drawing,
 * and number formatting for the live terminal UI.
 */

// ── Cursor & screen control ────────────────────────────────────────

export const ESC = {
  SAVE:           "\x1b[s",
  RESTORE:        "\x1b[u",
  HIDE_CURSOR:    "\x1b[?25l",
  SHOW_CURSOR:    "\x1b[?25h",
  CLEAR_LINE:     "\x1b[K",
  CLEAR_DOWN:     "\x1b[J",
  HOME:           "\x1b[H",
  RESET_SCROLL:   "\x1b[r",
};

/** Move cursor to absolute row, col (1-based). */
export function moveTo(row, col = 1) {
  return `\x1b[${row};${col}H`;
}

/** Set scroll region from startRow to endRow (1-based, inclusive). */
export function setScrollRegion(startRow, endRow) {
  return `\x1b[${startRow};${endRow}r`;
}

/** Move cursor up n lines. */
export function moveUp(n = 1) { return `\x1b[${n}A`; }

/** Move cursor down n lines. */
export function moveDown(n = 1) { return `\x1b[${n}B`; }

// ── Colors ─────────────────────────────────────────────────────────

export const C = {
  reset:   "\x1b[0m",
  bold:    "\x1b[1m",
  dim:     "\x1b[2m",
  italic:  "\x1b[3m",
  red:     "\x1b[31m",
  green:   "\x1b[32m",
  yellow:  "\x1b[33m",
  blue:    "\x1b[34m",
  magenta: "\x1b[35m",
  cyan:    "\x1b[36m",
  white:   "\x1b[37m",
  gray:    "\x1b[90m",
  bgBlack: "\x1b[40m",
};

/** Wrap text with color and auto-reset. */
export function color(text, ...styles) {
  return styles.join("") + text + C.reset;
}

// ── Progress bar ───────────────────────────────────────────────────

const FILL = "\u2588";  // █
const EMPTY = "\u2591"; // ░

/**
 * Render a progress bar: [████████░░░░░░░░] 52%
 * @param {number} pct - 0 to 100
 * @param {number} width - character width of the bar (default 20)
 */
export function progressBar(pct, width = 20) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  const filled = Math.round((clamped / 100) * width);
  const empty = width - filled;
  const bar = FILL.repeat(filled) + EMPTY.repeat(empty);
  const pctStr = String(Math.round(clamped)).padStart(3);
  if (clamped >= 100) return `${C.green}[${bar}]${C.reset} ${pctStr}%`;
  if (clamped >= 50) return `${C.cyan}[${bar}]${C.reset} ${pctStr}%`;
  return `${C.yellow}[${bar}]${C.reset} ${pctStr}%`;
}

// ── Box drawing ────────────────────────────────────────────────────

const BOX = { tl: "\u250c", tr: "\u2510", bl: "\u2514", br: "\u2518", h: "\u2500", v: "\u2502" };

/**
 * Draw a bordered box around lines of text.
 * @param {string[]} lines - Content lines
 * @param {number} width - Total box width (including borders)
 * @param {object} opts - { title, titleColor, borderColor }
 */
export function box(lines, width, opts = {}) {
  const innerW = width - 4; // 2 border chars + 2 padding spaces
  const bc = opts.borderColor || C.dim;
  const tc = opts.titleColor || C.cyan + C.bold;

  // Top border with optional title
  let topInner = BOX.h.repeat(width - 2);
  if (opts.title) {
    const titleStr = ` ${opts.title} `;
    const visLen = stripAnsi(titleStr).length;
    topInner = BOX.h.repeat(2) + tc + titleStr + bc + BOX.h.repeat(Math.max(0, width - 4 - visLen));
  }
  const top = bc + BOX.tl + topInner + BOX.tr + C.reset;

  // Content lines
  const body = lines.map(line => {
    const stripped = stripAnsi(line);
    const pad = Math.max(0, innerW - stripped.length);
    return bc + BOX.v + C.reset + " " + line + " ".repeat(pad) + " " + bc + BOX.v + C.reset;
  });

  // Bottom border
  const bottom = bc + BOX.bl + BOX.h.repeat(width - 2) + BOX.br + C.reset;

  return [top, ...body, bottom];
}

// ── Formatting ─────────────────────────────────────────────────────

/** Format number with commas: 1234 → "1,234" */
export function fmtNum(n) {
  if (n == null || isNaN(n)) return "--";
  return Number(n).toLocaleString("en-US");
}

/** Format USD cost: 0.0012 → "$0.0012" */
export function fmtCost(usd) {
  if (usd == null || isNaN(usd)) return "--";
  const val = Number(usd);
  if (val === 0) return "$0.00";
  if (val < 0.01) return `$${val.toFixed(4)}`;
  return `$${val.toFixed(2)}`;
}

/** Truncate string with ellipsis (simple character-boundary cut). */
export function truncate(str, max = 60) {
  if (!str) return "";
  if (str.length <= max) return str;
  return str.slice(0, max - 1) + "\u2026";
}

/**
 * Word-boundary-aware truncate. Trims to `max` chars then walks back to
 * the last space, avoiding mid-word cuts. Falls through to a hard cut if
 * the last space is < 40% of `max` (i.e. the first word alone is too long).
 * Uses "..." (three dots) rather than \u2026 because the word-aware variant
 * was historically used by tables with fixed-width terminals where `...`
 * takes a predictable 3 columns.
 */
export function truncateWords(str, max) {
  if (!str) return "";
  if (str.length <= max) return str;
  const trimmed = str.slice(0, max - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > max * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

/** Strip ANSI escape sequences for length calculations. */
export function stripAnsi(str) {
  return str.replace(/\x1b\[[0-9;]*m/g, "");
}

/** Format elapsed seconds: 127 → "2m 7s", 45 → "45s" */
export function fmtElapsed(sec) {
  if (sec == null) return "--";
  const s = Math.round(sec);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
}

/** Format a timestamp to HH:MM:SS local time. */
export function fmtTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString("en-US", { hour12: false });
  } catch {
    return "--:--:--";
  }
}

/** Check if stdout is an interactive TTY (not CI, not piped). */
export function isTTY() {
  return !!(process.stdout.isTTY && !process.env.CI);
}

/** Get terminal dimensions with safe defaults. */
export function termSize() {
  return {
    cols: process.stdout.columns || 80,
    rows: process.stdout.rows || 24,
  };
}
