// form-kernel-ts CLI.
//
// Usage:
//   tsx src/main.ts --expr "(+ 1 2)"
//   tsx src/main.ts --bench
//   tsx src/main.ts path/to/file.fk

import { readFile } from "node:fs/promises";
import { Frame, Kernel, Trace, walk } from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import { runBench } from "./bench.ts";
import { compileNode } from "./compiler.ts";
import { runNumericBench } from "./numeric-bench.ts";

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (--expr <expr> | --bench | --compiled <expr> | trace [--expr <expr> | <file.fk>] | <file.fk>)",
    );
    process.exit(2);
  }

  if (args[0] === "--bench") {
    runBench();
    return;
  }

  if (args[0] === "--numeric-bench") {
    runNumericBench();
    return;
  }

  if (args[0] === "trace") {
    await runTrace(args.slice(1));
    return;
  }

  const k = new Kernel();
  const frame = new Frame(null);

  if (args[0] === "--expr") {
    const expr = args[1];
    if (expr === undefined) {
      console.error("--expr requires an argument");
      process.exit(2);
    }
    const node = readForm(k, expr);
    const value = walk(k, node, frame);
    console.log(k.render(value));
    return;
  }

  if (args[0] === "--compiled") {
    const expr = args[1];
    if (expr === undefined) {
      console.error("--compiled requires an argument");
      process.exit(2);
    }
    const node = readForm(k, expr);
    const compiled = compileNode(k, node);
    const value = compiled(frame);
    console.log(k.render(value));
    return;
  }

  const path = args[0];
  if (path === undefined) {
    console.error("missing source file");
    process.exit(2);
  }
  const src = await readFile(path, "utf8");
  const node = readAll(k, src);
  const value = walk(k, node, frame);
  console.log(k.render(value));
}

// runTrace — execute with arm-dispatch tracing enabled, emit JSON report
// with the result, elapsed time, and per-arm dispatch counts including
// native Blueprint attribution. Sibling-parity with Rust/Go kernels.
async function runTrace(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts trace [--expr <expr> | <file.fk>]");
    process.exit(2);
  }
  let src: string;
  if (args[0] === "--expr") {
    if (args[1] === undefined) {
      console.error("--expr requires an argument");
      process.exit(2);
    }
    src = args[1];
  } else {
    src = await readFile(args[0]!, "utf8");
  }

  const k = new Kernel();
  k.trace = new Trace();
  const frame = new Frame(null);
  const node = readAll(k, src);
  const start = process.hrtime.bigint();
  const value = walk(k, node, frame);
  const elapsedNs = Number(process.hrtime.bigint() - start);

  const report = {
    result: k.render(value),
    elapsed_us: Math.round(elapsedNs / 1000),
    elapsed_human: `${(elapsedNs / 1000).toFixed(2)}µs`,
    trace: k.trace.toJSON(),
  };
  console.log(JSON.stringify(report, null, 2));
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`form-kernel-ts: ${msg}`);
  process.exit(1);
});
