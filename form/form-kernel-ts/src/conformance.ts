// TypeScript conformance runner for shared Form kernel vectors.

import { readFileSync } from "node:fs";

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

type Bindings = Array<Record<string, JsonValue>>;

interface Question extends Record<string, JsonValue> {
  id: string;
  agent_id: string;
  question: string;
  task_id: string | null;
  thread_id: string | null;
  choices: string[];
  context: Record<string, JsonValue>;
  status: "open" | "answered";
  answer: string | null;
  answered_by: string | null;
}

interface QuestionEvent extends Record<string, JsonValue> {
  id: string;
  sequence: number;
  event_type: string;
  question_id: string;
  question: Question;
}

class QuestionState {
  questions = new Map<string, Question>();
  events: QuestionEvent[] = [];
  private nextQuestion = 0;
  private nextEvent = 0;

  createQuestion(
    agentId: string,
    question: string,
    choices: string[],
    context: Record<string, JsonValue>,
  ): Question {
    this.nextQuestion++;
    const item: Question = {
      id: `question_ts_${String(this.nextQuestion).padStart(4, "0")}`,
      agent_id: agentId,
      question,
      task_id: contextString(context, "task_id"),
      thread_id: contextString(context, "thread_id"),
      choices,
      context,
      status: "open",
      answer: null,
      answered_by: null,
    };
    this.questions.set(item.id, item);
    this.emit("question_opened", item);
    return item;
  }

  answerQuestion(questionId: string, answer: string, answeredBy: string): void {
    const item = this.questions.get(questionId);
    if (item === undefined) {
      throw new Error(`question ${JSON.stringify(questionId)} not found`);
    }
    item.answer = answer;
    item.answered_by = answeredBy;
    item.status = "answered";
    this.emit("question_answered", item);
  }

  awaitAnswer(questionId: string): JsonValue {
    const item = this.questions.get(questionId);
    if (item === undefined) {
      throw new Error(`question ${JSON.stringify(questionId)} not found`);
    }
    return item.answer;
  }

  private emit(eventType: string, question: Question): void {
    this.nextEvent++;
    this.events.push({
      id: `event_ts_${String(this.nextEvent).padStart(4, "0")}`,
      sequence: this.nextEvent,
      event_type: eventType,
      question_id: question.id,
      question,
    });
  }
}

function contextString(
  context: Record<string, JsonValue>,
  key: string,
): string | null {
  const value = context[key];
  return typeof value === "string" ? value : null;
}

function lookup(bindings: Bindings, name: string): JsonValue | undefined {
  for (let i = bindings.length - 1; i >= 0; i--) {
    if (Object.prototype.hasOwnProperty.call(bindings[i], name)) {
      return bindings[i]![name];
    }
  }
  return undefined;
}

function assign(bindings: Bindings, name: string, value: JsonValue): JsonValue {
  for (let i = bindings.length - 1; i >= 0; i--) {
    if (Object.prototype.hasOwnProperty.call(bindings[i], name)) {
      bindings[i]![name] = value;
      return value;
    }
  }
  throw new Error(`set ${JSON.stringify(name)} has no enclosing binding`);
}

function isIdent(name: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(name);
}

function splitArgs(input: string): string[] {
  const args: string[] = [];
  let current = "";
  let inString = false;
  let escape = false;
  let parenDepth = 0;
  let squareDepth = 0;
  let braceDepth = 0;

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]!;
    if (escape) {
      current += ch;
      escape = false;
      continue;
    }
    if (ch === "\\" && inString) {
      current += ch;
      escape = true;
      continue;
    }
    if (ch === '"') {
      current += ch;
      inString = !inString;
      continue;
    }
    if (!inString) {
      if (ch === "(") parenDepth++;
      else if (ch === ")") parenDepth--;
      else if (ch === "[") squareDepth++;
      else if (ch === "]") squareDepth--;
      else if (ch === "{") braceDepth++;
      else if (ch === "}") braceDepth--;
      else if (
        ch === "," &&
        parenDepth === 0 &&
        squareDepth === 0 &&
        braceDepth === 0
      ) {
        if (current.trim() !== "") args.push(current.trim());
        current = "";
        continue;
      }
    }
    current += ch;
  }
  if (current.trim() !== "") args.push(current.trim());
  return args;
}

