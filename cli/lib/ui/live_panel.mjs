/**
 * LivePanel — fixed header with scroll-region isolation.
 *
 * Renders a persistent metadata header at the top of the terminal,
 * while allowing log lines to scroll freely below it.
 * Uses ANSI scroll regions so the header never flickers.
 *
 * Supports an inline readline prompt for agent→user "ask" interactions.
 */

import { createInterface } from "node:readline/promises";
import {
  ESC, moveTo, setScrollRegion,
  C, color, progressBar, box,
  fmtNum, fmtCost, truncate, fmtElapsed, fmtTime, stripAnsi,
  isTTY, termSize,
} from "./ansi.mjs";

const HEADER_LINES = 7; // top border + 4 content + bottom border + blank spacer

export class LivePanel {
  /**
   * @param {object} opts
   * @param {string} opts.taskId
   * @param {string} opts.taskType
   * @param {boolean} [opts.tty] - override TTY detection
   */
  constructor({ taskId, taskType, tty }) {
    this.taskId = taskId;
    this.taskType = taskType || "task";
    this._tty = tty ?? isTTY();
    this._destroyed = false;
    this._rl = null;

    /** Current metadata state — updated by updateMeta(). */
    this.meta = {
      provider: "--",
      model: "--",
      tokens_in: 0,
      tokens_out: 0,
      tokens_total: 0,
      cost_usd: null,
      progress_pct: null,
      current_step: "",
      node_id: "--",
      heartbeat_ago: null,
      git_sha: "",
      status: "running",
      elapsed_sec: null,
    };

    if (this._tty) {
      this._initScrollRegion();
      this._onResize = () => this._handleResize();
      process.stdout.on("resize", this._onResize);
    } else {
      this._printPlainHeader();
    }
  }

  // ── Scroll region setup ──────────────────────────────────────────

  _initScrollRegion() {
    const { rows } = termSize();
    // Hide cursor during setup
    process.stdout.write(ESC.HIDE_CURSOR);
    // Reserve space for header by printing blank lines
    process.stdout.write("\n".repeat(HEADER_LINES));
    // Set scroll region: rows below the header scroll freely
    process.stdout.write(setScrollRegion(HEADER_LINES + 1, rows));
    // Move cursor into scroll region
    process.stdout.write(moveTo(HEADER_LINES + 1, 1));
    // Render the initial header
    this._renderHeader();
  }

  _handleResize() {
    if (this._destroyed) return;
    const { rows } = termSize();
    process.stdout.write(setScrollRegion(HEADER_LINES + 1, rows));
    this._renderHeader();
  }

  // ── Header rendering ─────────────────────────────────────────────

  _renderHeader() {
    if (!this._tty || this._destroyed) return;
    const { cols } = termSize();
    const m = this.meta;
    const w = Math.max(50, cols - 2);

    // Build content lines
    const providerStr = color(m.provider, C.cyan, C.bold);
    const modelStr = color(truncate(m.model, 40), C.white);
    const statusIcon = m.status === "running" ? color("●", C.green) :
                       m.status === "completed" ? color("✓", C.green) :
                       m.status === "failed" ? color("✗", C.red) : color("○", C.dim);
    const line1 = `${statusIcon} Provider: ${providerStr}    Model: ${modelStr}`;

    const tokIn = fmtNum(m.tokens_in);
    const tokOut = fmtNum(m.tokens_out);
    const tokTotal = fmtNum(m.tokens_total);
    const costStr = fmtCost(m.cost_usd);
    const line2 = `Tokens: ${color(tokIn, C.cyan)} in / ${color(tokOut, C.green)} out (${color(tokTotal, C.bold)} total)  Cost: ${color(costStr, C.yellow)}`;

    let line3;
    if (m.progress_pct != null) {
      const step = m.current_step ? `  ${truncate(m.current_step, w - 40)}` : "";
      line3 = `Progress: ${progressBar(m.progress_pct, 20)}${step}`;
    } else {
      const step = m.current_step ? truncate(m.current_step, w - 15) : color("awaiting updates...", C.dim);
      line3 = `Step: ${step}`;
    }

    const heartbeat = m.heartbeat_ago != null ? `${color("♥", C.red)} ${fmtElapsed(m.heartbeat_ago)} ago` : color("♥ --", C.dim);
    const sha = m.git_sha ? color(m.git_sha.slice(0, 7), C.dim) : "";
    const elapsed = m.elapsed_sec != null ? `  ${color(fmtElapsed(m.elapsed_sec), C.dim)}` : "";
    const line4 = `Node: ${color(truncate(m.node_id, 20), C.white)}  ${heartbeat}  SHA: ${sha}${elapsed}`;

    const shortId = this.taskId.slice(0, 12);
    const title = `COHERENCE \u2500\u2500 ${shortId} \u2500\u2500 ${this.taskType}`;
    const rendered = box([line1, line2, line3, line4], w, {
      title,
      titleColor: C.cyan + C.bold,
      borderColor: C.dim,
    });

    // Write header at top of screen
    process.stdout.write(ESC.SAVE);
    process.stdout.write(moveTo(1, 1));
    for (const line of rendered) {
      process.stdout.write(line + ESC.CLEAR_LINE + "\n");
    }
    // Blank spacer line
    process.stdout.write(ESC.CLEAR_LINE + "\n");
    process.stdout.write(ESC.RESTORE);
  }

