// field.ts — Field Model Form (FMF) vertical slice.
//
// FMF generalizes BMF from a linear character stream to typed fields of
// cells. The execution contract is logical simultaneity on a bounded engine:
// freeze one snapshot, match rules against that snapshot, price and choose
// candidates, emit candidate deltas, resolve conflicts, commit atomically,
// and record a transparent receipt plus residual.

import {
  Kernel,
  Level,
  RBasic,
  nodeKey,
  type NodeID,
} from "./kernel.ts";

export type CarrierKind =
  | "sequence"
  | "graph"
  | "mesh"
  | "cell-graph"
  | "attention-graph";

export type FieldScalar = string | number | boolean | null;

export interface FieldSite {
  readonly id: string;
  readonly fiber: Record<string, FieldScalar>;
}

export interface FieldEdge {
  readonly from: string;
  readonly to: string;
  readonly kind: string;
  readonly fiber?: Record<string, FieldScalar>;
}

export interface FieldTrace {
  readonly rule: string;
  readonly kind: string;
  readonly bindings: Record<string, FieldScalar>;
  readonly data?: Record<string, FieldScalar>;
}

export interface FieldState {
  sites: FieldSite[];
  edges: FieldEdge[];
  traces: FieldTrace[];
  time: number;
}

export interface FieldBlueprint {
  readonly nodeID: NodeID;
  readonly name: string;
  readonly carrier: CarrierKind;
  readonly topology: string;
  readonly fiber: Record<string, string>;
  readonly units: Record<string, string>;
  readonly boundary: string;
}

export interface FieldCell {
  readonly nodeID: NodeID;
  readonly name: string;
  readonly blueprint: FieldBlueprint;
  readonly state: FieldState;
}

export interface CostLedger {
  readonly attention: number;
  readonly compute: number;
  readonly disturbance: number;
  readonly risk: number;
}

export interface FieldMatch {
  readonly bindings: Record<string, FieldScalar>;
  readonly cost?: Partial<CostLedger>;
}

export type FieldDelta =
  | {
      readonly op: "set-site";
      readonly site: string;
      readonly key: string;
      readonly value: FieldScalar;
    }
  | {
      readonly op: "inc-site";
      readonly site: string;
      readonly key: string;
      readonly value: number;
    }
  | {
      readonly op: "set-edge";
      readonly edge: number;
      readonly key: string;
      readonly value: FieldScalar;
    }
  | {
      readonly op: "inc-edge";
      readonly edge: number;
      readonly key: string;
      readonly value: number;
    }
  | {
      readonly op: "trace";
      readonly trace: FieldTrace;
    };

export interface AppliedDelta {
  readonly delta: FieldDelta;
  readonly previous?: FieldScalar;
  readonly previousTraceCount?: number;
}

export interface FieldRule {
  readonly name: string;
  readonly nodeID: NodeID;
  readonly evidence: "observed" | "inferred" | "simulated" | "validated" | "hypothesis";
  readonly consent: "read-only" | "observe" | "intervene";
  readonly baseCost: CostLedger;
  readonly match: (snapshot: FieldState) => readonly FieldMatch[];
  readonly forward: (match: FieldMatch, snapshot: FieldState) => readonly FieldDelta[];
}

export interface Candidate {
  readonly nodeID: NodeID;
  readonly rule: FieldRule;
  readonly match: FieldMatch;
  readonly cost: CostLedger;
}

export interface FieldBudget {
  readonly maxMatches: number;
  readonly maxDeltas: number;
}

export interface FieldObserver {
  readonly name: string;
  readonly policy: "all-compatible" | "least-disturbance";
}

export interface FieldReceipt {
  readonly nodeID: NodeID;
  readonly observer: FieldObserver;
  readonly candidates: readonly Candidate[];
  readonly selected: readonly Candidate[];
  readonly applied: readonly AppliedDelta[];
  readonly conflicts: readonly string[];
}