function splitTopLevel(input: string, separator: string): string[] {
  const parts: string[] = [];
  let current = "";
  let inString = false;
  let escape = false;
  let parenDepth = 0;
  let squareDepth = 0;
  let braceDepth = 0;

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]!;
    if (escape) {
      current += ch;
      escape = false;
      continue;
    }
    if (ch === "\\" && inString) {
      current += ch;
      escape = true;
      continue;
    }
    if (ch === '"') {
      current += ch;
      inString = !inString;
      continue;
    }
    if (!inString) {
      if (ch === "(") parenDepth++;
      else if (ch === ")") parenDepth--;
      else if (ch === "[") squareDepth++;
      else if (ch === "]") squareDepth--;
      else if (ch === "{") braceDepth++;
      else if (ch === "}") braceDepth--;
      else if (
        ch === separator &&
        parenDepth === 0 &&
        squareDepth === 0 &&
        braceDepth === 0
      ) {
        if (current.trim() !== "") parts.push(current.trim());
        current = "";
        continue;
      }
    }
    current += ch;
  }
  if (current.trim() !== "") parts.push(current.trim());
  return parts;
}

function findTopLevelKeyword(input: string, keyword: string): number {
  let inString = false;
  let escape = false;
  let parenDepth = 0;
  let squareDepth = 0;
  let braceDepth = 0;

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]!;
    if (escape) {
      escape = false;
      continue;
    }
    if (ch === "\\" && inString) {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "(") parenDepth++;
    else if (ch === ")") parenDepth--;
    else if (ch === "[") squareDepth++;
    else if (ch === "]") squareDepth--;
    else if (ch === "{") braceDepth++;
    else if (ch === "}") braceDepth--;
    if (
      parenDepth === 0 &&
      squareDepth === 0 &&
      braceDepth === 0 &&
      input.startsWith(keyword, i)
    ) {
      return i;
    }
  }
  return -1;
}

function splitHeadBody(input: string): [string, string] {
  const text = input.trim();
  if (!text.endsWith("}")) {
    throw new Error(`block expression missing closing brace: ${input}`);
  }
  let inString = false;
  let escape = false;
  let parenDepth = 0;
  let squareDepth = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (escape) {
      escape = false;
      continue;
    }
    if (ch === "\\" && inString) {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "(") parenDepth++;
    else if (ch === ")") parenDepth--;
    else if (ch === "[") squareDepth++;
    else if (ch === "]") squareDepth--;
    else if (ch === "{" && parenDepth === 0 && squareDepth === 0) {
      return [text.slice(0, i).trim(), text.slice(i + 1, -1).trim()];
    }
  }
  throw new Error(`block expression missing body: ${input}`);
}

function parseString(raw: string): string {
  const value = JSON.parse(raw.trim());
  if (typeof value !== "string") {
    throw new Error(`expected string literal, got ${raw}`);
  }
  return value;
}

function parseArray(raw: string): JsonValue[] {
  const text = raw.trim();
  if (text === "[]") return [];
  if (!text.startsWith("[") || !text.endsWith("]")) {
    throw new Error(`invalid list ${raw}`);
  }
  return splitArgs(text.slice(1, -1)).map((item) => parseValue(item));
}

function parseObject(raw: string): Record<string, JsonValue> {
  const text = raw.trim();
  if (text === "{}") return {};
  if (!text.startsWith("{") || !text.endsWith("}")) {
    throw new Error(`invalid object ${raw}`);
  }
  const out: Record<string, JsonValue> = {};
  for (const pair of splitArgs(text.slice(1, -1))) {
    const parts = splitTopLevel(pair, ":");
    if (parts.length !== 2) {
      throw new Error(`invalid object pair ${pair}`);
    }
    const key = parts[0]!.trim().replace(/^"|"$/g, "");
    out[key] = parseValue(parts[1]!);
  }
  return out;
}

function parseValue(raw: string): JsonValue {
  const text = raw.trim();
  if (text.startsWith("[") && text.endsWith("]")) return parseArray(text);
  if (text.startsWith("{") && text.endsWith("}")) return parseObject(text);
  return JSON.parse(text) as JsonValue;
}

function callBody(form: string, name: string): string {
  const trimmed = form.trim();
  const prefix = `${name}(`;
  if (!trimmed.startsWith(prefix) || !trimmed.endsWith(")")) {
    throw new Error(`unsupported Form expression ${JSON.stringify(form)}`);
  }
  return trimmed.slice(prefix.length, -1);
}

