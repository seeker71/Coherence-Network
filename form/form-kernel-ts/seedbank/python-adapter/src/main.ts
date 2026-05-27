// python-adapter CLI — entry point the parity suite invokes.
//
// Lives in the adapter (not in form-kernel-ts/src/main.ts) so the kernel
// stays language-agnostic. Three subcommands form the three-way parity
// gate alongside CPython:
//
//   python-compile <file.py> [out.fk|-]  — parse Python, emit .fk source
//   python-run     <file.py>             — compile + execute via Rust binary
//   python-eval    <file.py>             — parse + walk via TS evalPython
//   python-trace   <file.py>             — emit JSON dispatch report
//
// The parity suite captures stdout from cpython, python-eval (TS), and
// python-run (Rust kernel binary). All three must agree.

import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { dirname, resolve as pathResolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Frame, Kernel, Trace, walk, type Value } from "../../../src/kernel.ts";
import { evalPython, parsePython } from "./lang-python.ts";
import { emitFk } from "./lang-python-fk.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error(
      "usage: tsx src/main.ts (python-compile <file.py> [out.fk|-] | python-run <file.py> | python-eval <file.py> | python-trace <file.py>)",
    );
    process.exit(2);
  }

  switch (args[0]) {
    case "python-compile":
      return runPythonCompile(args.slice(1));
    case "python-run":
      return runPythonRun(args.slice(1));
    case "python-eval":
      return runPythonEval(args.slice(1));
    case "python-trace":
      return runPythonTrace(args.slice(1));
    default:
      console.error(`unknown subcommand: ${args[0]}`);
      process.exit(2);
  }
}

// runPythonCompile — parse Python source through BMF, emit .fk source the
// native form-kernel-rust binary can execute.
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
    (inPath.endsWith(".py") ? inPath.slice(0, -3) + ".fk" : inPath + ".fk");
  await writeFile(outPath, fk + "\n", "utf8");
  console.error(
    `form-kernel-ts: wrote ${outPath} (${fk.length} bytes of .fk)`,
  );
}

// runPythonRun — full Python → kernel pipeline. Parses Python, emits .fk,
// invokes the native form-kernel-rust binary on the emitted source.
// The end-to-end claim: no Python runtime in the execution path; only
// the kernel native binary walks the recipe tree.
async function runPythonRun(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-run <file.py>");
    process.exit(2);
  }
  const inPath = args[0]!;
  const src = await readFile(inPath, "utf8");

  const k = new Kernel();
  const tree = parsePython(k, src);
  const fk = emitFk(k, tree);

  const fkPath = inPath.endsWith(".py")
    ? inPath.slice(0, -3) + ".fk"
    : inPath + ".fk";
  await writeFile(fkPath, fk + "\n", "utf8");

  // Locate the native binary relative to this adapter:
  //   form-kernel-ts/seedbank/python-adapter/src/main.ts (this file)
  //   form-kernel-rust/target/release/form-kernel-rust
  // → up four levels (src → python-adapter → seedbank → form-kernel-ts → form/)
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
      console.error(`python-run: failed to spawn ${kernelPath}: ${err.message}`);
      console.error(
        "build the kernel first: cd ../../../form-kernel-rust && cargo build --release",
      );
      resolveCode(127);
    });
  });
  process.exit(exitCode);
}

// runPythonEval — parse Python, walk the captured-recipe tree through
// the TS evaluator. No kernel native binary, no .fk text round-trip —
// this is the second runtime in the three-way parity (CPython, TS
// evaluator, Rust kernel via .fk).
async function runPythonEval(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-eval <file.py>");
    process.exit(2);
  }
  const src = await readFile(args[0]!, "utf8");
  const k = new Kernel();
  const tree = parsePython(k, src);
  const value = evalPython(k, tree);
  console.log(renderForParity(value));
}

// runPythonTrace — parse + walk with trace enabled. Emits the JSON
// dispatch report the visualizer consumes.
async function runPythonTrace(args: string[]): Promise<void> {
  if (args.length === 0) {
    console.error("usage: tsx src/main.ts python-trace <file.py>");
    process.exit(2);
  }
  const src = await readFile(args[0]!, "utf8");
  const k = new Kernel();
  const parseStart = process.hrtime.bigint();
  const tree = parsePython(k, src);
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

// renderForParity — match CPython's print() output exactly. The kernel's
// own render uses `String(v.float)`, which drops the trailing zero for
// integer-valued floats (1.0 → "1"). The parity suite compares stdout
// strings, so we format floats here the way Python does, and emit
// booleans / None / lists in Python's surface form.
function renderForParity(v: Value): string {
  switch (v.kind) {
    case "f32":
    case "f64":
      return formatFloatPython(v.float);
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
      return v.bool ? "True" : "False";
    case "str":
      return v.str;
    case "null":
      return "None";
    case "list":
      return "[" + v.list.map(renderForParity).join(", ") + "]";
    case "closure":
      return `<closure>`;
    case "nodeid":
      return `@${v.nodeid.pkg}.${v.nodeid.level}.${v.nodeid.type}.${v.nodeid.inst}`;
    case "ctor":
      return `${v.ctor_name}(${v.args.map(renderForParity).join(", ")})`;
  }
}

function formatFloatPython(f: number): string {
  if (Number.isNaN(f)) return "nan";
  if (!Number.isFinite(f)) return f > 0 ? "inf" : "-inf";
  const s = String(f);
  if (s.includes(".") || s.includes("e") || s.includes("E")) return s;
  return `${s}.0`;
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`python-adapter: ${msg}`);
  process.exit(1);
});
