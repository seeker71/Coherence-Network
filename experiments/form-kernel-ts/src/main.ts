// form-kernel-ts CLI.
//
// Usage:
//   tsx src/main.ts --expr "(+ 1 2)"
//   tsx src/main.ts --bench
//   tsx src/main.ts path/to/file.fk

import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { resolve as pathResolve, basename } from "node:path";
import { Frame, Kernel, Trace, walk } from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import { runBench } from "./bench.ts";
import { compileNode } from "./compiler.ts";
import { runNumericBench } from "./numeric-bench.ts";
import { evalPython, parsePython } from "./lang-python.ts";
import { emitFk } from "./lang-python-fk.ts";

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (--expr <expr> | --bench | --compiled <expr> | trace ... | python-trace <file.py> | python-compile <file.py> [out.fk|-] | python-run <file.py> | <file.fk>)",
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

  if (args[0] === "python-trace") {
    await runPythonTrace(args.slice(1));
    return;
  }

  if (args[0] === "python-compile") {
    await runPythonCompile(args.slice(1));
    return;
  }

  if (args[0] === "python-run") {
    await runPythonRun(args.slice(1));
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

  const paths = args;
  if (paths.length === 0) {
    console.error("missing source file");
    process.exit(2);
  }
  const src = (
    await Promise.all(paths.map((path) => readFile(path, "utf8")))
  ).join("\n");
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

// runPythonTrace — parse real Python source into a Form recipe tree via
// the BMF parser (lang-python.ts), then evaluate that tree through the
// kernel walker with trace enabled. Emits JSON with the result, elapsed
// time, parse-vs-eval-phase walk counts, and the full (arm_ty, arm_inst,
// arm_variant_name, count) variant breakdown. Closes the demonstration
// the visualizer arc was named for: not toy fib(8) — real Python through
// real BMF through the kernel, with full Blueprint attribution surface.
async function runPythonTrace(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-trace <file.py>");
    process.exit(2);
  }
  const src = await readFile(args[0]!, "utf8");

  const k = new Kernel();
  // Phase 1 — parse. The Python source becomes a NodeID tree in the
  // substrate. Parsing IS substrate-write work (intern_node calls);
  // tracing it here would surface the parser's structural shape, but we
  // separate phases so the EVAL trace is legible on its own.
  const parseStart = process.hrtime.bigint();
  const tree = parsePython(k, src);
  const parseNs = Number(process.hrtime.bigint() - parseStart);

  // Phase 2 — evaluate, with trace. The Form recipe tree walks through
  // the kernel; each dispatch records (arm_ty, arm_inst) in the trace,
  // including Blueprint attribution for any native that fires. The
  // Python CTOR dispatch (evalNode's switch) records into ctorCounts —
  // separate altitude from the kernel walker, so both surfaces are
  // legible.
  k.trace = new Trace();
  k.ctorCounts = new Map<string, number>();
  const evalStart = process.hrtime.bigint();
  const value = evalPython(k, tree);
  const evalNs = Number(process.hrtime.bigint() - evalStart);

  // Sort CTORs by dispatch count for readable report.
  const pythonDispatch = Array.from(k.ctorCounts.entries())
    .map(([ctor, count]) => ({ ctor, count }))
    .sort((a, b) => b.count - a.count);
  const ctorTotal = pythonDispatch.reduce((s, x) => s + x.count, 0);

  const report = {
    source_path: args[0],
    source_bytes: src.length,
    result: k.render(value),
    parse_us: Math.round(parseNs / 1000),
    eval_us: Math.round(evalNs / 1000),
    parse_human: `${(parseNs / 1000).toFixed(2)}µs`,
    eval_human: `${(evalNs / 1000).toFixed(2)}µs`,
    tree_root_nodeid: `@${tree.pkg}.${tree.level}.${tree.type}.${tree.inst}`,
    interned_recipes: k.byID.size,
    interned_strings: k.strs.length,
    python_dispatch_total: ctorTotal,
    python_dispatch: pythonDispatch,
    trace: k.trace.toJSON(),
  };
  console.log(JSON.stringify(report, null, 2));
}

// runPythonCompile — parse Python source through BMF, emit .fk source the
// native form-kernel-rust binary can execute. The compilation step that
// closes the Python → Form → kernel pipeline. By default writes to a
// sibling .fk file; an explicit output path overrides.
//
//   tsx src/main.ts python-compile foo.py            → foo.fk
//   tsx src/main.ts python-compile foo.py out.fk     → out.fk
//   tsx src/main.ts python-compile foo.py -          → stdout
async function runPythonCompile(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-compile <file.py> [out.fk|-]");
    process.exit(2);
  }
  const inPath = args[0]!;
  const outArg = args[1];
  const src = await readFile(inPath, "utf8");

  const k = new Kernel();
  const tree = parsePython(k, src);
  const fk = emitFk(k, tree);

  if (outArg === "-") {
    process.stdout.write(fk + "\n");
    return;
  }
  const outPath =
    outArg ??
    (inPath.endsWith(".py")
      ? inPath.slice(0, -3) + ".fk"
      : inPath + ".fk");
  await writeFile(outPath, fk + "\n", "utf8");
  console.error(`form-kernel-ts: wrote ${outPath} (${fk.length} bytes of .fk)`);
}

// runPythonRun — full Python → kernel pipeline. Parses Python, emits .fk,
// invokes the native form-kernel-rust binary on the emitted source. The
// end-to-end claim: no Python runtime in the execution path; only the
// kernel native binary walks the recipe tree.
//
//   tsx src/main.ts python-run foo.py
//
// Locates the form-kernel-rust binary at
//   experiments/form-kernel-rust/target/release/form-kernel-rust
// (build it first with `cd experiments/form-kernel-rust && cargo build --release`).
async function runPythonRun(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-run <file.py>");
    process.exit(2);
  }
  const inPath = args[0]!;
  const src = await readFile(inPath, "utf8");

  // Compile in-memory.
  const k = new Kernel();
  const tree = parsePython(k, src);
  const fk = emitFk(k, tree);

  // Write to a temp .fk next to the source so the native binary can
  // read it. Keeping it on disk (rather than piping stdin) makes the
  // recipe inspectable after the run — useful for debugging.
  const fkPath = inPath.endsWith(".py")
    ? inPath.slice(0, -3) + ".fk"
    : inPath + ".fk";
  await writeFile(fkPath, fk + "\n", "utf8");

  // Locate the native binary. Walks up from cwd looking for the kernel.
  const kernelPath = pathResolve(
    process.cwd(),
    "../form-kernel-rust/target/release/form-kernel-rust",
  );

  // Spawn the native binary and forward its output.
  const child = spawn(kernelPath, [fkPath], {
    stdio: ["ignore", "inherit", "inherit"],
  });
  const exitCode = await new Promise<number>((resolveCode) => {
    child.on("close", (code) => resolveCode(code ?? 1));
    child.on("error", (err) => {
      console.error(`python-run: failed to spawn ${kernelPath}: ${err.message}`);
      console.error(
        "Build the kernel first: cd experiments/form-kernel-rust && cargo build --release",
      );
      resolveCode(127);
    });
  });
  process.exit(exitCode);
  // Silence unused-import lint if basename isn't used elsewhere.
  void basename;
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`form-kernel-ts: ${msg}`);
  process.exit(1);
});