export interface FieldResidual {
  readonly nodeID: NodeID;
  readonly budgetExhausted: boolean;
  readonly skippedCandidates: number;
  readonly conflicts: readonly string[];
  readonly projectionLoss?: string;
}

export interface FieldStepResult {
  readonly field: FieldCell;
  readonly receipt: FieldReceipt;
  readonly residual: FieldResidual;
}

const DEFAULT_COST: CostLedger = {
  attention: 1,
  compute: 1,
  disturbance: 0,
  risk: 0,
};

function cat(type: number, inst: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type, inst };
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${JSON.stringify(k)}:${stableJson(v)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

function cloneState(state: FieldState): FieldState {
  return JSON.parse(JSON.stringify(state)) as FieldState;
}

function jsonNode(k: Kernel, value: unknown): NodeID {
  return k.internString(stableJson(value));
}

function mergeCost(base: CostLedger, extra?: Partial<CostLedger>): CostLedger {
  return {
    attention: extra?.attention ?? base.attention,
    compute: extra?.compute ?? base.compute,
    disturbance: extra?.disturbance ?? base.disturbance,
    risk: extra?.risk ?? base.risk,
  };
}

function costScore(c: CostLedger): number {
  return c.disturbance * 1000 + c.risk * 100 + c.attention * 10 + c.compute;
}

export function makeFieldBlueprint(
  k: Kernel,
  name: string,
  carrier: CarrierKind,
  topology: string,
  fiber: Record<string, string>,
  units: Record<string, string> = {},
  boundary = "open",
): FieldBlueprint {
  const nodeID = k.intern(cat(RBasic.FIELD, 1), [
    k.internString(name),
    k.intern(cat(RBasic.CARRIER, 1), [k.internString(carrier)]),
    k.intern(cat(RBasic.TOPOLOGY, 1), [k.internString(topology)]),
    k.intern(cat(RBasic.FIBER, 1), [jsonNode(k, fiber)]),
    jsonNode(k, units),
    k.intern(cat(RBasic.BOUNDARY, 1), [k.internString(boundary)]),
  ]);
  return { nodeID, name, carrier, topology, fiber, units, boundary };
}

export function makeFieldCell(
  k: Kernel,
  name: string,
  blueprint: FieldBlueprint,
  state: FieldState,
): FieldCell {
  const normalized = normalizeState(state);
  const nodeID = k.intern(cat(RBasic.FIELD, 2), [
    blueprint.nodeID,
    k.intern(cat(RBasic.REGION, 1), [jsonNode(k, normalized)]),
  ]);
  return { nodeID, name, blueprint, state: normalized };
}

function normalizeState(state: FieldState): FieldState {
  return {
    time: state.time,
    sites: state.sites.map((site) => ({
      id: site.id,
      fiber: { ...site.fiber },
    })),
    edges: state.edges.map((edge) => ({
      from: edge.from,
      to: edge.to,
      kind: edge.kind,
      fiber: { ...(edge.fiber ?? {}) },
    })),
    traces: state.traces.map((trace) => ({
      rule: trace.rule,
      kind: trace.kind,
      bindings: { ...trace.bindings },
      data: trace.data ? { ...trace.data } : undefined,
    })),
  };
}

export function makeFieldRule(
  k: Kernel,
  name: string,
  kind: string,
  match: FieldRule["match"],
  forward: FieldRule["forward"],
  options: {
    readonly evidence?: FieldRule["evidence"];
    readonly consent?: FieldRule["consent"];
    readonly cost?: Partial<CostLedger>;
  } = {},
): FieldRule {
  const nodeID = k.intern(cat(RBasic.MATCH_FIELD, 1), [
    k.internString(name),
    k.internString(kind),
    k.intern(cat(RBasic.EVIDENCE, 1), [
      k.internString(options.evidence ?? "simulated"),
    ]),
    k.intern(cat(RBasic.CONSENT, 1), [
      k.internString(options.consent ?? "observe"),
    ]),
  ]);
  return {
    name,
    nodeID,
    evidence: options.evidence ?? "simulated",
    consent: options.consent ?? "observe",
    baseCost: mergeCost(DEFAULT_COST, options.cost),
    match,
    forward,
  };
}

export function liftSequenceToField(
  k: Kernel,
  name: string,
  blueprint: FieldBlueprint,
  text: string,
  slot = "symbol",
): FieldCell {
  const sites: FieldSite[] = [...text].map((symbol, index) => ({
    id: `p${index}`,
    fiber: { index, [slot]: symbol },
  }));
  const edges: FieldEdge[] = [];
  for (let i = 0; i < sites.length - 1; i++) {
    edges.push({ from: `p${i}`, to: `p${i + 1}`, kind: "next" });
  }
  return makeFieldCell(k, name, blueprint, {
    sites,
    edges,
    traces: [],
    time: 0,
  });
}

export function projectSequence(field: FieldCell, slot = "symbol"): string {
  return field.state.sites
    .slice()
    .sort((a, b) => Number(a.fiber.index) - Number(b.fiber.index))
    .map((site) => String(site.fiber[slot] ?? ""))
    .join("");
}

export function liftGraphToField(
  k: Kernel,
  name: string,
  blueprint: FieldBlueprint,
  sites: readonly FieldSite[],
  edges: readonly FieldEdge[],
): FieldCell {
  return makeFieldCell(k, name, blueprint, {
    sites: sites.map((site) => ({ id: site.id, fiber: { ...site.fiber } })),
    edges: edges.map((edge) => ({
      from: edge.from,
      to: edge.to,
      kind: edge.kind,
      fiber: { ...(edge.fiber ?? {}) },
    })),
    traces: [],
    time: 0,
  });
}

export function projectGraph(field: FieldCell): {
  readonly sites: readonly FieldSite[];
  readonly edges: readonly FieldEdge[];
} {
  return {
    sites: field.state.sites.map((site) => ({
      id: site.id,
      fiber: { ...site.fiber },
    })),
    edges: field.state.edges.map((edge) => ({
      from: edge.from,
      to: edge.to,
      kind: edge.kind,
      fiber: { ...(edge.fiber ?? {}) },
    })),
  };
}

export function makeSequenceWindowRule(
  k: Kernel,
  name: string,
  motif: string,
  slot = "symbol",
): FieldRule {
  return makeFieldRule(
    k,
    name,
    "sequence-window",
    (snapshot) => {
      const ordered = snapshot.sites
        .slice()
        .sort((a, b) => Number(a.fiber.index) - Number(b.fiber.index));
      const out: FieldMatch[] = [];
      for (let start = 0; start <= ordered.length - motif.length; start++) {
        const text = ordered
          .slice(start, start + motif.length)
          .map((site) => String(site.fiber[slot] ?? ""))
          .join("");
        if (text === motif) {
          out.push({
            bindings: {
              start,
              motif,
              positions: ordered
                .slice(start, start + motif.length)
                .map((site) => site.id)
                .join(","),
            },
            cost: { attention: 1, compute: motif.length },
          });
        }
      }
      return out;
    },
    (match) => [
      {
        op: "trace",
        trace: {
          rule: name,
          kind: "sequence-window",
          bindings: match.bindings,
        },
      },
    ],
    { evidence: "observed", consent: "observe" },
  );
}

export function makeOhmCurrentRule(k: Kernel): FieldRule {
  return makeFieldRule(
    k,
    "ohm-current",
    "edge-law",
    (snapshot) => {
      const out: FieldMatch[] = [];
      snapshot.edges.forEach((edge, edgeIndex) => {
        const resistance = Number(edge.fiber?.resistance_ohm);
        if (!Number.isFinite(resistance) || resistance === 0) return;
        const from = snapshot.sites.find((site) => site.id === edge.from);
        const to = snapshot.sites.find((site) => site.id === edge.to);
        if (!from || !to) return;
        const vFrom = Number(from.fiber.voltage_V);
        const vTo = Number(to.fiber.voltage_V);
        if (!Number.isFinite(vFrom) || !Number.isFinite(vTo)) return;
        out.push({
          bindings: {
            edge: edgeIndex,
            from: edge.from,
            to: edge.to,
            voltage_delta_V: vFrom - vTo,
            resistance_ohm: resistance,
          },
          cost: { compute: 1, disturbance: 0 },
        });
      });
      return out;
    },
    (match) => {
      const edge = Number(match.bindings.edge);
      const current =
        Number(match.bindings.voltage_delta_V) /
        Number(match.bindings.resistance_ohm);
      return [
        { op: "set-edge", edge, key: "current_A", value: current },
        {
          op: "trace",
          trace: {
            rule: "ohm-current",
            kind: "field-law",
            bindings: match.bindings,
            data: { current_A: current },
          },
        },
      ];
    },
    { evidence: "validated", consent: "observe" },
  );
}

export function makeBindingRule(
  k: Kernel,
  name: string,
  ligandSlot: string,
  receptorSlot: string,
): FieldRule {
  return makeFieldRule(
    k,
    name,
    "site-binding",
    (snapshot) => {
      const out: FieldMatch[] = [];
      snapshot.edges.forEach((edge, edgeIndex) => {
        if (edge.kind !== "contact") return;
        const a = snapshot.sites.find((site) => site.id === edge.from);
        const b = snapshot.sites.find((site) => site.id === edge.to);
        if (!a || !b) return;
        if (a.fiber[ligandSlot] === true && b.fiber[receptorSlot] === true) {
          out.push({
            bindings: { edge: edgeIndex, ligand: a.id, receptor: b.id },
          });
        }
        if (b.fiber[ligandSlot] === true && a.fiber[receptorSlot] === true) {
          out.push({
            bindings: { edge: edgeIndex, ligand: b.id, receptor: a.id },
          });
        }
      });
      return out;
    },
    (match) => [
      { op: "set-site", site: String(match.bindings.ligand), key: "bound", value: true },
      { op: "set-site", site: String(match.bindings.receptor), key: "bound", value: true },
      {
        op: "trace",
        trace: { rule: name, kind: "binding", bindings: match.bindings },
      },
    ],
    { evidence: "observed", consent: "observe", cost: { disturbance: 1 } },
  );
}

export function makeDiffusionRule(
  k: Kernel,
  name: string,
  slot: string,
  edgeKind: string,
  coefficient: number,
): FieldRule {
  return makeFieldRule(
    k,
    name,
    "diffusion",
    (snapshot) => {
      const out: FieldMatch[] = [];
      snapshot.edges.forEach((edge, edgeIndex) => {
        if (edge.kind !== edgeKind) return;
        const from = snapshot.sites.find((site) => site.id === edge.from);
        const to = snapshot.sites.find((site) => site.id === edge.to);
        if (!from || !to) return;
        const a = Number(from.fiber[slot] ?? 0);
        const b = Number(to.fiber[slot] ?? 0);
        if (a <= b) return;
        out.push({
          bindings: {
            edge: edgeIndex,
            from: from.id,
            to: to.id,
            amount: (a - b) * coefficient,
          },
          cost: { compute: 1, disturbance: 1 },
        });
      });
      return out;
    },
    (match) => {
      const amount = Number(match.bindings.amount);
      return [
        {
          op: "inc-site",
          site: String(match.bindings.from),
          key: slot,
          value: -amount,
        },
        {
          op: "inc-site",
          site: String(match.bindings.to),
          key: slot,
          value: amount,
        },
        {
          op: "trace",
          trace: { rule: name, kind: "diffusion", bindings: match.bindings },
        },
      ];
    },
    { evidence: "simulated", consent: "observe", cost: { disturbance: 1 } },
  );
}

export function fieldStep(
  k: Kernel,
  field: FieldCell,
  rules: readonly FieldRule[],
  observer: FieldObserver,
  budget: FieldBudget = { maxMatches: 1024, maxDeltas: 4096 },
): FieldStepResult {
  const snapshot = cloneState(field.state);
  const candidates: Candidate[] = [];
  let skippedCandidates = 0;
  let budgetExhausted = false;

  for (const rule of rules) {
    const matches = rule.match(snapshot);
    for (const match of matches) {
      if (candidates.length >= budget.maxMatches) {
        budgetExhausted = true;
        skippedCandidates++;
        continue;
      }
      const cost = mergeCost(rule.baseCost, match.cost);
      candidates.push({
        nodeID: k.intern(cat(RBasic.CHOICE, 1), [
          rule.nodeID,
          jsonNode(k, match.bindings),
          jsonNode(k, cost),
        ]),
        rule,
        match,
        cost,
      });
    }
  }

  const selected =
    observer.policy === "least-disturbance"
      ? candidates.slice().sort((a, b) => costScore(a.cost) - costScore(b.cost)).slice(0, 1)
      : candidates;

  const rawDeltas = selected.flatMap((candidate) =>
    candidate.rule.forward(candidate.match, snapshot),
  );
  if (rawDeltas.length > budget.maxDeltas) {
    budgetExhausted = true;
  }
  const limitedDeltas = rawDeltas.slice(0, budget.maxDeltas);
  const { applied, state, conflicts } = applyDeltas(snapshot, limitedDeltas);
  const nextField = makeFieldCell(k, field.name, field.blueprint, {
    ...state,
    time: field.state.time + 1,
  });

  const receiptNode = k.intern(cat(RBasic.RECEIPT, 1), [
    k.internString(observer.name),
    jsonNode(k, candidates.map((c) => c.rule.name)),
    jsonNode(k, selected.map((c) => c.rule.name)),
    jsonNode(k, applied.map((a) => a.delta)),
    jsonNode(k, conflicts),
  ]);
  const residualNode = k.intern(cat(RBasic.RESIDUAL, 1), [
    jsonNode(k, { budgetExhausted, skippedCandidates, conflicts }),
  ]);

  return {
    field: nextField,
    receipt: {
      nodeID: receiptNode,
      observer,
      candidates,
      selected,
      applied,
      conflicts,
    },
    residual: {
      nodeID: residualNode,
      budgetExhausted,
      skippedCandidates,
      conflicts,
    },
  };
}

function applyDeltas(
  snapshot: FieldState,
  deltas: readonly FieldDelta[],
): {
  readonly state: FieldState;
  readonly applied: readonly AppliedDelta[];
  readonly conflicts: readonly string[];
} {
  const state = cloneState(snapshot);
  const applied: AppliedDelta[] = [];
  const conflicts: string[] = [];
  const writeTargets = new Map<string, FieldScalar>();

  for (const delta of deltas) {
    if (delta.op === "trace") {
      const previousTraceCount = state.traces.length;
      state.traces = [...state.traces, delta.trace];
      applied.push({ delta, previousTraceCount });
      continue;
    }

    const targetKey =
      delta.op === "set-site" || delta.op === "inc-site"
        ? `site:${delta.site}:${delta.key}`
        : `edge:${delta.edge}:${delta.key}`;
    if ((delta.op === "set-site" || delta.op === "set-edge") && writeTargets.has(targetKey)) {
      const old = writeTargets.get(targetKey);
      if (old !== delta.value) {
        conflicts.push(`conflict:${targetKey}`);
        continue;
      }
    }

    if (delta.op === "set-site" || delta.op === "inc-site") {
      const site = state.sites.find((candidate) => candidate.id === delta.site);
      if (!site) {
        conflicts.push(`missing-site:${delta.site}`);
        continue;
      }
      const previous = site.fiber[delta.key];
      const next =
        delta.op === "inc-site" ? Number(previous ?? 0) + delta.value : delta.value;
      site.fiber[delta.key] = next;
      writeTargets.set(targetKey, next);
      applied.push({ delta, previous });
      continue;
    }

    const edge = state.edges[delta.edge];
    if (!edge) {
      conflicts.push(`missing-edge:${delta.edge}`);
      continue;
    }
    const mutableFiber = { ...(edge.fiber ?? {}) };
    const previous = mutableFiber[delta.key];
    const next =
      delta.op === "inc-edge" ? Number(previous ?? 0) + delta.value : delta.value;
    mutableFiber[delta.key] = next;
    state.edges[delta.edge] = { ...edge, fiber: mutableFiber };
    writeTargets.set(targetKey, next);
    applied.push({ delta, previous });
  }

  return { state, applied, conflicts };
}

export function intervene(
  k: Kernel,
  field: FieldCell,
  observer: FieldObserver,
  deltas: readonly FieldDelta[],
  consent: "read-only" | "observe" | "intervene" = "intervene",
): FieldStepResult {
  if (consent !== "intervene") {
    throw new Error(`intervene: consent=${consent} does not allow field writes`);
  }
  const rule = makeFieldRule(
    k,
    "observer-intervention",
    "intervention",
    () => [{ bindings: { observer: observer.name } }],
    () => deltas,
    { evidence: "observed", consent: "intervene", cost: { disturbance: 1, risk: 1 } },
  );
  return fieldStep(k, field, [rule], observer, {
    maxMatches: 1,
    maxDeltas: Math.max(1, deltas.length),
  });
}

export function reverseReceipt(
  k: Kernel,
  result: FieldStepResult,
): FieldStepResult {
  const state = cloneState(result.field.state);
  const reverseDeltas: FieldDelta[] = [];

  for (const applied of result.receipt.applied.slice().reverse()) {
    const delta = applied.delta;
    if (delta.op === "trace") {
      const count = applied.previousTraceCount ?? state.traces.length;
      state.traces = state.traces.slice(0, count);
      reverseDeltas.push({
        op: "trace",
        trace: {
          rule: "reverse-receipt",
          kind: "undo-trace",
          bindings: { original_rule: delta.trace.rule },
        },
      });
      continue;
    }
    if (delta.op === "set-site" || delta.op === "inc-site") {
      const site = state.sites.find((candidate) => candidate.id === delta.site);
      if (site) {
        site.fiber[delta.key] = applied.previous ?? null;
        reverseDeltas.push({
          op: "set-site",
          site: delta.site,
          key: delta.key,
          value: applied.previous ?? null,
        });
      }
      continue;
    }
    const edge = state.edges[delta.edge];
    if (edge) {
      const fiber = { ...(edge.fiber ?? {}) };
      fiber[delta.key] = applied.previous ?? null;
      state.edges[delta.edge] = { ...edge, fiber };
      reverseDeltas.push({
        op: "set-edge",
        edge: delta.edge,
        key: delta.key,
        value: applied.previous ?? null,
      });
    }
  }

  const field = makeFieldCell(k, result.field.name, result.field.blueprint, {
    ...state,
    time: result.field.state.time + 1,
  });
  const receiptNode = k.intern(cat(RBasic.RECEIPT, 2), [
    result.receipt.nodeID,
    jsonNode(k, reverseDeltas),
  ]);
  const residualNode = k.intern(cat(RBasic.RESIDUAL, 2), [jsonNode(k, {})]);
  return {
    field,
    receipt: {
      nodeID: receiptNode,
      observer: result.receipt.observer,
      candidates: [],
      selected: [],
      applied: [],
      conflicts: [],
    },
    residual: {
      nodeID: residualNode,
      budgetExhausted: false,
      skippedCandidates: 0,
      conflicts: [],
    },
  };
}

export function fieldNodeSummary(k: Kernel, node: NodeID): string {
  const category = k.category(node);
  return `${nodeKey(node)} category=${nodeKey(category)}`;
}