function callParts(form: string): [string, string[]] | null {
  const trimmed = form.trim();
  const open = trimmed.indexOf("(");
  if (open <= 0 || !trimmed.endsWith(")")) return null;
  const name = trimmed.slice(0, open).trim();
  if (!isIdent(name)) return null;
  return [name, splitArgs(trimmed.slice(open + 1, -1))];
}

function expectArray(value: JsonValue, name: string): JsonValue[] {
  if (!Array.isArray(value)) {
    throw new Error(`${name} expects a list`);
  }
  return value;
}

function expectNumber(value: JsonValue, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${name} expects an integer`);
  }
  return Math.trunc(value);
}

function evalBuiltin(name: string, args: JsonValue[]): JsonValue {
  switch (name) {
    case "len": {
      if (args.length !== 1) throw new Error(`len expects 1 arg, got ${args.length}`);
      const value = args[0];
      if (Array.isArray(value)) return value.length;
      if (typeof value === "string") return Array.from(value).length;
      if (value !== null && typeof value === "object") return Object.keys(value).length;
      throw new Error("len expects a list, object, or string");
    }
    case "head": {
      if (args.length !== 1) throw new Error(`head expects 1 arg, got ${args.length}`);
      return expectArray(args[0] ?? null, "head")[0] ?? null;
    }
    case "tail": {
      if (args.length !== 1) throw new Error(`tail expects 1 arg, got ${args.length}`);
      return expectArray(args[0] ?? null, "tail").slice(1);
    }
    case "sum": {
      if (args.length !== 1) throw new Error(`sum expects 1 arg, got ${args.length}`);
      return expectArray(args[0] ?? null, "sum").reduce<number>(
        (acc, item) => acc + expectNumber(item, "sum"),
        0,
      );
    }
    case "concat": {
      if (args.length !== 2) {
        throw new Error(`concat expects 2 args, got ${args.length}`);
      }
      const [left, right] = args;
      if (typeof left === "string" && typeof right === "string") {
        return left + right;
      }
      if (Array.isArray(left) && Array.isArray(right)) {
        return [...left, ...right];
      }
      throw new Error("concat expects two strings or two lists");
    }
    case "reverse": {
      if (args.length !== 1) {
        throw new Error(`reverse expects 1 arg, got ${args.length}`);
      }
      const value = args[0];
      if (typeof value === "string") return Array.from(value).reverse().join("");
      return [...expectArray(value ?? null, "reverse")].reverse();
    }
    default:
      throw new Error(`unsupported Form function ${JSON.stringify(name)}`);
  }
}

type ExprToken =
  | { kind: "value"; value: JsonValue }
  | { kind: "op"; op: string }
  | { kind: "lparen" }
  | { kind: "rparen" };

function tokenizeExpr(input: string, bindings: Bindings): ExprToken[] {
  const tokens: ExprToken[] = [];
  let pos = 0;
  while (pos < input.length) {
    const ch = input[pos]!;
    if (/\s/.test(ch)) {
      pos++;
      continue;
    }
    if (ch === '"') {
      let end = pos + 1;
      let escape = false;
      while (end < input.length) {
        const current = input[end]!;
        if (escape) escape = false;
        else if (current === "\\") escape = true;
        else if (current === '"') {
          end++;
          break;
        }
        end++;
      }
      tokens.push({ kind: "value", value: parseString(input.slice(pos, end)) });
      pos = end;
      continue;
    }
    if (/[0-9]/.test(ch)) {
      const start = pos;
      while (pos < input.length && /[0-9]/.test(input[pos]!)) pos++;
      tokens.push({ kind: "value", value: Number.parseInt(input.slice(start, pos), 10) });
      continue;
    }
    if (/[A-Za-z_]/.test(ch)) {
      const start = pos;
      while (pos < input.length && /[A-Za-z0-9_]/.test(input[pos]!)) pos++;
      const raw = input.slice(start, pos);
      if (raw === "true") tokens.push({ kind: "value", value: true });
      else if (raw === "false") tokens.push({ kind: "value", value: false });
      else if (raw === "null") tokens.push({ kind: "value", value: null });
      else {
        const value = lookup(bindings, raw);
        if (value === undefined) throw new Error(`unsupported identifier ${raw}`);
        tokens.push({ kind: "value", value });
      }
      continue;
    }
    if (ch === "(") {
      tokens.push({ kind: "lparen" });
      pos++;
      continue;
    }
    if (ch === ")") {
      tokens.push({ kind: "rparen" });
      pos++;
      continue;
    }
    const two = input.slice(pos, pos + 2);
    if (["==", "!=", "<=", ">=", "&&", "||"].includes(two)) {
      tokens.push({ kind: "op", op: two });
      pos += 2;
      continue;
    }
    if ("+-*/%<>!".includes(ch)) {
      tokens.push({ kind: "op", op: ch });
      pos++;
      continue;
    }
    throw new Error(`unexpected character ${JSON.stringify(ch)} in ${input}`);
  }
  return tokens;
}

class ExprParser {
  pos = 0;

  constructor(private readonly tokens: ExprToken[]) {}

  parse(): JsonValue {
    const value = this.parseOr();
    if (this.pos !== this.tokens.length) {
      throw new Error(`unexpected token at ${this.pos}`);
    }
    return value;
  }

  private takeOp(op: string): boolean {
    const token = this.tokens[this.pos];
    if (token?.kind === "op" && token.op === op) {
      this.pos++;
      return true;
    }
    return false;
  }

  private parseOr(): JsonValue {
    let left = this.parseAnd();
    while (this.takeOp("||")) {
      const right = this.parseAnd();
      left = truthy(left) || truthy(right);
    }
    return left;
  }

  private parseAnd(): JsonValue {
    let left = this.parseCompare();
    while (this.takeOp("&&")) {
      const right = this.parseCompare();
      left = truthy(left) && truthy(right);
    }
    return left;
  }

  private parseCompare(): JsonValue {
    let left = this.parseAdd();
    while (this.pos < this.tokens.length) {
      const token = this.tokens[this.pos];
      if (
        token?.kind !== "op" ||
        !["==", "!=", "<", "<=", ">", ">="].includes(token.op)
      ) {
        break;
      }
      this.pos++;
      const right = this.parseAdd();
      left = applyCompare(token.op, left, right);
    }
    return left;
  }

  private parseAdd(): JsonValue {
    let left = this.parseMul();
    for (;;) {
      if (this.takeOp("+")) left = applyNumeric("+", left, this.parseMul());
      else if (this.takeOp("-")) left = applyNumeric("-", left, this.parseMul());
      else return left;
    }
  }

  private parseMul(): JsonValue {
    let left = this.parseUnary();
    for (;;) {
      if (this.takeOp("*")) left = applyNumeric("*", left, this.parseUnary());
      else if (this.takeOp("/")) left = applyNumeric("/", left, this.parseUnary());
      else if (this.takeOp("%")) left = applyNumeric("%", left, this.parseUnary());
      else return left;
    }
  }

  private parseUnary(): JsonValue {
    if (this.takeOp("-")) return -expectNumber(this.parseUnary(), "unary -");
    if (this.takeOp("!")) return !truthy(this.parseUnary());
    return this.parsePrimary();
  }

  private parsePrimary(): JsonValue {
    const token = this.tokens[this.pos];
    if (token === undefined) throw new Error("unexpected end of expression");
    this.pos++;
    if (token.kind === "value") return token.value;
    if (token.kind === "lparen") {
      const value = this.parseOr();
      if (this.tokens[this.pos]?.kind !== "rparen") {
        throw new Error("missing closing parenthesis");
      }
      this.pos++;
      return value;
    }
    throw new Error(`unexpected token at ${this.pos - 1}`);
  }
}

function truthy(value: JsonValue): boolean {
  if (value === null) return false;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return value !== "";
  if (Array.isArray(value)) return value.length > 0;
  return Object.keys(value).length > 0;
}

function applyNumeric(op: string, left: JsonValue, right: JsonValue): number {
  const a = expectNumber(left, op);
  const b = expectNumber(right, op);
  switch (op) {
    case "+":
      return a + b;
    case "-":
      return a - b;
    case "*":
      return a * b;
    case "/":
      if (b === 0) throw new Error("division by zero");
      return Math.trunc(a / b);
    case "%":
      if (b === 0) throw new Error("modulo by zero");
      return a % b;
    default:
      throw new Error(`unknown numeric op ${op}`);
  }
}

function applyCompare(op: string, left: JsonValue, right: JsonValue): boolean {
  if (op === "==") return stableEqual(left, right);
  if (op === "!=") return !stableEqual(left, right);
  const a = expectNumber(left, op);
  const b = expectNumber(right, op);
  if (op === "<") return a < b;
  if (op === "<=") return a <= b;
  if (op === ">") return a > b;
  if (op === ">=") return a >= b;
  throw new Error(`unknown compare op ${op}`);
}

function stableEqual(left: JsonValue, right: JsonValue): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function evalExpression(form: string, bindings: Bindings): JsonValue {
  return new ExprParser(tokenizeExpr(form, bindings)).parse();
}

function evalForm(state: QuestionState, form: string): JsonValue {
  return evalFormIn(state, form, [{}]);
}

function evalIf(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const rest = form.trim().slice("if ".length).trim();
  const thenPos = findTopLevelKeyword(rest, " then ");
  if (thenPos < 0) throw new Error(`if expression missing then: ${form}`);
  const condSrc = rest.slice(0, thenPos).trim();
  const afterThen = rest.slice(thenPos + " then ".length);
  const elsePos = findTopLevelKeyword(afterThen, " else ");
  const thenSrc =
    elsePos >= 0 ? afterThen.slice(0, elsePos).trim() : afterThen.trim();
  const elseSrc =
    elsePos >= 0 ? afterThen.slice(elsePos + " else ".length).trim() : "";
  return truthy(evalFormIn(state, condSrc, bindings))
    ? evalFormIn(state, thenSrc, bindings)
    : elseSrc === ""
      ? null
      : evalFormIn(state, elseSrc, bindings);
}

function evalDo(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const body = form.trim().slice("do".length).trim();
  if (!body.startsWith("{") || !body.endsWith("}")) {
    throw new Error(`invalid do block ${form}`);
  }
  return evalStatements(state, body.slice(1, -1), [...bindings, {}]);
}

function evalLet(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const rest = form.trim().slice("let ".length).trim();
  const parts = splitTopLevel(rest, "=");
  if (parts.length !== 2) throw new Error(`let expression missing '=': ${form}`);
  const name = parts[0]!.trim();
  if (!isIdent(name)) throw new Error(`invalid let binding name ${name}`);
  const value = evalFormIn(state, parts[1]!.trim(), bindings);
  bindings[bindings.length - 1]![name] = value;
  return value;
}

function evalSet(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const rest = form.trim().slice("set ".length).trim();
  const parts = splitTopLevel(rest, "=");
  if (parts.length !== 2) throw new Error(`set expression missing '=': ${form}`);
  const name = parts[0]!.trim();
  if (!isIdent(name)) throw new Error(`invalid set binding name ${name}`);
  return assign(bindings, name, evalFormIn(state, parts[1]!.trim(), bindings));
}

function evalArray(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue[] {
  const text = form.trim();
  if (text === "[]") return [];
  if (!text.startsWith("[") || !text.endsWith("]")) {
    throw new Error(`invalid list ${form}`);
  }
  return splitArgs(text.slice(1, -1)).map((item) =>
    evalFormIn(state, item, bindings),
  );
}

function evalStatements(
  state: QuestionState,
  body: string,
  bindings: Bindings,
): JsonValue {
  let value: JsonValue = null;
  for (const stmt of splitTopLevel(body, ";")) {
    value = evalFormIn(state, stmt, bindings);
  }
  return value;
}

function evalFor(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const rest = form.trim().slice("for ".length).trim();
  const inPos = findTopLevelKeyword(rest, " in ");
  if (inPos < 0) throw new Error(`for expression missing in: ${form}`);
  const varName = rest.slice(0, inPos).trim();
  if (!isIdent(varName)) throw new Error(`invalid for binding name ${varName}`);
  const [iterSrc, bodySrc] = splitHeadBody(rest.slice(inPos + " in ".length));
  const iterable = evalFormIn(state, iterSrc, bindings);
  const items = Array.isArray(iterable)
    ? iterable
    : typeof iterable === "string"
      ? Array.from(iterable)
      : null;
  if (items === null) {
    throw new Error(`for expects a list or string`);
  }
  const results: JsonValue[] = [];
  for (const item of items) {
    const local = [...bindings, { [varName]: item }];
    results.push(evalStatements(state, bodySrc, local));
  }
  return results;
}

function evalWhile(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const [condSrc, bodySrc] = splitHeadBody(form.trim().slice("while ".length));
  let result: JsonValue = null;
  const maxIterations = 10_000;
  for (let iterations = 0; ; iterations++) {
    if (!truthy(evalFormIn(state, condSrc, bindings))) return result;
    result = evalStatements(state, bodySrc, bindings);
    if (iterations >= maxIterations) {
      throw new Error(`while loop exceeded ${maxIterations} iterations`);
    }
  }
}

function evalFormIn(
  state: QuestionState,
  form: string,
  bindings: Bindings,
): JsonValue {
  const trimmed = form.trim();
  if (trimmed.startsWith("if ")) return evalIf(state, trimmed, bindings);
  if (trimmed.startsWith("do")) return evalDo(state, trimmed, bindings);
  if (trimmed.startsWith("let ")) return evalLet(state, trimmed, bindings);
  if (trimmed.startsWith("set ")) return evalSet(state, trimmed, bindings);
  if (trimmed.startsWith("for ")) return evalFor(state, trimmed, bindings);
  if (trimmed.startsWith("while ")) return evalWhile(state, trimmed, bindings);

  if (trimmed.startsWith("ask(")) {
    const args = splitArgs(callBody(trimmed, "ask"));
    if (args.length < 2 || args.length > 4) {
      throw new Error(`ask expects 2 to 4 args, got ${args.length}`);
    }
    const rawChoices = args[2] === undefined ? [] : parseArray(args[2]);
    const choices = rawChoices.map((choice) => {
      if (typeof choice !== "string") throw new Error("ask choices must be strings");
      return choice;
    });
    const context =
      args[3] === undefined ? {} : (parseObject(args[3]) as Record<string, JsonValue>);
    return state.createQuestion(parseString(args[0]!), parseString(args[1]!), choices, context);
  }

  if (trimmed.startsWith("await_answer(")) {
    const args = splitArgs(callBody(trimmed, "await_answer"));
    if (args.length !== 1) {
      throw new Error(`await_answer expects 1 arg, got ${args.length}`);
    }
    return state.awaitAnswer(parseString(args[0]!));
  }

  const call = callParts(trimmed);
  if (call !== null) {
    const [name, rawArgs] = call;
    return evalBuiltin(
      name,
      rawArgs.map((arg) => evalFormIn(state, arg, bindings)),
    );
  }
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    return evalArray(state, trimmed, bindings);
  }
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    return parseObject(trimmed);
  }
  return evalExpression(trimmed, bindings);
}

function runCase(rawCase: Record<string, unknown>): Record<string, unknown> {
  const state = new QuestionState();
  let questionId = "";
  const setup = rawCase.setup;
  if (setup !== null && typeof setup === "object" && !Array.isArray(setup)) {
    const setupRecord = setup as Record<string, unknown>;
    if (typeof setupRecord.open_question_form === "string") {
      const opened = evalForm(state, setupRecord.open_question_form);
      if (opened === null || typeof opened !== "object" || Array.isArray(opened)) {
        throw new Error("open_question_form did not return a question object");
      }
      questionId = String((opened as Record<string, JsonValue>).id);
      if (typeof setupRecord.answer === "string") {
        const answeredBy =
          typeof setupRecord.answered_by === "string"
            ? setupRecord.answered_by
            : "conformance";
        state.answerQuestion(questionId, setupRecord.answer, answeredBy);
      }
    }
  }
  const rawForm = rawCase.form;
  if (typeof rawForm !== "string") throw new Error("case form must be a string");
  const value = evalForm(state, rawForm.replaceAll("${question_id}", questionId));
  if (questionId === "" && value !== null && typeof value === "object" && !Array.isArray(value)) {
    const id = (value as Record<string, JsonValue>).id;
    questionId = typeof id === "string" ? id : "";
  }
  return {
    name: rawCase.name,
    question_id: questionId,
    value,
    events: state.events,
  };
}

function main(): void {
  const vectorPath = process.argv[2];
  if (vectorPath === undefined) {
    console.error("usage: conformance.ts <vector.json>");
    process.exit(2);
  }
  const vector = JSON.parse(readFileSync(vectorPath, "utf8")) as Record<string, unknown>;
  const rawCases = vector.cases;
  if (!Array.isArray(rawCases)) throw new Error("vector cases must be a list");
  const payload = {
    kernel: "typescript",
    status: "pass",
    cases: rawCases.map((rawCase) => runCase(rawCase as Record<string, unknown>)),
  };
  console.log(JSON.stringify(payload, null, 2));
}

main();
