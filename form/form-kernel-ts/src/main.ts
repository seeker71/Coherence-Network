// form-kernel-ts CLI.
//
// Usage:
//   tsx src/main.ts --binary file.fkb
//   tsx src/main.ts --emit-binary out.fkb path/to/file.fk
//   tsx src/main.ts --expr "(+ 1 2)"
//   tsx src/main.ts --bench
//   tsx src/main.ts path/to/file.fk

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  deserializeRecipeArtifact,
  Frame,
  Kernel,
  serializeRecipeArtifact,
  shutdownSocketWorker,
  Trace,
  walk,
} from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import { runBench } from "./bench.ts";
import { compileNode } from "./compiler.ts";
import { runNumericBench } from "./numeric-bench.ts";

type CrashTraceContext = {
  mode: string;
  args: string[];
  source: string;
};

const crashTraceContext: CrashTraceContext = {
  mode: "startup",
  args: [],
  source: "",
};

// The kernel whose Form call stack the top-level catch surfaces. Set as
// soon as the CLI kernel exists; the frames live at the crash answer
// "which Form source line produced this".
let crashKernel: Kernel | null = null;

function setCrashTraceContext(mode: string, args: string[], source?: string): void {
  crashTraceContext.mode = mode;
  crashTraceContext.args = [...args];
  if (source !== undefined) crashTraceContext.source = source;
}

function sourceLineCount(source: string): number {
  return source.length === 0 ? 0 : source.split("\n").length;
}

async function writeKernelCrashTrace(err: unknown): Promise<string | null> {
  const dir = join(".cache", "form-kernel-ts");
  try {
    await mkdir(dir, { recursive: true });
  } catch {
    return null;
  }
  const when = new Date();
  const safeStamp = when.toISOString().replace(/[:.]/g, "");
  const path = join(dir, `crash-${safeStamp}-${process.pid}.json`);
  const message = err instanceof Error ? err.message : String(err);
  const stack = err instanceof Error ? err.stack : undefined;
  const source = crashTraceContext.source;
  const report = {
    when_utc: when.toISOString(),
    pid: process.pid,
    mode: crashTraceContext.mode,
    args: crashTraceContext.args,
    error: message,
    source_bytes: Buffer.byteLength(source, "utf8"),
    source_line_count: sourceLineCount(source),
    source_head: source.slice(0, 2000),
    source_tail: source.slice(Math.max(0, source.length - 2000)),
    js_stack: stack ?? null,
    // Innermost frame first — the Form-level call chain live at the crash.
    form_stack: crashKernel === null ? [] : [...crashKernel.formStack].reverse(),
  };
  try {
    await writeFile(path, `${JSON.stringify(report, null, 2)}\n`);
    return path;
  } catch {
    return null;
  }
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  setCrashTraceContext("startup", args);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (--binary file.fkb | --emit-binary out.fkb file.fk... | --expr <expr> | --bench | --compiled <expr> | trace ... | <file.fk>)",
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
  crashKernel = k;
  // Install the Form→host-JS JIT hook so (jit_compile "name") from Form
  // code compiles the named closure's body through compiler.ts.
  k.jitCompileHook = compileNode;
  const frame = new Frame(null);

  if (args[0] === "--binary") {
    const path = args[1];
    if (path === undefined) {
      console.error("--binary requires a path");
      process.exit(2);
    }
    setCrashTraceContext("binary", args);
    const root = deserializeRecipeArtifact(k, await readFile(path));
    k.setActiveRoots([root]);
    const value = walk(k, root, frame);
    k.substrateGC([value], frame);
    console.log(k.render(value));
    return;
  }

  if (args[0] === "--emit-binary") {
    const outPath = args[1];
    const paths = args.slice(2);
    if (outPath === undefined || paths.length === 0) {
      console.error("--emit-binary requires an output path and one or more .fk files");
      process.exit(2);
    }
    const src = (
      await Promise.all(paths.map((path) => readFile(path, "utf8")))
    ).join("\n");
    setCrashTraceContext("emit-binary", args, src);
    const node = readAll(k, src);
    await writeFile(outPath, serializeRecipeArtifact(k, node));
    return;
  }

  if (args[0] === "--expr") {
    const expr = args[1];
    if (expr === undefined) {
      console.error("--expr requires an argument");
      process.exit(2);
    }
    setCrashTraceContext("expr", args, expr);
    const node = readForm(k, expr);
    k.setActiveRoots([node]);
    const value = walk(k, node, frame);
    k.substrateGC([value], frame);
    console.log(k.render(value));
    return;
  }

  if (args[0] === "--compiled") {
    const expr = args[1];
    if (expr === undefined) {
      console.error("--compiled requires an argument");
      process.exit(2);
    }
    setCrashTraceContext("compiled", args, expr);
    const node = readForm(k, expr);
    const compiled = compileNode(k, node);
    const value = compiled(frame);
    console.log(k.render(value));
    return;
  }

  const paths = args;
  if (paths.length === 0) {
    console.error("missing source file");
    process.exit(2);
  }
  const parts = await Promise.all(paths.map((path) => readFile(path, "utf8")));
  // Line map: each file's first global line in the joined source, so
  // read-time attribution names the ORIGINAL file:line (+1 per join newline).
  let nextLine = 1;
  for (let i = 0; i < paths.length; i++) {
    k.readingFiles.push({ file: paths[i]!, startLine: nextLine });
    nextLine += (parts[i]!.match(/\n/g)?.length ?? 0) + 1;
  }
  const src = parts.join("\n");
  setCrashTraceContext("source", args, src);
  const node = readAll(k, src);
  k.readingFiles = [];
  k.setActiveRoots([node]);
  const value = walk(k, node, frame);
  k.substrateGC([value], frame);
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
  setCrashTraceContext("trace", args, src);

  const k = new Kernel();
  // Install the Form→host-JS JIT hook so (jit_compile "name") from Form
  // code compiles the named closure's body through compiler.ts.
  k.jitCompileHook = compileNode;
  k.trace = new Trace();
  const frame = new Frame(null);
  const node = readAll(k, src);
  k.setActiveRoots([node]);
  const start = process.hrtime.bigint();
  const value = walk(k, node, frame);
  k.substrateGC([value], frame);
  const elapsedNs = Number(process.hrtime.bigint() - start);

  const report = {
    result: k.render(value),
    elapsed_us: Math.round(elapsedNs / 1000),
    elapsed_human: `${(elapsedNs / 1000).toFixed(2)}µs`,
    trace: k.trace.toJSON(),
  };
  console.log(JSON.stringify(report, null, 2));
}

main()
  .then(() => {
    // Terminate the socket worker (if any) so the process exits promptly;
    // its net handles otherwise keep Node's event loop alive.
    shutdownSocketWorker();
  })
  .catch(async (err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`form-kernel-ts: ${msg}`);
    // The Form-level call chain live at the crash, innermost first — the
    // line that produced the fatal is the innermost attributed frame.
    const formStack = crashKernel?.formStackDisplay(16) ?? "";
    if (formStack !== "") {
      console.error(`form-kernel-ts: form stack: ${formStack}`);
    }
    const tracePath = await writeKernelCrashTrace(err);
    if (tracePath !== null) {
      console.error(`form-kernel-ts: crash trace: ${tracePath}`);
    }
    shutdownSocketWorker();
    process.exit(1);
  });
