// form-kernel-ts CLI.
//
// Usage:
//   tsx src/main.ts --expr "(+ 1 2)"
//   tsx src/main.ts --bench
//   tsx src/main.ts path/to/file.fk [path/to/next.fk ...]

import { readFile } from "node:fs/promises";
import { Frame, Kernel, walk } from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import { runBench } from "./bench.ts";
import { compileNode } from "./compiler.ts";

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (--expr <expr> | --bench | --compiled <expr> | <file.fk> [file.fk ...])",
    );
    process.exit(2);
  }

  if (args[0] === "--bench") {
    runBench();
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
  const src = (await Promise.all(paths.map((path) => readFile(path, "utf8")))).join(
    "\n",
  );
  const node = readAll(k, src);
  const value = walk(k, node, frame);
  console.log(k.render(value));
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`form-kernel-ts: ${msg}`);
  process.exit(1);
});
