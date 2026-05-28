// form-kernel-ts CLI.
//
// Usage:
//   tsx src/main.ts --binary file.fkb
//   tsx src/main.ts --emit-binary out.fkb path/to/file.fk
//   tsx src/main.ts --expr "(+ 1 2)"
//   tsx src/main.ts --bench
//   tsx src/main.ts path/to/file.fk

import { readFile, writeFile } from "node:fs/promises";
import { deserializeRecipeArtifact, Frame, Kernel, serializeRecipeArtifact, Trace, walk } from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import { runBench } from "./bench.ts";
import { compileNode } from "./compiler.ts";
import { runNumericBench } from "./numeric-bench.ts";

async function main(): Promise<void> {
  const args = process.argv.slice(2);
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

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`form-kernel-ts: ${msg}`);
  process.exit(1);
});