  _printPlainHeader() {
    const m = this.meta;
    const shortId = this.taskId.slice(0, 12);
    console.log(`--- COHERENCE ${shortId} [${this.taskType}] ---`);
    console.log(`Provider: ${m.provider}  Model: ${m.model}`);
    console.log("");
  }

  // ── Public API ───────────────────────────────────────────────────

  /** Update metadata and re-render header. */
  updateMeta(partial) {
    Object.assign(this.meta, partial);
    if (this._tty) {
      this._renderHeader();
    }
  }

  /** Append a log line to the scrolling region. */
  appendLog(line) {
    if (this._destroyed) return;
    process.stdout.write(line + "\n");
  }

  /**
   * Show an agent question and prompt the user for an answer.
   * Returns a Promise that resolves with the user's answer string.
   * @param {string} question
   * @returns {Promise<string>}
   */
  async startAskPrompt(question) {
    if (!this._tty) {
      this.appendLog(`\n  AGENT QUESTION: ${question}`);
      this.appendLog("  (interactive response not available in pipe mode)\n");
      return "";
    }

    const { cols } = termSize();
    const w = Math.max(50, cols - 4);

    // Draw question box
    const qLines = this._wrapText(question, w - 6);
    const qBox = box(qLines, w, {
      title: "AGENT QUESTION",
      titleColor: C.yellow + C.bold,
      borderColor: C.yellow,
    });
    for (const line of qBox) {
      this.appendLog("  " + line);
    }

    // Show cursor for input
    process.stdout.write(ESC.SHOW_CURSOR);

    const rl = createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    this._rl = rl;

    try {
      const answer = await rl.question(color("  Your answer: ", C.cyan, C.bold));
      return answer || "";
    } finally {
      rl.close();
      this._rl = null;
      process.stdout.write(ESC.HIDE_CURSOR);
      this.appendLog(""); // blank line after answer
    }
  }

  /** Word-wrap text to fit within maxWidth. */
  _wrapText(text, maxWidth) {
    const words = text.split(/\s+/);
    const lines = [];
    let current = "";
    for (const word of words) {
      if (current.length + word.length + 1 > maxWidth && current.length > 0) {
        lines.push(current);
        current = word;
      } else {
        current = current ? current + " " + word : word;
      }
    }
    if (current) lines.push(current);
    return lines.length ? lines : [""];
  }

  /** Clean up terminal state. */
  destroy() {
    if (this._destroyed) return;
    this._destroyed = true;

    if (this._rl) {
      this._rl.close();
      this._rl = null;
    }

    if (this._tty) {
      process.stdout.write(ESC.RESET_SCROLL);
      process.stdout.write(ESC.SHOW_CURSOR);
      if (this._onResize) {
        process.stdout.removeListener("resize", this._onResize);
      }
    }
  }
}
