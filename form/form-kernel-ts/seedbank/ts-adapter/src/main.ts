// ts-adapter CLI — entry point the parity suite invokes.
//
// Four subcommands form the three-way parity gate alongside tsc + node:
//
//   ts-compile <file.ts> [out.fk|-]  — parse TS, emit .fk source
//   ts-run     <file.ts>             — compile + execute via Rust binary
//   ts-eval    <file.ts>             — parse + walk via TS evalTypeScript
//   ts-trace   <file.ts>             — emit JSON dispatch report
//
// Three runtimes for parity:
//   1. tsc transpile → node runs the JS, captures stdout of final expr
//   2. ts-eval — lang-typescript.ts walker (no kernel binary, no .fk)
//   3. ts-run  — emit .fk + run via form-kernel-rust binary
// All three must agree on the printed value of the final expression.

import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { dirname, resolve as pathResolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Frame, Kernel, Trace, walk, type Value } from "../../../src/kernel.ts";
import {
  buildTypeScriptLanguage,
  parseTypeScript as parseTypeScriptNative,
  evalTypeScriptValue,
} from "../../../src/lang-typescript.ts";
import { parseTypeScript as parseTypeScriptLegacy } from "./lang-ts.ts";
import { emitTypeScriptFk } from "./lang-typescript-fk.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (ts-compile <file.ts> [out.fk|-] | ts-run <file.ts> | ts-eval <file.ts> | ts-trace <file.ts>)",
    );
    process.exit(2);
  }

  switch (args[0]) {
    case "ts-compile":
      return runTsCompile(args.slice(1));
    case "ts-run":
      return runTsRun(args.slice(1));
    case "ts-eval":
      return runTsEval(args.slice(1));
    case "ts-trace":
      return runTsTrace(args.slice(1));
    default:
      console.error(`unknown subcommand: ${args[0]}`);
      process.exit(2);
  }
}

async function runTsCompile(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts ts-compile <file.ts> [out.fk|-]");
    process.exit(2);
  }
  const inPath = args[0]!;
  const outArg = args[1];
  const src = await readFile(inPath, "utf8");

  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const tree = parseTypeScriptNative(k, ts.grammar, src);
  const fk = emitTypeScriptFk(k, tree);

  if (outArg === "-") {
    process.stdout.write(fk + "\n");
    return;
  }
  const outPath =
    outArg ??
    (inPath.endsWith(".ts") ? inPath.slice(0, -3) + ".fk" : inPath + ".fk");
  await writeFile(outPath, fk + "\n", "utf8");
  console.error(`ts-adapter: wrote ${outPath} (${fk.length} bytes of .fk)`);
}

async function runTsRun(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts ts-run <file.ts>");
    process.exit(2);
  }
  const inPath = args[0]!;
  const src = await readFile(inPath, "utf8");

  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const tree = parseTypeScriptNative(k, ts.grammar, src);
  const fk = emitTypeScriptFk(k, tree);

  const fkPath = inPath.endsWith(".ts")
    ? inPath.slice(0, -3) + ".fk"
    : inPath + ".fk";
  await writeFile(fkPath, fk + "\n", "utf8");

  const kernelPath = pathResolve(
    __dirname,
    "../../../../form-kernel-rust/target/release/form-kernel-rust",
  );

  const child = spawn(kernelPath, [fkPath], {
    stdio: ["ignore", "inherit", "inherit"],
  });
  const exitCode = await new Promise<number>((resolveCode) => {
    child.on("close", (code) => resolveCode(code ?? 1));
    child.on("error", (err) => {
      console.error(`ts-run: failed to spawn ${kernelPath}: ${err.message}`);
      console.error(
        "build the kernel first: cd ../../../form-kernel-rust && cargo build --release",
      );
      resolveCode(127);
    });
  });
  process.exit(exitCode);
}

async function runTsEval(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts ts-eval <file.ts>");
    process.exit(2);
  }
  const src = await readFile(args[0]!, "utf8");
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const tree = parseTypeScriptNative(k, ts.grammar, src);
  const value = evalTypeScriptValue(k, tree);
  console.log(renderJsForParity(value));
}

async function runTsTrace(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts ts-trace <file.ts>");
    process.exit(2);
  }
  const src = await readFile(args[0]!, "utf8");
  const k = new Kernel();
  const parseStart = process.hrtime.bigint();
  const tree = parseTypeScriptLegacy(k, src);
  const parseNs = Number(process.hrtime.bigint() - parseStart);

  k.trace = new Trace();
  const frame = new Frame(null);
  const evalStart = process.hrtime.bigint();
  const value = walk(k, tree, frame);
  const evalNs = Number(process.hrtime.bigint() - evalStart);

  const report = {
    source_path: args[0],
    source_bytes: src.length,
    result: renderForParity(value),
    parse_us: Math.round(parseNs / 1000),
    eval_us: Math.round(evalNs / 1000),
    trace: k.trace.toJSON(),
  };
  console.log(JSON.stringify(report, null, 2));
}

// renderJsForParity — lang-typescript.ts eval returns JS primitives.
function renderJsForParity(v: unknown): string {
  if (v === null) return "null";
  if (v === undefined) return "undefined";
  if (typeof v === "number") return formatFloatJs(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") return v;
  if (typeof v === "bigint") return String(v);
  if (Array.isArray(v)) return "[ " + v.map(renderJsForParity).join(", ") + " ]";
  if (typeof v === "function") return "[Function]";
  return String(v);
}

// renderForParity — legacy lang-ts.ts Value renderer (ts-trace / walk path).
function renderForParity(v: Value): string {
  switch (v.kind) {
    case "f32":
    case "f64":
      return formatFloatJs(v.float);
    case "int":
    case "i8":
    case "i16":
    case "u8":
    case "u16":
    case "u32":
      return String(v.int);
    case "i64":
    case "u64":
      return String(v.bigint);
    case "bool":
      return v.bool ? "true" : "false";
    case "str":
      return v.str;
    case "null":
      return "null";
    case "list":
      return "[ " + v.list.map(renderForParity).join(", ") + " ]";
    case "closure":
      return `[Function]`;
    case "nodeid":
      return `@${v.nodeid.pkg}.${v.nodeid.level}.${v.nodeid.type}.${v.nodeid.inst}`;
    case "ctor":
      return `${v.ctor_name}(${v.args.map(renderForParity).join(", ")})`;
  }
}

// JS-style float formatting: integer-valued floats render without
// trailing `.0` (node prints `1` for the number `1.0`). The kernel's
// own renderer drops `.0` already; this matches.
function formatFloatJs(f: number): string {
  if (Number.isNaN(f)) return "NaN";
  if (!Number.isFinite(f)) return f > 0 ? "Infinity" : "-Infinity";
  return String(f);
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`ts-adapter: ${msg}`);
  process.exit(1);
});
