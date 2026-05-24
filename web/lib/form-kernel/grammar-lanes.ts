// Grammar lane compilers for the Form playground.

export type GrammarLaneId = "action" | "python" | "builder" | "modality";

export type GrammarLaneOutput = {
  title: string;
  form: string;
  summary: string;
  steps: string[];
  loadableExpression?: string;
};

export const ACTION_LANGUAGE_STARTER =
  "delegate @concept(lc-trust-over-fear) to @concept(lc-permission-is-interior)";

export const PYTHON_FORM_STARTER = `def integration_breath(signal, practice):
    if signal > 3:
        return practice + signal
    return practice`;

export const GRAMMAR_PATTERN_STARTER =
  "when {trigger} arises, offer {practice} for {duration}";

export const GRAMMAR_CAPTURES_STARTER = "trigger, practice, duration";

export const GRAMMAR_ACTION_STARTER =
  "emit movement_recipe(trigger, practice, duration)";

export const CROSS_MODALITY_STARTER = `A facilitator tells the story of a stuck team:
first they name the contraction, then each person mirrors one sentence,
then the group commits one reversible action and one verification breath.`;

const ACTION_VERBS = new Set(["delegate", "raise", "undo", "with", "invoke"]);

function cleanLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function quote(value: string): string {
  return JSON.stringify(value);
}

function parseCaptures(value: string): string[] {
  return value
    .split(/[,|\n]/)
    .map((part) => part.trim().replace(/^\{|\}$/g, ""))
    .filter(Boolean);
}

function indent(value: string, spaces = 2): string {
  const pad = " ".repeat(spaces);
  return value
    .split("\n")
    .map((line) => `${pad}${line}`)
    .join("\n");
}

export function compileActionLanguage(command: string): GrammarLaneOutput {
  const source = command.trim() || ACTION_LANGUAGE_STARTER;
  const verb = source.split(/\s+/)[0]?.toLowerCase() || "invoke";
  const recognized = ACTION_VERBS.has(verb);
  const form = recognized
    ? source
    : `invoke ${source.replace(/\s+/g, "_")} on @concept(lc-trust-over-fear)`;

  return {
    title: "BML / Action Language",
    form,
    loadableExpression: form,
    summary:
      "Action phrases become embodied Form commands that can be loaded into the evaluator and walked as recipes.",
    steps: [
      `verb: ${recognized ? verb : "invoke"}`,
      "bind subject / target",
      "walk delegation, exception, reverse, or method dispatch",
      "return a Recipe NodeID or runtime value",
    ],
  };
}

function parsePythonFunction(source: string): {
  name: string;
  args: string[];
  returns: string[];
} {
  const lines = cleanLines(source || PYTHON_FORM_STARTER);
  const header = lines.find((line) => line.startsWith("def ")) || "def recipe(input):";
  const match = header.match(/^def\s+([A-Za-z_][\w]*)\s*\(([^)]*)\)\s*:/);
  const name = match?.[1] || "recipe";
  const args = (match?.[2] || "input")
    .split(",")
    .map((arg) => arg.trim())
    .filter(Boolean);
  const returns = lines
    .filter((line) => line.startsWith("return "))
    .map((line) => line.replace(/^return\s+/, "").trim());
  return { name, args, returns: returns.length ? returns : ["input"] };
}

export function compilePythonToForm(source: string): GrammarLaneOutput {
  const parsed = parsePythonFunction(source);
  const bindings = parsed.args
    .map((arg, index) => `let ${arg} = .arg${index};`)
    .join("\n");
  const body = parsed.returns.length === 1
    ? parsed.returns[0]
    : `if ${parsed.returns[0]} then ${parsed.returns[0]} else ${
        parsed.returns[parsed.returns.length - 1]
      }`;
  const form = `method ${parsed.name} on @concept(local-python-form) {\n${indent(
    `do {\n${indent(bindings, 4)}\n    ${body}\n  }`,
    2,
  )}\n}`;

  return {
    title: "Python => Form",
    form,
    loadableExpression: form,
    summary:
      "A tiny Python function becomes a method-shaped Form recipe skeleton with arguments, body, and return expression visible.",
    steps: [
      `function: ${parsed.name}`,
      `captures: ${parsed.args.join(", ") || "none"}`,
      "map Python args to .arg slots",
      "preserve the return shape as the Form body",
    ],
  };
}

export function compileGrammarBuilder(
  pattern: string,
  captures: string,
  semanticAction: string,
): GrammarLaneOutput {
  const parsedCaptures = parseCaptures(captures || GRAMMAR_CAPTURES_STARTER);
  const patternText = pattern.trim() || GRAMMAR_PATTERN_STARTER;
  const actionText = semanticAction.trim() || GRAMMAR_ACTION_STARTER;
  const captureRows = parsedCaptures
    .map((capture) => `capture ${capture} as @field(${capture})`)
    .join("\n");
  const form = `grammar @concept(local-grammar-lane) {\n${indent(
    `pattern ${quote(patternText)}\n${captureRows}\naction { ${actionText} }`,
    2,
  )}\n}`;

  return {
    title: "Grammar Builder",
    form,
    summary:
      "A human-readable pattern becomes a grammar rule with named captures and one semantic action.",
    steps: [
      "recognize pattern",
      `capture ${parsedCaptures.length} field${parsedCaptures.length === 1 ? "" : "s"}`,
      "bind captures into a semantic action",
      "emit a reusable grammar cell",
    ],
  };
}

export function compileCrossModalityRecipe(
  source: string,
  recipeKind: string,
): GrammarLaneOutput {
  const kind = recipeKind || "teaching recipe";
  const text = (source.trim() || CROSS_MODALITY_STARTER).replace(/\s+/g, " ");
  const channels =
    kind === "movement recipe"
      ? ["gesture", "breath", "tempo", "somatic cue"]
      : kind === "implementation recipe"
        ? ["intent", "interface", "state change", "proof"]
        : kind === "verification recipe"
          ? ["claim", "observable", "command", "witness"]
          : ["story beat", "intonation", "image", "turning point"];
  const form = `recipe ${quote(kind)} {\n${indent(
    `source ${quote(text)}\nchannels [${channels.map(quote).join(", ")}]\nextract core_sequence\ncompose steps\nverify embodied_transfer`,
    2,
  )}\n}`;

  return {
    title: "Cross-Modality Recipe",
    form,
    summary:
      "A story, song, video, or source excerpt becomes a reusable recipe that preserves channel, sequence, and verification.",
    steps: [
      `mode: ${kind}`,
      `channels: ${channels.join(", ")}`,
      "extract repeatable sequence",
      "verify the transfer in another medium",
    ],
  };
}
