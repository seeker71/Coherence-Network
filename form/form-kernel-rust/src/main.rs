// form-kernel-rust — vertical-slice host for Form-on-top.
//
// Executes Form recipe trees and binary artifacts. The CLI still carries a
// source-to-recipe adapter for current tests; the kernel path is the
// substrate, walker, host primitives, and binary artifact loader.
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — all 22 RBasic dispatch arms
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, I/O, conversion
//   • Binary loader      — Form artifact bytes → recipe tree
//
// Parsers and grammars belong in Form artifacts above this layer.
//
// Usage:  form-kernel-rust <file.fk>
//         form-kernel-rust --bench
//         form-kernel-rust --expr "(add 2 3)"

use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::{Read, Seek, SeekFrom};
use std::sync::Arc;
use std::time::Instant;

mod formats;
mod inductive;
mod quotient;

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// Registered substrate ids use pkg=1. Runtime-interned composites use pkg=0
// so temporary recipe ids cannot collide with registered/basic categories
// across an execution context boundary.
#[derive(Copy, Clone, PartialEq, Eq, Hash, Debug)]
pub(crate) struct NodeID {
    pub(crate) pkg: u32,
    pub(crate) level: u32,
    pub(crate) ty: u32,
    pub(crate) inst: u32,
}

pub(crate) const LEVEL_TRIVIAL: u32 = 1;
pub(crate) const LEVEL_BASIC: u32 = 2;

// RBasic — aligned with api/app/services/substrate/category.py
const RB_UNDEFINED: u32 = 0;
const RB_WITNESS: u32 = 6; // substrate self-attestation
const RB_BLOCK: u32 = 9;
const RB_CALL: u32 = 10; // invoke external effect (I/O, tool)
const RB_COND: u32 = 11;
const RB_MATH: u32 = 12;
const RB_COMPARE: u32 = 13;
const RB_LOGIC: u32 = 14;
const RB_ACCESS: u32 = 15; // read a property / field
const RB_METHOD: u32 = 27; // method on a cell-like value
const RB_TRANSMUTE: u32 = 76; // present value through Blueprint without changing identity
                              // Kernel-demo additions
const RB_FNDEF: u32 = 31;
const RB_FNCALL: u32 = 32;
const RB_IDENT: u32 = 33;
const RB_LIST: u32 = 34;

pub(crate) const TRIV_INT: u32 = 1;
pub(crate) const TRIV_STRING: u32 = 2;
const TRIV_BOOL: u32 = 3;
const TRIV_NULL: u32 = 4;

// Per-RBasic instance constants
const RMATH_PLUS: u32 = 1;
const RMATH_MINUS: u32 = 2;
const RMATH_MULTIPLY: u32 = 3;
const RMATH_DIVIDE: u32 = 4;
const RMATH_MODULO: u32 = 5;

const RCMP_EQ: u32 = 1;
const RCMP_NE: u32 = 2;
const RCMP_LT: u32 = 3;
const RCMP_LE: u32 = 4;
const RCMP_GT: u32 = 5;
const RCMP_GE: u32 = 6;

const RLOG_AND: u32 = 1;
const RLOG_OR: u32 = 2;
const RLOG_NOT: u32 = 3;

const RCOND_IF: u32 = 1;
const RCOND_IF_ELSE: u32 = 2;

const RBLK_DO: u32 = 1;
const RBLK_SEQ: u32 = 2;
const RBLK_LET: u32 = 3;
const FORM_KERNEL_STACK_BYTES: usize = 256 * 1024 * 1024;

#[derive(Clone, Debug)]
struct Recipe {
    category: NodeID,
    children: Vec<NodeID>,
}

#[derive(Clone, PartialEq, Eq, Hash)]
struct ShapeKey {
    category: NodeID,
    children: Vec<NodeID>,
}

// NativeFn now takes &mut Kernel + &mut Arena so substrate-write natives
// (intern_node, intern_trivial_*) can grow the substrate, and walk_recipe
// can re-enter the walker. Pure natives ignore the mutable handles. The
// cost: walker's children() must return owned Vec (the Breath 1 slice
// optimization is undone). Future breath: restore via Cow or split tables.
type NativeFn = fn(&mut Kernel, &mut Arena, &[Value]) -> Value;

// EnvAwareNativeFn — natives that need the caller's env (walk_recipe_here).
// Separate registry path to avoid changing the NativeFn signature across
// every existing native.
type EnvAwareNativeFn = fn(&mut Kernel, &mut Arena, FrameId, &[Value]) -> Value;

#[derive(Copy, Clone)]
struct EnvAwareNativeEntry {
    name: NameID,
    category: NodeID,
    func: EnvAwareNativeFn,
}

// NativeEntry — a native's function plus the Form category it expresses.
// Carries Blueprint attribution into the kernel: when the walker dispatches
// through a native, the trace records the category alongside the FNCALL
// arm, so reasoning about which Form-shapes did the work reaches inside
// the host-language layer. UNDEFINED is the honest marker for natives
// whose Form attribution hasn't been settled yet.
#[derive(Copy, Clone)]
struct NativeEntry {
    name: NameID,
    category: NodeID,
    func: NativeFn,
}

// NameID — interned identifier handle. The same u32 used to encode a name
// trivial's NodeID instance is what every runtime name-lookup compares.
// String comparison happens once, at parse time, never in the hot path.
type NameID = u32;

// FrameId — index into kernel.frames. Closures carry these instead of
// Rc<RefCell<Frame>>; lookup walks the chain by integer indirection. The
// arena grows monotonically per session — no freeing, no cycles, no
// reference-count traffic in the hot path.
type FrameId = u32;

// Kernel — the immutable-during-walk substrate: intern table, string
// table, native dispatch. Mutates only at parse/intern time. Held as
// `&Kernel` by the walker so children() can return borrowed slices.
pub(crate) struct Kernel {
    by_shape: HashMap<ShapeKey, NodeID>,
    by_id: HashMap<NodeID, Recipe>,
    // Source attribution side-map: NodeID → (file_name_id, line, col).
    // Populated by `intern_node_at` for Recipes emitted from parser actions
    // that carry source-location context. `node_source` reads back.
    // The satsang-load-bearing surface: every cell's state is traceable
    // back to the source line of the recipe that authored it.
    source_attr: HashMap<NodeID, (NameID, u32, u32)>,
    // walk_cache — JIT-vector memoization: pure recipes (no I/O, no
    // external state) can have their walk result cached by NodeID.
    // Content-addressing means same recipe shape → same NodeID, so
    // cache lookups are O(1) by structure. Real JIT compiles to
    // native code; memoization skips redundant interpretation.
    // For now: opt-in via `walk-cached` native; not used by default
    // `walk_recipe` to avoid invalidating semantics for impure recipes.
    walk_cache: HashMap<NodeID, Value>,
    walk_cache_hits: u64,
    walk_cache_misses: u64,
    import_seq: u32,
    strs: Vec<String>,
    str_idx: HashMap<String, NameID>,
    next_inst: u32,
    natives: HashMap<NameID, NativeEntry>,
    env_natives: HashMap<NameID, EnvAwareNativeEntry>,
    active_roots: Vec<NodeID>,
    // Optional tracing — None for hot-path runs, Some for `trace` subcommand.
    // Hooked at the top of walk() to record per-arm dispatch counts and
    // choice success/failure rates. Per lc-native-kernel-binary's
    // "tracing and observation pattern" — the body's own attestation of
    // which arms are doing the work at any moment.
    pub(crate) trace: Option<Trace>,
}

// Trace — per-(arm, inst) dispatch counters + choice success/failure tracking.
// Held inside Kernel so the walker can record without threading an extra
// reference through every recursive call. Storing (ty, inst) instead of
// just ty surfaces typed-numeric distribution — MATH.PLUS_F64 (inst=0x91)
// becomes distinguishable from MATH.PLUS_I32 (inst=0x01) in the report.
#[derive(Default)]
pub(crate) struct Trace {
    pub(crate) total_walks: u64,
    pub(crate) arm_counts: HashMap<(u32, u32), u64>, // (cat.ty, cat.inst) → count
    pub(crate) fn_counts: HashMap<String, u64>,
    pub(crate) native_counts: HashMap<String, u64>,
    pub(crate) choice_attempts: u64,
    pub(crate) choice_successes: u64,
    pub(crate) choice_failures: u64,
}

impl Trace {
    pub(crate) fn new() -> Self {
        Self::default()
    }

    pub(crate) fn record(&mut self, arm_ty: u32, arm_inst: u32) {
        self.total_walks += 1;
        *self.arm_counts.entry((arm_ty, arm_inst)).or_insert(0) += 1;
    }

    pub(crate) fn record_fn(&mut self, name: &str) {
        *self.fn_counts.entry(name.to_string()).or_insert(0) += 1;
    }

    pub(crate) fn record_native(&mut self, name: &str) {
        *self.native_counts.entry(name.to_string()).or_insert(0) += 1;
    }

    pub(crate) fn record_choice_attempt(&mut self) {
        self.choice_attempts += 1;
    }
    pub(crate) fn record_choice_success(&mut self) {
        self.choice_successes += 1;
    }
    pub(crate) fn record_choice_failure(&mut self) {
        self.choice_failures += 1;
    }

    pub(crate) fn arm_name(arm_ty: u32) -> &'static str {
        match arm_ty {
            RB_BLOCK => "BLOCK",
            RB_COND => "COND",
            RB_MATH => "MATH",
            RB_COMPARE => "COMPARE",
            RB_LOGIC => "LOGIC",
            RB_IDENT => "IDENT",
            RB_FNDEF => "FNDEF",
            RB_FNCALL => "FNCALL",
            RB_LIST => "LIST",
            // Native-Blueprint attribution categories — recorded
            // alongside FNCALL when a native fires.
            RB_WITNESS => "WITNESS",
            RB_CALL => "CALL",
            RB_ACCESS => "ACCESS",
            RB_METHOD => "METHOD",
            RB_TRANSMUTE => "TRANSMUTE",
            _ => "OTHER",
        }
    }

    /// Variant name — readable label for an (arm_ty, arm_inst) pair.
    /// Returns "MATH.PLUS", "COMPARE.LE", "BLOCK.LET", etc. For arms
    /// without a known inst encoding, returns just the bare arm name.
    /// Symmetric with TS / Go variant naming so trace JSONs read the
    /// same way across kernels.
    pub(crate) fn arm_variant_name(arm_ty: u32, arm_inst: u32) -> String {
        let base = Self::arm_name(arm_ty);
        let variant = match arm_ty {
            RB_MATH => match arm_inst {
                RMATH_PLUS => "PLUS",
                RMATH_MINUS => "MINUS",
                RMATH_MULTIPLY => "MUL",
                RMATH_DIVIDE => "DIV",
                RMATH_MODULO => "MOD",
                _ => "",
            },
            RB_COMPARE => match arm_inst {
                RCMP_EQ => "EQ",
                RCMP_NE => "NE",
                RCMP_LT => "LT",
                RCMP_LE => "LE",
                RCMP_GT => "GT",
                RCMP_GE => "GE",
                _ => "",
            },
            RB_LOGIC => match arm_inst {
                RLOG_AND => "AND",
                RLOG_OR => "OR",
                RLOG_NOT => "NOT",
                _ => "",
            },
            RB_COND => match arm_inst {
                RCOND_IF => "IF",
                RCOND_IF_ELSE => "IF_ELSE",
                _ => "",
            },
            RB_BLOCK => match arm_inst {
                RBLK_DO => "DO",
                RBLK_SEQ => "SEQ",
                RBLK_LET => "LET",
                _ => "",
            },
            _ => "",
        };
        if variant.is_empty() {
            base.to_string()
        } else {
            format!("{}.{}", base, variant)
        }
    }

    pub(crate) fn to_json(&self) -> serde_json::Value {
        // Per-(ty, inst) records — preserves typed-numeric distribution.
        let mut variants: Vec<serde_json::Value> = self
            .arm_counts
            .iter()
            .map(|((ty, inst), count)| {
                serde_json::json!({
                    "arm_ty":           ty,
                    "arm_inst":         inst,
                    "arm_name":         Self::arm_name(*ty),
                    "arm_variant_name": Self::arm_variant_name(*ty, *inst),
                    "count":            count,
                })
            })
            .collect();
        variants.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        // Per-ty aggregate — kept for backward compatibility with consumers
        // that want the coarser shape (the previous trace JSON form).
        let mut by_ty: HashMap<u32, u64> = HashMap::new();
        for ((ty, _), count) in &self.arm_counts {
            *by_ty.entry(*ty).or_insert(0) += count;
        }
        let mut arms: Vec<serde_json::Value> = by_ty
            .into_iter()
            .map(|(ty, count)| {
                serde_json::json!({
                    "arm_ty":   ty,
                    "arm_name": Self::arm_name(ty),
                    "count":    count,
                })
            })
            .collect();
        arms.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        let mut functions: Vec<serde_json::Value> = self
            .fn_counts
            .iter()
            .map(|(name, count)| {
                serde_json::json!({
                    "name":  name,
                    "count": count,
                })
            })
            .collect();
        functions.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        let mut natives: Vec<serde_json::Value> = self
            .native_counts
            .iter()
            .map(|(name, count)| {
                serde_json::json!({
                    "name":  name,
                    "count": count,
                })
            })
            .collect();
        natives.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        serde_json::json!({
            "total_walks":       self.total_walks,
            "arms":              arms,        // aggregated by ty (backward-compatible)
            "variants":          variants,    // full (ty, inst) granularity
            "functions":         functions,
            "natives":           natives,
            "choice_attempts":   self.choice_attempts,
            "choice_successes":  self.choice_successes,
            "choice_failures":   self.choice_failures,
            "choice_success_rate": if self.choice_attempts > 0 {
                (self.choice_successes as f64) / (self.choice_attempts as f64)
            } else { 0.0 },
        })
    }
}

// Arena — the mutable-during-walk runtime state. Held as `&mut Arena`
// by the walker; orthogonal to the kernel so reading recipes and
// writing frames don't fight the borrow checker.
struct Arena {
    frames: Vec<Frame>,
}

impl Arena {
    fn new() -> Self {
        Self {
            frames: Vec::with_capacity(256),
        }
    }

    fn new_frame(&mut self, parent: Option<FrameId>) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame {
            parent,
            bindings: Vec::new(),
        });
        id
    }

    // OPT (2026-05-21): allocate a frame with pre-sized bindings vec. Used
    // by the FNCALL hot path where the exact arg count is known. Saves
    // Vec capacity reallocations during arg-binding for recursive workloads
    // (fib at 1973 calls × 1 arg = 1973 reallocations avoided).
    fn new_frame_with_capacity(&mut self, parent: Option<FrameId>, cap: usize) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame {
            parent,
            bindings: Vec::with_capacity(cap),
        });
        id
    }

    fn bind(&mut self, fid: FrameId, name: NameID, v: Value) {
        let f = &mut self.frames[fid as usize];
        for slot in &mut f.bindings {
            if slot.0 == name {
                slot.1 = v;
                return;
            }
        }
        f.bindings.push((name, v));
    }

    fn lookup(&self, fid: FrameId, name: NameID) -> Option<Value> {
        let mut cur = Some(fid);
        while let Some(id) = cur {
            let f = &self.frames[id as usize];
            for slot in &f.bindings {
                if slot.0 == name {
                    return Some(slot.1.clone());
                }
            }
            cur = f.parent;
        }
        None
    }
}

impl Kernel {
    pub(crate) fn new() -> Self {
        let mut k = Self {
            by_shape: HashMap::new(),
            by_id: HashMap::new(),
            source_attr: HashMap::new(),
            walk_cache: HashMap::new(),
            walk_cache_hits: 0,
            walk_cache_misses: 0,
            import_seq: 1,
            strs: Vec::new(),
            str_idx: HashMap::new(),
            next_inst: 1,
            natives: HashMap::new(),
            env_natives: HashMap::new(),
            active_roots: Vec::new(),
            trace: None,
        };
        k.register_natives();
        k
    }

    // intern — content-addressed insertion. Same shape ⇒ same NodeID.
    pub(crate) fn intern(&mut self, category: NodeID, children: Vec<NodeID>) -> NodeID {
        let key = ShapeKey {
            category,
            children: children.clone(),
        };
        if let Some(&nid) = self.by_shape.get(&key) {
            return nid;
        }
        let nid = NodeID {
            pkg: 0,
            level: category.level,
            ty: category.ty,
            inst: self.next_inst,
        };
        self.next_inst += 1;
        self.by_shape.insert(key, nid);
        self.by_id.insert(nid, Recipe { category, children });
        nid
    }

    fn next_import_scope(&mut self) -> u32 {
        let scope = self.import_seq;
        self.import_seq += 1;
        scope
    }

    fn remap_imported_leaf(&mut self, scope: u32, nid: NodeID) -> NodeID {
        if nid.pkg != 0 {
            return nid;
        }
        let children = vec![
            self.intern_trivial_int(scope as i64),
            self.intern_trivial_int(nid.level as i64),
            self.intern_trivial_int(nid.ty as i64),
            self.intern_trivial_int(nid.inst as i64),
        ];
        self.intern(cat_undefined(), children)
    }

    pub(crate) fn intern_trivial_int(&self, n: i64) -> NodeID {
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_INT,
            inst: (n as i32) as u32,
        }
    }

    pub(crate) fn intern_string(&mut self, s: &str) -> NodeID {
        if let Some(&idx) = self.str_idx.get(s) {
            return NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: idx,
            };
        }
        let idx = self.strs.len() as u32;
        self.strs.push(s.to_string());
        self.str_idx.insert(s.to_string(), idx);
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_STRING,
            inst: idx,
        }
    }

    fn substrate_mark(&self) -> Vec<Value> {
        vec![
            Value::Int(self.next_inst as i64),
            Value::Int(self.strs.len() as i64),
            Value::Int(self.by_id.len() as i64),
        ]
    }

    fn substrate_counts(&self) -> Vec<Value> {
        vec![
            Value::Int(self.by_id.len() as i64),
            Value::Int(self.strs.len() as i64),
        ]
    }

    fn substrate_release(&mut self, mark: &[Value]) -> i64 {
        if mark.len() < 2 {
            return 0;
        }
        let next_mark = mark[0].as_int() as u32;
        let str_mark = mark[1].as_int() as usize;
        if next_mark == 0 || str_mark > self.strs.len() {
            return 0;
        }
        let doomed: Vec<NodeID> = self
            .by_id
            .keys()
            .copied()
            .filter(|nid| nid.pkg == 0 && nid.inst >= next_mark)
            .collect();
        for nid in &doomed {
            self.by_id.remove(nid);
            self.source_attr.remove(nid);
            self.walk_cache.remove(nid);
        }
        self.by_shape
            .retain(|_, nid| !(nid.pkg == 0 && nid.inst >= next_mark));
        for s in self.strs.iter().skip(str_mark) {
            self.str_idx.remove(s);
        }
        self.strs.truncate(str_mark);
        self.next_inst = next_mark;
        self.walk_cache.clear();
        doomed.len() as i64
    }

    fn mark_string_node(n: NodeID, live_strings: &mut HashSet<NameID>) {
        if n.pkg == 1 && n.level == LEVEL_TRIVIAL && n.ty == TRIV_STRING {
            live_strings.insert(n.inst);
        }
    }

    fn mark_node(
        &self,
        n: NodeID,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
    ) {
        Self::mark_string_node(n, live_strings);
        if n.pkg != 0 || live_nodes.contains(&n) {
            return;
        }
        let Some(recipe) = self.by_id.get(&n) else {
            return;
        };
        live_nodes.insert(n);
        self.mark_node(recipe.category, live_nodes, live_strings);
        for child in &recipe.children {
            self.mark_node(*child, live_nodes, live_strings);
        }
    }

    fn mark_value(
        &self,
        value: &Value,
        arena: Option<&Arena>,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
        live_frames: &mut HashSet<FrameId>,
    ) {
        match value {
            Value::List(xs) => {
                for item in xs {
                    self.mark_value(item, arena, live_nodes, live_strings, live_frames);
                }
            }
            Value::Closure(cl) => {
                live_strings.insert(cl.name);
                self.mark_node(cl.body, live_nodes, live_strings);
                if let Some(a) = arena {
                    self.mark_frame(a, cl.env, live_nodes, live_strings, live_frames);
                }
            }
            Value::Nid(nid) => self.mark_node(*nid, live_nodes, live_strings),
            _ => {}
        }
    }

    fn mark_frame(
        &self,
        arena: &Arena,
        frame: FrameId,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
        live_frames: &mut HashSet<FrameId>,
    ) {
        let mut cur = Some(frame);
        while let Some(id) = cur {
            if !live_frames.insert(id) {
                return;
            }
            let Some(f) = arena.frames.get(id as usize) else {
                return;
            };
            for (name, value) in &f.bindings {
                live_strings.insert(*name);
                self.mark_value(value, Some(arena), live_nodes, live_strings, live_frames);
            }
            cur = f.parent;
        }
    }

    fn substrate_gc(&mut self, roots: &[Value], stack: Option<(&Arena, FrameId)>) -> Vec<Value> {
        let mut live_nodes: HashSet<NodeID> = HashSet::new();
        let mut live_strings: HashSet<NameID> = HashSet::new();
        let mut live_frames: HashSet<FrameId> = HashSet::new();
        for name in self.natives.keys() {
            live_strings.insert(*name);
        }
        for (_, (file_id, _, _)) in &self.source_attr {
            live_strings.insert(*file_id);
        }
        for root in &self.active_roots {
            self.mark_node(*root, &mut live_nodes, &mut live_strings);
        }
        for root in roots {
            self.mark_value(
                root,
                stack.map(|(arena, _)| arena),
                &mut live_nodes,
                &mut live_strings,
                &mut live_frames,
            );
        }
        if let Some((arena, frame)) = stack {
            self.mark_frame(
                arena,
                frame,
                &mut live_nodes,
                &mut live_strings,
                &mut live_frames,
            );
        }
        let mut changed = true;
        while changed {
            let before_nodes = live_nodes.len();
            let before_strings = live_strings.len();
            for (nid, value) in &self.walk_cache {
                if live_nodes.contains(nid) {
                    self.mark_value(
                        value,
                        stack.map(|(arena, _)| arena),
                        &mut live_nodes,
                        &mut live_strings,
                        &mut live_frames,
                    );
                }
            }
            changed = live_nodes.len() != before_nodes || live_strings.len() != before_strings;
        }
        let doomed: Vec<NodeID> = self
            .by_id
            .keys()
            .copied()
            .filter(|nid| nid.pkg == 0 && !live_nodes.contains(nid))
            .collect();
        for nid in &doomed {
            self.by_id.remove(nid);
            self.source_attr.remove(nid);
            self.walk_cache.remove(nid);
        }
        self.by_shape
            .retain(|_, nid| !(nid.pkg == 0 && !live_nodes.contains(nid)));
        self.walk_cache
            .retain(|nid, _| nid.pkg != 0 || live_nodes.contains(nid));
        let mut pruned = 0usize;
        if stack.is_some() {
            while let Some(idx) = self.strs.len().checked_sub(1) {
                let name_id = idx as NameID;
                if live_strings.contains(&name_id) {
                    break;
                }
                if let Some(s) = self.strs.pop() {
                    self.str_idx.remove(&s);
                    pruned += 1;
                }
            }
        }
        vec![Value::Int(doomed.len() as i64), Value::Int(pruned as i64)]
    }

    fn category(&self, n: NodeID) -> NodeID {
        if n.level == LEVEL_TRIVIAL {
            return n;
        }
        self.by_id.get(&n).map(|r| r.category).unwrap_or(n)
    }

    // Owned children — clones the children vec. The slice version went
    // away when substrate-write natives required `&mut Kernel`; future
    // breath restores zero-copy via Cow<'_, [NodeID]>.
    pub(crate) fn children(&self, n: NodeID) -> Vec<NodeID> {
        self.by_id
            .get(&n)
            .map(|r| r.children.clone())
            .unwrap_or_default()
    }

    fn readonly_worker_clone(&self) -> Self {
        Self {
            by_shape: self.by_shape.clone(),
            by_id: self.by_id.clone(),
            source_attr: self.source_attr.clone(),
            walk_cache: HashMap::new(),
            walk_cache_hits: 0,
            walk_cache_misses: 0,
            import_seq: self.import_seq,
            strs: self.strs.clone(),
            str_idx: self.str_idx.clone(),
            next_inst: self.next_inst,
            natives: self.natives.clone(),
            env_natives: self.env_natives.clone(),
            active_roots: Vec::new(),
            trace: None,
        }
    }

    fn is_parallel_pure(&self, n: NodeID, seen: &mut HashSet<NodeID>) -> bool {
        if n.level == LEVEL_TRIVIAL {
            return true;
        }
        if !seen.insert(n) {
            return true;
        }
        let Some(recipe) = self.by_id.get(&n) else {
            return false;
        };
        match recipe.category.ty {
            RB_MATH | RB_COMPARE | RB_LOGIC | RB_COND | RB_LIST => recipe
                .children
                .iter()
                .all(|child| self.is_parallel_pure(*child, seen)),
            _ => false,
        }
    }

    pub(crate) fn trivial_value(&self, n: NodeID) -> Value {
        match n.ty {
            TRIV_INT => Value::Int((n.inst as i32) as i64),
            TRIV_STRING => Value::Str(self.strs[n.inst as usize].clone()),
            TRIV_BOOL => Value::Bool(n.inst != 0),
            TRIV_NULL => Value::Null,
            _ => panic!("trivial_value: unknown trivial type {}", n.ty),
        }
    }

    // Interned name handle — the NameID this identifier resolves to. No
    // string allocation, no comparison; lookup is a u32 compare downstream.
    //
    // OPT (2026-05-21): Reads `self.by_id.get(&n)` directly instead of going
    // through `self.children(n)` which clones the children Vec. Saves one
    // Vec allocation per IDENT dispatch. With IDENT at 36.5% of dispatches
    // on python_demo.fk (viz_kernel_trace.py output), this is the single
    // hottest path in the walker.
    fn ident_id(&self, n: NodeID) -> NameID {
        if n.level == LEVEL_TRIVIAL && n.ty == TRIV_STRING {
            return n.inst;
        }
        if let Some(r) = self.by_id.get(&n) {
            let kids = &r.children;
            if kids.len() == 1 && kids[0].level == LEVEL_TRIVIAL && kids[0].ty == TRIV_STRING {
                return kids[0].inst;
            }
        }
        panic!("ident_id: {:?} is not an identifier shape", n);
    }

    // Resolve a NameID back to its source-level string. Only used in error
    // messages and on the parse-time slow path.
    fn name_str(&self, id: NameID) -> &str {
        &self.strs[id as usize]
    }
}

// ---------------------------------------------------------------------------
// Values — runtime tagged values
// ---------------------------------------------------------------------------

// `Nid` lets Form code hold NodeIDs as first-class values — the foundation
// for substrate-write natives that close form-runtime-in-form gaps W1-W3.
#[derive(Clone, Debug)]
pub(crate) enum Value {
    Null,
    Int(i64),
    Str(String),
    Bool(bool),
    List(Vec<Value>),
    Closure(Arc<Closure>),
    Nid(NodeID),
}

#[derive(Debug)]
struct Closure {
    // Interned name for display only — runtime lookup never uses it.
    name: NameID,
    params: Vec<NameID>,
    body: NodeID,
    env: FrameId,
}

impl Value {
    fn display(&self) -> String {
        match self {
            Value::Null => "null".to_string(),
            Value::Int(n) => n.to_string(),
            Value::Str(s) => s.clone(),
            Value::Bool(b) => {
                if *b {
                    "true".to_string()
                } else {
                    "false".to_string()
                }
            }
            Value::List(xs) => {
                let parts: Vec<String> = xs.iter().map(|x| x.display()).collect();
                format!("[{}]", parts.join(", "))
            }
            Value::Closure(c) => format!("<closure #{}>", c.name),
            Value::Nid(n) => format!("@{}.{}.{}.{}", n.pkg, n.level, n.ty, n.inst),
        }
    }

    fn as_nid(&self) -> NodeID {
        match self {
            Value::Nid(n) => *n,
            _ => panic!("as_nid: {:?}", self),
        }
    }

    fn as_int(&self) -> i64 {
        match self {
            Value::Int(n) => *n,
            _ => panic!("as_int: {:?}", self),
        }
    }

    fn as_bool(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Int(n) => *n != 0,
            Value::Null => false,
            _ => true,
        }
    }

    fn as_str(&self) -> &str {
        match self {
            Value::Str(s) => s,
            _ => panic!("as_str: {:?}", self),
        }
    }
}

fn native_walk_parallel(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
    let roots: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("walk_parallel: first argument must be a list of NodeIDs"),
    };
    let mut workers = args[1].as_int().max(1) as usize;
    if roots.is_empty() {
        return Value::List(Vec::new());
    }
    workers = workers.min(roots.len());
    let sequential = |k: &mut Kernel, roots: &[NodeID]| {
        let mut out = Vec::with_capacity(roots.len());
        for root in roots {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            out.push(walk(k, &mut sub_arena, *root, env));
        }
        Value::List(out)
    };
    if workers <= 1
        || k.trace.is_some()
        || !roots
            .iter()
            .all(|root| k.is_parallel_pure(*root, &mut HashSet::new()))
    {
        return sequential(k, &roots);
    }

    let mut buckets = vec![Vec::<(usize, NodeID)>::new(); workers];
    for (idx, root) in roots.iter().copied().enumerate() {
        buckets[idx % workers].push((idx, root));
    }
    let mut handles = Vec::with_capacity(workers);
    for bucket in buckets {
        let mut worker = k.readonly_worker_clone();
        handles.push(std::thread::spawn(move || {
            let mut chunk = Vec::with_capacity(bucket.len());
            for (idx, root) in bucket {
                let mut sub_arena = Arena::new();
                let env = sub_arena.new_frame(None);
                chunk.push((idx, walk(&mut worker, &mut sub_arena, root, env)));
            }
            chunk
        }));
    }
    let mut out: Vec<Option<Value>> = vec![None; roots.len()];
    for handle in handles {
        for (idx, value) in handle.join().expect("walk_parallel worker panicked") {
            out[idx] = Some(value);
        }
    }
    Value::List(
        out.into_iter()
            .map(|value| value.expect("walk_parallel missing worker result"))
            .collect(),
    )
}

fn native_walk_parallel_cached(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
    let roots: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("walk_parallel_cached: first argument must be a list of NodeIDs"),
    };
    let mut workers = args[1].as_int().max(1) as usize;
    if roots.is_empty() {
        return Value::List(Vec::new());
    }
    workers = workers.min(roots.len());
    let all_pure = roots
        .iter()
        .all(|root| k.is_parallel_pure(*root, &mut HashSet::new()));
    if !all_pure {
        let mut out = Vec::with_capacity(roots.len());
        for root in &roots {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            out.push(walk(k, &mut sub_arena, *root, env));
        }
        return Value::List(out);
    }
    if workers <= 1 || roots.len() <= 1 || k.trace.is_some() {
        let cache_enabled = k.trace.is_none();
        let mut out = Vec::with_capacity(roots.len());
        let mut local = HashMap::<NodeID, Value>::new();
        for root in &roots {
            if cache_enabled {
                if let Some(v) = k.walk_cache.get(root).cloned() {
                    k.walk_cache_hits += 1;
                    out.push(v);
                    continue;
                }
                if let Some(v) = local.get(root).cloned() {
                    k.walk_cache_hits += 1;
                    out.push(v);
                    continue;
                }
                k.walk_cache_misses += 1;
            }
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            let value = walk(k, &mut sub_arena, *root, env);
            if cache_enabled {
                k.walk_cache.insert(*root, value.clone());
                local.insert(*root, value.clone());
            }
            out.push(value);
        }
        return Value::List(out);
    }

    let mut out: Vec<Option<Value>> = vec![None; roots.len()];
    let mut jobs = Vec::<(usize, NodeID)>::new();
    let mut first = HashMap::<NodeID, usize>::new();
    let mut fanout = HashMap::<usize, Vec<usize>>::new();
    for (idx, root) in roots.iter().copied().enumerate() {
        if let Some(v) = k.walk_cache.get(&root).cloned() {
            k.walk_cache_hits += 1;
            out[idx] = Some(v);
        } else if let Some(primary) = first.get(&root).copied() {
            k.walk_cache_hits += 1;
            fanout.entry(primary).or_default().push(idx);
        } else {
            k.walk_cache_misses += 1;
            first.insert(root, idx);
            jobs.push((idx, root));
        }
    }
    if !jobs.is_empty() {
        let mut buckets = vec![Vec::<(usize, NodeID)>::new(); workers];
        for (pos, job) in jobs.into_iter().enumerate() {
            buckets[pos % workers].push(job);
        }
        let mut handles = Vec::with_capacity(workers);
        for bucket in buckets {
            if bucket.is_empty() {
                continue;
            }
            let mut worker = k.readonly_worker_clone();
            handles.push(std::thread::spawn(move || {
                let mut chunk = Vec::with_capacity(bucket.len());
                for (idx, root) in bucket {
                    let mut sub_arena = Arena::new();
                    let env = sub_arena.new_frame(None);
                    chunk.push((idx, root, walk(&mut worker, &mut sub_arena, root, env)));
                }
                chunk
            }));
        }
        for handle in handles {
            for (idx, root, value) in handle.join().expect("walk_parallel_cached worker panicked") {
                k.walk_cache.insert(root, value.clone());
                out[idx] = Some(value);
                if let Some(dups) = fanout.get(&idx) {
                    for dup in dups {
                        out[*dup] = out[idx].clone();
                    }
                }
            }
        }
    }
    Value::List(
        out.into_iter()
            .map(|value| value.expect("walk_parallel_cached missing worker result"))
            .collect(),
    )
}

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

// Frame — arena-resident scope. Bindings as a small ordered vec; the
// common case (function call with 1-3 args) beats a hash table at this
// size and keeps the data layout cache-friendly.
#[derive(Debug)]
struct Frame {
    parent: Option<FrameId>,
    bindings: Vec<(NameID, Value)>,
}

// ---------------------------------------------------------------------------
// Native functions — what Form-on-top reaches for at the leaves
// ---------------------------------------------------------------------------

impl Kernel {
    fn register_env_native(&mut self, name: &str, category: NodeID, f: EnvAwareNativeFn) {
        let id = self.intern_string(name).inst;
        self.env_natives.insert(
            id,
            EnvAwareNativeEntry {
                name: id,
                category,
                func: f,
            },
        );
    }

    fn register_native(&mut self, name: &str, category: NodeID, f: NativeFn) {
        let id = self.intern_string(name).inst;
        self.natives.insert(
            id,
            NativeEntry {
                name: id,
                category,
                func: f,
            },
        );
    }

    fn register_natives(&mut self) {
        // Blueprint attribution discipline:
        //   cat_call()      — invoke external effect (I/O, tool)
        //   cat_access()    — read a property / field (length, index, byte)
        //   cat_method()    — transform on a cell-like value (string build, format)
        //   cat_compare()   — equality / ordering
        //   cat_list_nat()  — construct or destructure a List
        //   cat_witness()   — substrate self-attestation (intern, walk, lookup)
        //   cat_undefined() — honest "no Form category settled yet"
        //
        // The category rides on each NativeEntry; the walker records it in
        // the trace when the native fires. The kernel knows itself from
        // inside, not only at its Form surface.

        self.register_native("print", cat_call(), |_, _, args| {
            for (i, a) in args.iter().enumerate() {
                if i > 0 {
                    print!(" ");
                }
                print!("{}", a.display());
            }
            println!();
            Value::Null
        });
        self.register_native("str_len", cat_access(), |_, _, args| {
            Value::Int(args[0].as_str().len() as i64)
        });
        self.register_native("substring", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let a = args[1].as_int() as usize;
            let b = args[2].as_int() as usize;
            Value::Str(s[a..b].to_string())
        });
        self.register_native("char_at", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let i = args[1].as_int() as usize;
            Value::Str((s.as_bytes()[i] as char).to_string())
        });
        self.register_native("str_concat", cat_method(), |_, _, args| {
            let mut s = args[0].as_str().to_string();
            s.push_str(args[1].as_str());
            Value::Str(s)
        });
        // str_find — Rust-level substring search starting at index `from`.
        // (str_find s needle from) → int (index or -1). Whole search in
        // this Rust loop; no Form callback per byte, no Form recursion.
        self.register_native("str_find", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let needle = args[1].as_str();
            let from = args[2].as_int() as usize;
            if from > s.len() {
                return Value::Int(-1);
            }
            match s[from..].find(needle) {
                Some(i) => Value::Int((from + i) as i64),
                None => Value::Int(-1),
            }
        });
        // scan_run — return the end-index where a contiguous run of bytes
        // matching `class_code` ends (exclusive). Sibling parity with Go +
        // TS scan_run. Generic per-byte loop in Rust avoids the walker
        // dispatch a pure-Form recursion would pay per character.
        // Class codes: 0=ws, 1=digit, 2=alpha, 3=identifier-char,
        //              4=non-quote-non-escape, 5=non-newline.
        self.register_native("scan_run", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let from = args[1].as_int().max(0) as usize;
            let class = args[2].as_int();
            let bytes = s.as_bytes();
            let n = bytes.len();
            let mut end = from.min(n);
            match class {
                0 => while end < n && matches!(bytes[end], b' ' | b'\t' | b'\n' | b'\r') { end += 1; },
                1 => while end < n && bytes[end].is_ascii_digit() { end += 1; },
                2 => while end < n && bytes[end].is_ascii_alphabetic() { end += 1; },
                3 => while end < n && (bytes[end].is_ascii_alphanumeric() || bytes[end] == b'_' || bytes[end] == b'-') { end += 1; },
                4 => while end < n && bytes[end] != b'"' && bytes[end] != b'\\' { end += 1; },
                5 => while end < n && bytes[end] != b'\n' { end += 1; },
                _ => panic!("scan_run: unknown class_code {} (valid: 0-5)", class),
            }
            Value::Int(end as i64)
        });
        // string_fold — Rust-level streaming iteration over a string's bytes.
        // Signature: (string_fold s init step) where step is a closure of
        // (acc, char) → acc. Whole iteration in this Rust for-loop; no Form-
        // level recursion. Lets the substrate process arbitrary-length input
        // streams without piling kernel stack frames.
        self.register_native("string_fold", cat_call(), |k, a, args| {
            let s = args[0].as_str().to_string();
            let mut acc = args[1].clone();
            let cl = match &args[2] {
                Value::Closure(c) => c.clone(),
                _ => panic!("string_fold: third arg must be a closure"),
            };
            if cl.params.len() != 2 {
                panic!(
                    "string_fold: step closure wants 2 params (acc char), got {}",
                    cl.params.len()
                );
            }
            for byte in s.as_bytes().to_vec() {
                let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
                a.bind(call_frame, cl.params[0], acc);
                a.bind(call_frame, cl.params[1], Value::Str((byte as char).to_string()));
                acc = walk(k, a, cl.body, call_frame);
            }
            acc
        });
        self.register_native("str_eq", cat_compare(RCMP_EQ), |_, _, args| {
            Value::Bool(args[0].as_str() == args[1].as_str())
        });
        // int_to_str — value-to-string for trivial leaves. Historical name
        // (first use: line numbers in cell-trace.fk); semantics is "render
        // any trivial value as text" so emit-engine.fk's leaf walker can
        // pass node_value of any leaf type through it. Multi-target emit
        // (universal codec lattice — emit.fk + emits/json.fk) depends on
        // string + bool + null passthrough.
        self.register_native("int_to_str", cat_method(), |_, _, args| match &args[0] {
            Value::Str(s) => Value::Str(s.clone()),
            Value::Bool(b) => Value::Str(if *b {
                "true".to_string()
            } else {
                "false".to_string()
            }),
            Value::Null => Value::Str("null".to_string()),
            _ => Value::Str(args[0].as_int().to_string()),
        });
        self.register_native("str_to_int", cat_method(), |_, _, args| {
            Value::Int(args[0].as_str().parse().unwrap_or(0))
        });
        self.register_native("ord", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            if s.is_empty() {
                Value::Int(-1)
            } else {
                Value::Int(s.as_bytes()[0] as i64)
            }
        });
        self.register_native("byte_to_str", cat_access(), |_, _, args| {
            let b = args[0].as_int();
            if !(0..=255).contains(&b) {
                Value::Str(String::new())
            } else {
                Value::Str((b as u8 as char).to_string())
            }
        });
        self.register_native("list", cat_list_nat(), |_, _, args| {
            Value::List(args.to_vec())
        });
        self.register_native("cons", cat_list_nat(), |_, _, args| {
            let mut out = vec![args[0].clone()];
            if let Value::List(rest) = &args[1] {
                out.extend(rest.iter().cloned());
            }
            Value::List(out)
        });
        self.register_native("head", cat_list_nat(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                xs.first().cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            }
        });
        self.register_native("tail", cat_list_nat(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                Value::List(if xs.is_empty() {
                    vec![]
                } else {
                    xs[1..].to_vec()
                })
            } else {
                Value::Null
            }
        });
        self.register_native("len", cat_access(), |_, _, args| match &args[0] {
            Value::List(xs) => Value::Int(xs.len() as i64),
            Value::Str(s) => Value::Int(s.len() as i64),
            _ => Value::Int(0),
        });
        // `nth` composted 2026-05-22 — unused in form-stdlib/, can be
        // re-authored in core.fk as needed:
        //   (defn nth (xs n)
        //       (if (eq n 0) (head xs)
        //           (nth (tail xs) (sub n 1))))
        self.register_native("empty", cat_list_nat(), |_, _, _| Value::List(vec![]));
        // min / max / sum — common Python builtins applied to a list.
        // sum returns the integer sum; min/max return the smallest/largest
        // int element. All three handle empty lists honestly (sum=0,
        // min/max panic with a clear message matching CPython's TypeError).
        self.register_native("min", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if xs.is_empty() {
                    panic!("min: empty list");
                }
                let mut best = xs[0].as_int();
                for v in &xs[1..] {
                    let x = v.as_int();
                    if x < best {
                        best = x;
                    }
                }
                return Value::Int(best);
            }
            Value::Int(args[0].as_int())
        });
        self.register_native("max", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if xs.is_empty() {
                    panic!("max: empty list");
                }
                let mut best = xs[0].as_int();
                for v in &xs[1..] {
                    let x = v.as_int();
                    if x > best {
                        best = x;
                    }
                }
                return Value::Int(best);
            }
            Value::Int(args[0].as_int())
        });
        // `sum` composted from the kernel native list 2026-05-22 —
        // core.fk's `(defn sum (xs) (foldl plus 0 xs))` covers it
        // via the existing `foldl` + `plus` primitives. Kernel
        // minimality audit (kernel-minimality-audit.md) named this
        // one of 9 composable natives; this is the first compost.
        self.register_native("abs", cat_method(), |_, _, args| {
            let n = args[0].as_int();
            Value::Int(if n < 0 { -n } else { n })
        });
        // Polymorphic `+` for Python compilation: int+int→add,
        // str+str→concat, list+list→concat. The compile-time emitter
        // can't always determine operand types (variables, function
        // returns); _plus dispatches at runtime instead.
        self.register_native("_plus", cat_method(), |_, _, args| {
            match (&args[0], &args[1]) {
                (Value::Int(a), Value::Int(b)) => Value::Int(a + b),
                (Value::Str(a), Value::Str(b)) => {
                    let mut s = a.clone();
                    s.push_str(b);
                    Value::Str(s)
                }
                (Value::Str(a), Value::Int(b)) => {
                    let mut s = a.clone();
                    s.push_str(&b.to_string());
                    Value::Str(s)
                }
                (Value::Int(a), Value::Str(b)) => {
                    let mut s = a.to_string();
                    s.push_str(b);
                    Value::Str(s)
                }
                (Value::List(a), Value::List(b)) => {
                    let mut out = a.clone();
                    out.extend(b.iter().cloned());
                    Value::List(out)
                }
                _ => panic!("_plus: unsupported operand types"),
            }
        });
        // range(n)        → [0, 1, ..., n-1]
        // range(a, b)     → [a, a+1, ..., b-1]
        // range(a, b, s)  → [a, a+s, a+2s, ..., < b]
        // Opens `for i in range(N):` end-to-end through the kernel —
        // the most common Python loop idiom. Same semantics as CPython's
        // range builtin (returning an eager list rather than a lazy
        // iterator, which the kernel doesn't yet have iterators for).
        // `range` composted 2026-05-22 — core.fk's
        //   (defn range (start end)
        //       (if (ge start end) (empty)
        //           (cons start (range (add start 1) end))))
        // covers the (start, end) variant. Step variant can be re-
        // authored in core.fk if/when needed (no current usage).
        self.register_native(
            "read_file",
            cat_call(),
            |_, _, args| match fs::read_to_string(args[0].as_str()) {
                Ok(s) => Value::Str(s),
                Err(_) => Value::Null,
            },
        );
        // Byte-level host file read — returns a list of ints (0-255), one per byte.
        self.register_native("read_file_bytes", cat_call(), |_, _, args| {
            match fs::read(args[0].as_str()) {
                Ok(bytes) => Value::List(bytes.into_iter().map(|b| Value::Int(b as i64)).collect()),
                Err(_) => Value::Null,
            }
        });
        // write_form_binary — emit a Recipe to .fkb in the full artifact
        // format (string table + tree). Sibling to read_form_binary.
        // Use when source-compile output crosses kernel invocations:
        // serialize-recipe alone drops string indices.
        self.register_native("write_form_binary", cat_call(), |k, _, args| {
            let path = args[0].as_str().to_string();
            let nid = args[1].as_nid();
            let bytes = serialize_artifact(k, nid);
            match fs::write(&path, &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("read_form_binary", cat_call(), |k, _, args| {
            match fs::read(args[0].as_str()) {
                Ok(bytes) => match deserialize_artifact(k, &bytes) {
                    Ok(root) => Value::Nid(root),
                    Err(_) => Value::Null,
                },
                Err(_) => Value::Null,
            }
        });
        self.register_native("file_size", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) => Value::Int(meta.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // file_mtime — modification time in unix seconds; -1 if missing.
        // Sibling parity with Go + TS file_mtime; powers Form-side cache
        // layers that regenerate .fkb projections when source files drift.
        self.register_native("file_mtime", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) => match meta.modified() {
                    Ok(t) => match t.duration_since(std::time::UNIX_EPOCH) {
                        Ok(d) => Value::Int(d.as_secs() as i64),
                        Err(_) => Value::Int(-1),
                    },
                    Err(_) => Value::Int(-1),
                },
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("file_byte_at", cat_call(), |_, _, args| {
            let offset = args[1].as_int();
            if offset < 0 {
                return Value::Int(-1);
            }
            let mut file = match fs::File::open(args[0].as_str()) {
                Ok(file) => file,
                Err(_) => return Value::Int(-1),
            };
            if file.seek(SeekFrom::Start(offset as u64)).is_err() {
                return Value::Int(-1);
            }
            let mut buf = [0u8; 1];
            match file.read(&mut buf) {
                Ok(1) => Value::Int(buf[0] as i64),
                _ => Value::Int(-1),
            }
        });
        self.register_native("read_file_slice", cat_call(), |_, _, args| {
            let offset = args[1].as_int();
            let length = args[2].as_int();
            if offset < 0 || length <= 0 {
                return Value::Str(String::new());
            }
            let mut file = match fs::File::open(args[0].as_str()) {
                Ok(file) => file,
                Err(_) => return Value::Str(String::new()),
            };
            if file.seek(SeekFrom::Start(offset as u64)).is_err() {
                return Value::Str(String::new());
            }
            let mut buf = vec![0u8; length as usize];
            match file.read(&mut buf) {
                Ok(n) => Value::Str(String::from_utf8_lossy(&buf[..n]).to_string()),
                Err(_) => Value::Str(String::new()),
            }
        });

        // --- Substrate write surface ------------------------------------
        // Form code holds NodeIDs as values (Value::Nid) and uses these
        // natives to construct recipes. Closes form-runtime-in-form gaps
        // W1-W3. With these, templates (Breath 2) become expressible —
        // Form code can BUILD recipes from pattern matches, not just walk
        // pre-existing ones. All attributed as WITNESS — the substrate
        // attesting to its own structure.

        self.register_native("make_nodeid", cat_witness(), |_, _, args| {
            Value::Nid(NodeID {
                pkg: args[0].as_int() as u32,
                level: args[1].as_int() as u32,
                ty: args[2].as_int() as u32,
                inst: args[3].as_int() as u32,
            })
        });
        self.register_native("intern_trivial_int", cat_witness(), |k, _, args| {
            Value::Nid(k.intern_trivial_int(args[0].as_int()))
        });
        self.register_native("intern_trivial_string", cat_witness(), |k, _, args| {
            let s = args[0].as_str().to_string();
            Value::Nid(k.intern_string(&s))
        });
        self.register_native("intern_node", cat_witness(), |k, _, args| {
            // args[0]: category as Nid; args[1]: children as List of Nids
            let cat = args[0].as_nid();
            let kids: Vec<NodeID> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
                _ => panic!("intern_node: children must be a list"),
            };
            Value::Nid(k.intern(cat, kids))
        });
        self.register_native("substrate_mark", cat_witness(), |k, _, _| {
            Value::List(k.substrate_mark())
        });
        self.register_native("substrate_counts", cat_witness(), |k, _, _| {
            Value::List(k.substrate_counts())
        });
        self.register_native(
            "substrate_release",
            cat_witness(),
            |k, _, args| match &args[0] {
                Value::List(mark) => Value::Int(k.substrate_release(mark)),
                _ => Value::Int(0),
            },
        );
        self.register_native("substrate_gc", cat_witness(), |k, _, args| match &args[0] {
            Value::List(roots) => Value::List(k.substrate_gc(roots, None)),
            _ => Value::List(k.substrate_gc(&[], None)),
        });
        self.register_native("node_category", cat_witness(), |k, _, args| {
            Value::Nid(k.category(args[0].as_nid()))
        });
        self.register_native("node_children", cat_witness(), |k, _, args| {
            let kids = k.children(args[0].as_nid());
            Value::List(kids.into_iter().map(Value::Nid).collect())
        });
        self.register_native("node_value", cat_witness(), |k, _, args| {
            k.trivial_value(args[0].as_nid())
        });
        self.register_native("node_pkg", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().pkg as i64)
        });
        self.register_native("node_level", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().level as i64)
        });
        self.register_native("node_type", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().ty as i64)
        });
        self.register_native("node_inst", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().inst as i64)
        });
        // node_eq — compare two NodeIDs structurally without coercing to int.
        // The kernel's `eq` (RCMP_EQ) does as_int on both operands, which
        // panics on NodeIDs. node_eq closes that gap so Form code (like
        // emit-engine.fk's lookup-template) can dispatch on Recipe category
        // by direct NodeID equality. Sibling parity required across Go/TS.
        self.register_native("node_eq", cat_compare(RCMP_EQ), |_, _, args| {
            Value::Bool(args[0].as_nid() == args[1].as_nid())
        });
        // value_eq — polymorphic equality across Value kinds. Returns
        // true when both args have the same kind AND compare equal
        // within that kind. Cross-kind returns false. Use when a
        // Form-side function holds tagged values that may be either
        // strings or NodeIDs — e.g. domain/lens in bmf-symbol-context.
        self.register_native("value_eq", cat_compare(RCMP_EQ), |_, _, args| {
            let eq = match (&args[0], &args[1]) {
                (Value::Null, Value::Null) => true,
                (Value::Int(x), Value::Int(y)) => x == y,
                (Value::Str(x), Value::Str(y)) => x == y,
                (Value::Bool(x), Value::Bool(y)) => x == y,
                (Value::Nid(x), Value::Nid(y)) => x == y,
                _ => false,
            };
            Value::Bool(eq)
        });
        // intern_node_at — intern a composite Recipe AND record its source
        // attribution. Engine.fk's parser actions call this so every emitted
        // Recipe carries (file, line, col) provenance. The satsang teaching:
        // a cell's state can be traced back to the recipe lines that
        // authored it — the practice of self-knowing.
        //
        // Args: (category, children, file_string, line_int, col_int)
        // Returns: the interned NodeID (same as intern_node).
        self.register_native("intern_node_at", cat_witness(), |k, _, args| {
            let cat = args[0].as_nid();
            let kids: Vec<NodeID> = match &args[1] {
                Value::List(v) => v.iter().map(|x| x.as_nid()).collect(),
                _ => Vec::new(),
            };
            let nid = k.intern(cat, kids);
            let file_nid = k.intern_string(args[2].as_str());
            let file_id = file_nid.inst;
            let line = args[3].as_int() as u32;
            let col = args[4].as_int() as u32;
            k.source_attr.insert(nid, (file_id, line, col));
            Value::Nid(nid)
        });
        // node_source — read back a Recipe's source attribution.
        // Returns (list file_string line col) or empty list if none recorded.
        self.register_native("node_source", cat_witness(), |k, _, args| {
            let nid = args[0].as_nid();
            match k.source_attr.get(&nid).copied() {
                Some((file_id, line, col)) => {
                    let file = k.strs[file_id as usize].clone();
                    Value::List(vec![
                        Value::Str(file),
                        Value::Int(line as i64),
                        Value::Int(col as i64),
                    ])
                }
                None => Value::List(vec![]),
            }
        });
        // framebuffer-events — return all NodeIDs that have source
        // attribution recorded. The substrate's source_attr side-map
        // IS the framebuffer: every intern_node_at write becomes a
        // discoverable trace event. Observer-side tracing: the
        // EMITTER pays only the side-map write (~O(1)); the OBSERVER
        // pays the cost of walking + filtering this list when it
        // wants to analyze hot-spots or flow.
        self.register_native("framebuffer-events", cat_witness(), |k, _, _| {
            Value::List(k.source_attr.keys().copied().map(Value::Nid).collect())
        });
        // framebuffer-clear — reset the framebuffer. Useful for
        // bounded observation windows (subscribe → do work →
        // analyze → clear → next window).
        self.register_native("framebuffer-clear", cat_witness(), |k, _, _| {
            k.source_attr.clear();
            Value::Null
        });
        // serialize-recipe — walk a Recipe tree, emit a flat byte list
        // (each byte as Value::Int). Format per node: 5 big-endian u32
        // values (pkg, level, ty, inst, children_count) + recursively
        // each child's serialization. Trivials have children_count=0.
        // The substrate's content-addressing means deserialize re-
        // creates the same NodeID via intern.
        self.register_native("serialize-recipe", cat_witness(), |k, _, args| {
            let mut bytes: Vec<u8> = Vec::new();
            serialize_nid(k, args[0].as_nid(), &mut bytes);
            Value::List(bytes.into_iter().map(|b| Value::Int(b as i64)).collect())
        });
        // deserialize-recipe — read flat byte list back into a Recipe
        // tree, re-interning composites so the resulting NodeIDs
        // collapse to the same identities as the original tree.
        self.register_native("deserialize-recipe", cat_witness(), |k, _, args| {
            let bytes: Vec<u8> = match &args[0] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => Vec::new(),
            };
            let scope = k.next_import_scope();
            let (nid, _pos) = deserialize_nid(k, &bytes, 0, scope);
            Value::Nid(nid)
        });
        // write_file_bytes — write a list of byte-values to a path.
        // Sibling of read_file_bytes (added with PNG binary parser).
        self.register_native("write_file_bytes", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let bytes: Vec<u8> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => Vec::new(),
            };
            match fs::write(&path, &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // write_file_text — host text output. Keeps text compilers from
        // materializing byte lists while byte codecs still use write_file_bytes.
        self.register_native("write_file_text", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let text = args[1].as_str().to_string();
            match fs::write(&path, text.as_bytes()) {
                Ok(_) => Value::Int(text.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // walk_recipe — evaluate a NodeID in a fresh root frame. Returns
        // the value the recipe produces. Use case: Form code builds a
        // recipe via intern_node, then walks it to get the runtime result.
        self.register_native("walk_recipe", cat_witness(), |k, _, args| {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            walk(k, &mut sub_arena, args[0].as_nid(), env)
        });
        // walk_recipe_here — walks a Recipe in the CALLER's env, so let-
        // bindings inside the Recipe land in the caller's scope. Matches
        // the Go kernel's env-aware variant.
        self.register_env_native("walk_recipe_here", cat_witness(), |k, a, env, args| {
            // Pin the recipe root as an active root so substrate_gc keeps the
            // definitions reachable. Closures bound here hold body NodeIDs
            // that aren't reachable from the source-parsed root, so without
            // this pin a subsequent substrate_gc would sweep them and leave
            // env holding closures with deleted bodies.
            let root = args[0].as_nid();
            k.active_roots.push(root);
            walk(k, a, root, env)
        });
        self.register_native("walk_parallel", cat_witness(), native_walk_parallel);
        self.register_native("walk-parallel", cat_witness(), native_walk_parallel);
        self.register_native(
            "walk_parallel_cached",
            cat_witness(),
            native_walk_parallel_cached,
        );
        self.register_native(
            "walk-parallel-cached",
            cat_witness(),
            native_walk_parallel_cached,
        );
        // walk-cached — JIT-vector memoization. Caller asserts the
        // recipe is pure (no I/O, no external state). Result cached
        // by recipe NodeID. Subsequent calls return O(1) from cache
        // instead of re-walking the tree. Demonstrates the JIT slot:
        // once a recipe is identified as a hot path (via framebuffer
        // observation), its result can be cached / pre-compiled.
        // Real JIT replaces this cache with native machine code; the
        // architectural shape stays the same.
        self.register_native("walk-cached", cat_witness(), |k, _, args| {
            let nid = args[0].as_nid();
            if let Some(v) = k.walk_cache.get(&nid).cloned() {
                k.walk_cache_hits += 1;
                return v;
            }
            k.walk_cache_misses += 1;
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            let v = walk(k, &mut sub_arena, nid, env);
            k.walk_cache.insert(nid, v.clone());
            v
        });
        // walk-cache-clear — reset the memoization cache. Use when
        // the substrate state changes in ways that would invalidate
        // cached results (e.g. native re-registration).
        self.register_native("walk-cache-clear", cat_witness(), |k, _, _| {
            k.walk_cache.clear();
            k.walk_cache_hits = 0;
            k.walk_cache_misses = 0;
            Value::Null
        });
        // walk-cache-size — number of cached recipes. Useful for
        // observability — when paired with framebuffer-events, lets
        // tooling compare "recipes seen" vs "recipes JIT-cached".
        self.register_native("walk-cache-size", cat_witness(), |k, _, _| {
            Value::Int(k.walk_cache.len() as i64)
        });
        self.register_native("walk-cache-stats", cat_witness(), |k, _, _| {
            Value::List(vec![
                Value::Int(k.walk_cache_hits as i64),
                Value::Int(k.walk_cache_misses as i64),
                Value::Int(k.walk_cache.len() as i64),
            ])
        });

        // native_blueprint — read a native's Form category from inside Form.
        // Returns the category NodeID (level=2, ty=RBasic, inst=instance) or
        // Null if the name isn't bound to a native. Makes attribution legible
        // from Form code: `(native_blueprint "intern_node")` → @1.2.6.1.
        self.register_native("native_blueprint", cat_witness(), |k, _, args| {
            let s = args[0].as_str();
            match k.str_idx.get(s).copied() {
                Some(name_id) => match k.natives.get(&name_id) {
                    Some(ne) => Value::Nid(ne.category),
                    None => Value::Null,
                },
                None => Value::Null,
            }
        });

        // --- Debug / inspection -----------------------------------------
        // `trace` — print-and-return. Drop into any Form expression to
        // inspect a value mid-computation without breaking control flow.
        // Output goes to stderr so it doesn't pollute the result on stdout.
        //   (let result (trace (filter even? xs)))
        //   (trace "label" value)   ; with a label prefix
        // No Form category claimed — `trace` is a debug surface, honest
        // about being outside the structural vocabulary.
        self.register_native("trace", cat_undefined(), |_, _, args| {
            if args.len() >= 2 {
                eprintln!("[trace {}] {}", args[0].as_str(), args[1].display());
                args[1].clone()
            } else {
                eprintln!("[trace] {}", args[0].display());
                args[0].clone()
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Walker — full RBasic dispatch
// ---------------------------------------------------------------------------

fn walk(k: &mut Kernel, a: &mut Arena, n: NodeID, env: FrameId) -> Value {
    if n.level == LEVEL_TRIVIAL {
        return k.trivial_value(n);
    }
    let cat = k.category(n);
    // Tracing hook: when k.trace is Some, record the arm dispatch. Pure
    // counter increment — no allocation, no IO. Per lc-native-kernel-binary
    // "tracing and observation pattern". Records (ty, inst) so typed-numeric
    // distribution (MATH.PLUS_F64 vs MATH.PLUS_I32) stays distinguishable.
    if let Some(t) = &mut k.trace {
        t.record(cat.ty, cat.inst);
    }
    let kids = k.children(n);

    match cat.ty {
        RB_MATH => {
            let l = walk(k, a, kids[0], env).as_int();
            let r = walk(k, a, kids[1], env).as_int();
            Value::Int(match cat.inst {
                RMATH_PLUS => l + r,
                RMATH_MINUS => l - r,
                RMATH_MULTIPLY => l * r,
                RMATH_DIVIDE => l / r,
                RMATH_MODULO => l % r,
                _ => panic!("math: unknown op {}", cat.inst),
            })
        }
        RB_COMPARE => {
            let l = walk(k, a, kids[0], env).as_int();
            let r = walk(k, a, kids[1], env).as_int();
            Value::Bool(match cat.inst {
                RCMP_EQ => l == r,
                RCMP_NE => l != r,
                RCMP_LT => l < r,
                RCMP_LE => l <= r,
                RCMP_GT => l > r,
                RCMP_GE => l >= r,
                _ => panic!("compare: unknown op {}", cat.inst),
            })
        }
        RB_LOGIC => match cat.inst {
            RLOG_AND => {
                if !walk(k, a, kids[0], env).as_bool() {
                    Value::Bool(false)
                } else {
                    Value::Bool(walk(k, a, kids[1], env).as_bool())
                }
            }
            RLOG_OR => {
                if walk(k, a, kids[0], env).as_bool() {
                    Value::Bool(true)
                } else {
                    Value::Bool(walk(k, a, kids[1], env).as_bool())
                }
            }
            RLOG_NOT => Value::Bool(!walk(k, a, kids[0], env).as_bool()),
            _ => panic!("logic: unknown op {}", cat.inst),
        },
        RB_COND => {
            if walk(k, a, kids[0], env).as_bool() {
                walk(k, a, kids[1], env)
            } else if cat.inst == RCOND_IF_ELSE && kids.len() >= 3 {
                walk(k, a, kids[2], env)
            } else {
                Value::Null
            }
        }
        RB_BLOCK => {
            if cat.inst == RBLK_LET {
                let name = k.ident_id(kids[0]);
                let v = walk(k, a, kids[1], env);
                a.bind(env, name, v.clone());
                return v;
            }
            let mut last = Value::Null;
            for c in kids {
                last = walk(k, a, c, env);
            }
            last
        }
        RB_IDENT => {
            let id = k.ident_id(n);
            a.lookup(env, id)
                .unwrap_or_else(|| panic!("unbound: {}", k.name_str(id)))
        }
        RB_FNDEF => {
            let name = k.ident_id(kids[0]);
            let params: Vec<NameID> = k.children(kids[1]).iter().map(|p| p.inst).collect();
            let cl = Arc::new(Closure {
                name,
                params,
                body: kids[2],
                env,
            });
            a.bind(env, name, Value::Closure(cl.clone()));
            Value::Closure(cl)
        }
        RB_FNCALL => {
            let name = k.ident_id(kids[0]);
            // Env-aware natives first — they need caller env (walk_recipe_here).
            let env_ne_opt = k.env_natives.get(&name).copied();
            if let Some(ne) = env_ne_opt {
                if a.lookup(env, name).is_none() {
                    let mut args = Vec::with_capacity(kids.len() - 1);
                    for arg in &kids[1..] {
                        args.push(walk(k, a, *arg, env));
                    }
                    if ne.category.ty != RB_UNDEFINED {
                        if let Some(t) = &mut k.trace {
                            t.record(ne.category.ty, ne.category.inst);
                        }
                    }
                    let native_name = k.name_str(ne.name).to_string();
                    if let Some(t) = &mut k.trace {
                        t.record_native(&native_name);
                    }
                    return (ne.func)(k, a, env, &args);
                }
            }
            // Native takes priority unless user shadowed. Copy the entry
            // out so the natives-map borrow releases before we call &mut k.
            let ne_opt = k.natives.get(&name).copied();
            if let Some(ne) = ne_opt {
                if a.lookup(env, name).is_none() {
                    let mut args = Vec::with_capacity(kids.len() - 1);
                    for arg in &kids[1..] {
                        args.push(walk(k, a, *arg, env));
                    }
                    // Native Blueprint attribution — record the Form
                    // category the native expresses alongside the FNCALL
                    // arm already recorded above. Trace now reflects the
                    // structural shape of the work, not just the dispatch
                    // mechanism.
                    if ne.category.ty != RB_UNDEFINED {
                        if let Some(t) = &mut k.trace {
                            t.record(ne.category.ty, ne.category.inst);
                        }
                    }
                    let native_name = k.name_str(ne.name).to_string();
                    if let Some(t) = &mut k.trace {
                        t.record_native(&native_name);
                    }
                    return (ne.func)(k, a, &args);
                }
            }
            let callee = a
                .lookup(env, name)
                .unwrap_or_else(|| panic!("unbound function: {}", k.name_str(name)));
            let cl = match callee {
                Value::Closure(c) => c,
                _ => panic!("not callable: {}", k.name_str(name)),
            };
            if kids.len() - 1 != cl.params.len() {
                panic!(
                    "{} wants {} args, got {}",
                    k.name_str(name),
                    cl.params.len(),
                    kids.len() - 1
                );
            }
            let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            // Evaluate args in CALLER's env, then bind in call_frame.
            // The clone is Arc<Closure> — bump-the-refcount, not deep.
            let cl2 = cl.clone();
            for (i, p) in cl2.params.iter().enumerate() {
                let arg = walk(k, a, kids[i + 1], env);
                a.bind(call_frame, *p, arg);
            }
            let fn_name = k.name_str(cl.name).to_string();
            if let Some(t) = &mut k.trace {
                t.record_fn(&fn_name);
            }
            walk(k, a, cl.body, call_frame)
        }
        RB_LIST => {
            let mut out = Vec::with_capacity(kids.len());
            for c in &kids {
                out.push(walk(k, a, *c, env));
            }
            Value::List(out)
        }
        // Structural passthrough — categories the walker can't yet execute
        // (CHOICE_MATCH, CONSTRUCTOR, INDUCTIVE, QUOTIENT, ALIAS, BLANKET,
        // PROJECT, GENERATIVE, PROOF, INFERENCE, VECTOR, TILE, PARALLELIZE,
        // VECTORIZE, OBSERVER, TRANSMUTE, ...) intern fine and the trace
        // records their attribution. Walking returns the NodeID itself so
        // downstream structural reasoning continues. Sibling-parity with
        // TS kernel's behavior. The honest stance: "this kernel knows the
        // shape exists but cannot yet execute its semantics; the substrate
        // identity is preserved." Replaces the prior panic — kernels are
        // no longer fragile in face of recipes from richer dialects.
        _ => Value::Nid(n),
    }
}

// ---------------------------------------------------------------------------
// S-expression source adapter — text → recipe tree
// ---------------------------------------------------------------------------

// SexpTok — source-reader cell. Carries 1-based line/col so parse
// errors can point at the source. Without this, every paren imbalance
// surfaces as an unhelpful "index out of bounds" panic.
#[derive(Debug, Clone)]
struct SexpTok {
    kind: &'static str,
    value: String,
    line: u32,
    col: u32,
}

fn tokenize_sexp(src: &str) -> Vec<SexpTok> {
    let bytes = src.as_bytes();
    let mut toks = Vec::with_capacity(64);
    let mut i = 0;
    let mut line: u32 = 1;
    let mut col: u32 = 1;
    while i < bytes.len() {
        let c = bytes[i];
        let (sline, scol) = (line, col);
        match c {
            b'\n' => {
                i += 1;
                line += 1;
                col = 1;
            }
            b' ' | b'\t' | b'\r' => {
                i += 1;
                col += 1;
            }
            b';' => {
                while i < bytes.len() && bytes[i] != b'\n' {
                    i += 1;
                }
                // newline handled by outer loop
            }
            b'(' => {
                toks.push(SexpTok {
                    kind: "LPAREN",
                    value: "(".into(),
                    line: sline,
                    col: scol,
                });
                i += 1;
                col += 1;
            }
            b')' => {
                toks.push(SexpTok {
                    kind: "RPAREN",
                    value: ")".into(),
                    line: sline,
                    col: scol,
                });
                i += 1;
                col += 1;
            }
            b'"' => {
                i += 1;
                col += 1;
                let start = i;
                while i < bytes.len() && bytes[i] != b'"' {
                    if bytes[i] == b'\\' && i + 1 < bytes.len() {
                        i += 2;
                        col += 2;
                        continue;
                    }
                    if bytes[i] == b'\n' {
                        line += 1;
                        col = 1;
                    } else {
                        col += 1;
                    }
                    i += 1;
                }
                let raw = &src[start..i];
                toks.push(SexpTok {
                    kind: "STRING",
                    value: unescape(raw),
                    line: sline,
                    col: scol,
                });
                if i < bytes.len() {
                    i += 1;
                    col += 1;
                }
            }
            b'0'..=b'9' => {
                let start = i;
                while i < bytes.len() && bytes[i].is_ascii_digit() {
                    i += 1;
                }
                toks.push(SexpTok {
                    kind: "INT",
                    value: src[start..i].to_string(),
                    line: sline,
                    col: scol,
                });
                col += (i - start) as u32;
            }
            b'-' if i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit() => {
                let start = i;
                i += 1;
                while i < bytes.len() && bytes[i].is_ascii_digit() {
                    i += 1;
                }
                toks.push(SexpTok {
                    kind: "INT",
                    value: src[start..i].to_string(),
                    line: sline,
                    col: scol,
                });
                col += (i - start) as u32;
            }
            _ => {
                let start = i;
                while i < bytes.len() {
                    let cc = bytes[i];
                    if cc == b' '
                        || cc == b'\t'
                        || cc == b'\n'
                        || cc == b'\r'
                        || cc == b'('
                        || cc == b')'
                        || cc == b'"'
                        || cc == b';'
                    {
                        break;
                    }
                    i += 1;
                }
                toks.push(SexpTok {
                    kind: "IDENT",
                    value: src[start..i].to_string(),
                    line: sline,
                    col: scol,
                });
                col += (i - start) as u32;
            }
        }
    }
    toks
}

fn unescape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'\\' && i + 1 < bytes.len() {
            match bytes[i + 1] {
                b'n' => out.push('\n'),
                b't' => out.push('\t'),
                b'r' => out.push('\r'),
                b'\\' => out.push('\\'),
                b'"' => out.push('"'),
                c => out.push(c as char),
            }
            i += 2;
            continue;
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    out
}

// read_sexp — every error path includes line/col so paren imbalance points
// at the source instead of dying with "index out of bounds." The source
// reader is foreign-syntax-by-necessity; its job is to fail informatively
// when humans miscount.
fn read_sexp(k: &mut Kernel, toks: &[SexpTok], i: usize) -> (NodeID, usize) {
    if i >= toks.len() {
        panic!("parse error: unexpected end of input (expected an expression)");
    }
    let t = &toks[i];
    match t.kind {
        "INT" => {
            let n: i64 = t.value.parse().unwrap();
            (k.intern_trivial_int(n), i + 1)
        }
        "STRING" => (k.intern_string(&t.value), i + 1),
        "IDENT" => {
            // Bool literals — true/false are reserved, become trivial values at
            // parse time. Parallel to int/string literals; lets Form predicates
            // read naturally without `(eq 0 0)` constructors.
            if t.value == "true" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_BOOL,
                        inst: 1,
                    },
                    i + 1,
                );
            }
            if t.value == "false" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_BOOL,
                        inst: 0,
                    },
                    i + 1,
                );
            }
            let s = k.intern_string(&t.value);
            (k.intern(cat_ident(), vec![s]), i + 1)
        }
        "RPAREN" => {
            panic!(
                "parse error at line {} col {}: unmatched `)` (no `(` to close)",
                t.line, t.col
            );
        }
        "LPAREN" => {
            let (open_line, open_col) = (t.line, t.col);
            let mut j = i + 1;
            if j >= toks.len() {
                panic!(
                    "parse error: unclosed `(` opened at line {} col {} (reached end of input)",
                    open_line, open_col
                );
            }
            if toks[j].kind == "RPAREN" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_NULL,
                        inst: 0,
                    },
                    j + 1,
                );
            }
            if toks[j].kind != "IDENT" {
                panic!("parse error at line {} col {}: expected verb after `(` opened at line {} col {}, got {} {:?}",
                    toks[j].line, toks[j].col, open_line, open_col, toks[j].kind, toks[j].value);
            }
            let verb = toks[j].value.clone();
            j += 1;
            let mut args = Vec::new();
            loop {
                if j >= toks.len() {
                    panic!("parse error: unclosed `(` opened at line {} col {} in `({} ...)` (reached end of input)",
                        open_line, open_col, verb);
                }
                if toks[j].kind == "RPAREN" {
                    j += 1;
                    break;
                }
                let (arg, nj) = read_sexp(k, toks, j);
                args.push(arg);
                j = nj;
            }
            (build_verb(k, &verb, args), j)
        }
        _ => panic!(
            "parse error at line {} col {}: unexpected token {} {:?}",
            t.line, t.col, t.kind, t.value
        ),
    }
}

fn build_verb(k: &mut Kernel, verb: &str, args: Vec<NodeID>) -> NodeID {
    match verb {
        "do" => k.intern(cat_block(RBLK_DO), args),
        "seq" => k.intern(cat_block(RBLK_SEQ), args),
        "let" => {
            // (let <ident> <value>) — args[0] is an Identifier recipe wrapping
            // a string trivial. Repackage as the bare string trivial.
            let name_id = k.ident_id(args[0]);
            let name_trivial = NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: name_id,
            };
            k.intern(cat_block(RBLK_LET), vec![name_trivial, args[1]])
        }
        "if" => {
            if args.len() == 2 {
                k.intern(cat_cond(RCOND_IF), args)
            } else {
                k.intern(cat_cond(RCOND_IF_ELSE), args)
            }
        }
        "add" => k.intern(cat_math(RMATH_PLUS), args),
        "sub" => k.intern(cat_math(RMATH_MINUS), args),
        "mul" => k.intern(cat_math(RMATH_MULTIPLY), args),
        "div" => k.intern(cat_math(RMATH_DIVIDE), args),
        "mod" => k.intern(cat_math(RMATH_MODULO), args),
        "eq" => k.intern(cat_compare(RCMP_EQ), args),
        "ne" => k.intern(cat_compare(RCMP_NE), args),
        "lt" => k.intern(cat_compare(RCMP_LT), args),
        "le" => k.intern(cat_compare(RCMP_LE), args),
        "gt" => k.intern(cat_compare(RCMP_GT), args),
        "ge" => k.intern(cat_compare(RCMP_GE), args),
        "and" => k.intern(cat_logic(RLOG_AND), args),
        "or" => k.intern(cat_logic(RLOG_OR), args),
        "not" => k.intern(cat_logic(RLOG_NOT), args),
        "defn" => {
            // (defn <name> (<params>...) <body>) — repackage name + params
            // as bare string trivials so the walker reads `inst` as NameID.
            let name_id = k.ident_id(args[0]);
            let name_trivial = NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: name_id,
            };
            let param_ids: Vec<NameID> =
                k.children(args[1]).iter().map(|p| k.ident_id(*p)).collect();
            let param_trivials: Vec<NodeID> = param_ids
                .into_iter()
                .map(|id| NodeID {
                    pkg: 1,
                    level: LEVEL_TRIVIAL,
                    ty: TRIV_STRING,
                    inst: id,
                })
                .collect();
            let params_block = k.intern(cat_block(RBLK_SEQ), param_trivials);
            k.intern(cat_fndef(), vec![name_trivial, params_block, args[2]])
        }
        "params" => k.intern(cat_block(RBLK_SEQ), args),
        _ => {
            let name_str = k.intern_string(verb);
            let mut all = vec![name_str];
            all.extend(args);
            k.intern(cat_fncall(), all)
        }
    }
}

fn cat_math(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_MATH,
        inst,
    }
}
fn cat_compare(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_COMPARE,
        inst,
    }
}
fn cat_logic(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_LOGIC,
        inst,
    }
}
fn cat_cond(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_COND,
        inst,
    }
}
fn cat_block(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_BLOCK,
        inst,
    }
}
fn cat_ident() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_IDENT,
        inst: 1,
    }
}
fn cat_fndef() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_FNDEF,
        inst: 1,
    }
}
fn cat_fncall() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_FNCALL,
        inst: 1,
    }
}

// Native-attribution category constructors. Each names the Form-shape
// a native expresses; the walker records them in the trace when the
// native fires. inst:1 is the "generic instance" — when a native maps
// to a specific RBasic subop (e.g. str_eq → COMPARE.EQ), use the
// already-existing cat_compare(RCMP_EQ) instead.
fn cat_call() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_CALL,
        inst: 1,
    }
}
fn cat_witness() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_WITNESS,
        inst: 1,
    }
}
fn cat_access() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_ACCESS,
        inst: 1,
    }
}
fn cat_method() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_METHOD,
        inst: 1,
    }
}
fn cat_list_nat() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_LIST,
        inst: 1,
    }
}
fn cat_transmute() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_TRANSMUTE,
        inst: 1,
    }
}
fn cat_undefined() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_UNDEFINED,
        inst: 0,
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn count_top_level(toks: &[SexpTok]) -> usize {
    let mut depth = 0;
    let mut count = 0;
    for t in toks {
        match t.kind {
            "LPAREN" => {
                if depth == 0 {
                    count += 1;
                }
                depth += 1;
            }
            "RPAREN" => {
                depth -= 1;
            }
            _ => {
                if depth == 0 {
                    count += 1;
                }
            }
        }
    }
    count
}

fn run_source(src: &str) -> Value {
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, src);
    execute_root(&mut k, root)
}

fn read_root_from_source(k: &mut Kernel, src: &str) -> NodeID {
    let toks = tokenize_sexp(src);
    let wrapped: String;
    let toks = if count_top_level(&toks) == 1 {
        toks
    } else {
        wrapped = format!("(do {})", src);
        tokenize_sexp(&wrapped)
    };
    let (root, _) = read_sexp(k, &toks, 0);
    root
}

fn execute_root(k: &mut Kernel, root: NodeID) -> Value {
    let mut a = Arena::new();
    let env = a.new_frame(None);
    k.active_roots = vec![root];
    let value = walk(k, &mut a, root, env);
    k.substrate_gc(&[value.clone()], Some((&a, env)));
    value
}

// --- Native implementations — same recursive shape as the Form versions.
// `black_box` on the recursive call's argument prevents LLVM from analyzing
// the recursion and constant-folding the whole computation. Without it,
// pure functions with eventually-constant inputs collapse to a register
// load and the "native" column becomes a measurement of nothing. With it,
// the actual instructions get executed.

fn native_fib(n: i64) -> i64 {
    if n <= 1 {
        n
    } else {
        native_fib(std::hint::black_box(n - 1)) + native_fib(std::hint::black_box(n - 2))
    }
}

fn native_fact(n: i64) -> i64 {
    if n <= 1 {
        1
    } else {
        n * native_fact(std::hint::black_box(n - 1))
    }
}

fn native_sum(n: i64, acc: i64) -> i64 {
    if n == 0 {
        acc
    } else {
        native_sum(std::hint::black_box(n - 1), std::hint::black_box(acc + n))
    }
}

fn native_ack(m: i64, n: i64) -> i64 {
    if m == 0 {
        n + 1
    } else if n == 0 {
        native_ack(std::hint::black_box(m - 1), 1)
    } else {
        native_ack(
            std::hint::black_box(m - 1),
            native_ack(m, std::hint::black_box(n - 1)),
        )
    }
}

// `black_box` prevents LLVM from constant-folding pure functions called
// with constant arguments — without it, native_fact(12) gets folded to
// 479001600 at compile time and the "native" column measures register
// loads, not arithmetic. Passing args through black_box at the call site
// forces the optimizer to treat them as opaque and actually execute.
use std::hint::black_box;

fn run_bench() {
    // Native runners — each takes opaque inputs and returns an int. The
    // black_box on the entry point makes LLVM compile actual code paths.
    type Runner = fn() -> i64;
    let cases: &[(&str, &str, u32, Runner)] = &[
        (
            "fib28",
            "(do (defn fib (n) (if (le n 1) n (add (fib (sub n 1)) (fib (sub n 2))))) (fib 28))",
            100,
            || native_fib(black_box(28)),
        ),
        (
            "fact12",
            "(do (defn fact (n) (if (le n 1) 1 (mul n (fact (sub n 1))))) (fact 12))",
            5_000_000,
            || native_fact(black_box(12)),
        ),
        (
            "sum1000",
            "(do (defn sum (n acc) (if (eq n 0) acc (sum (sub n 1) (add acc n)))) (sum 1000 0))",
            50_000,
            || native_sum(black_box(1000), black_box(0)),
        ),
        (
            "ackermann",
            "(do (defn ack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (ack (sub m 1) 1) (ack (sub m 1) (ack m (sub n 1)))))) (ack 3 6))",
            100,
            || native_ack(black_box(3), black_box(6)),
        ),
    ];

    const KERNEL_ITERS: u32 = 5;

    println!(
        "{:<12} {:<12} {:<14} {:<14} {}",
        "workload", "result", "native", "kernel", "overhead"
    );
    for (name, src, native_iters, native) in cases {
        // Native timing — black_box the result so the loop can't be hoisted
        let start = Instant::now();
        let mut native_result = 0i64;
        for _ in 0..*native_iters {
            native_result = black_box(native());
        }
        let native_dur = start.elapsed() / *native_iters;
        let _ = native_result;

        // Kernel timing — fresh kernel per case so intern starts clean
        let toks = tokenize_sexp(src);
        let mut k = Kernel::new();
        let (root, _) = read_sexp(&mut k, &toks, 0);
        let start = Instant::now();
        let mut kernel_result = Value::Null;
        for _ in 0..KERNEL_ITERS {
            let mut a = Arena::new();
            let env = a.new_frame(None);
            kernel_result = walk(&mut k, &mut a, root, env);
        }
        let kernel_dur = start.elapsed() / KERNEL_ITERS;

        let overhead = kernel_dur.as_nanos() as f64 / native_dur.as_nanos().max(1) as f64;
        println!(
            "{:<12} {:<12} {:<14} {:<14} {:.0}×",
            name,
            kernel_result.display(),
            format!("{:?}", native_dur),
            format!("{:?}", kernel_dur),
            overhead,
        );
    }
}

// ---------------------------------------------------------------------------
// Traced run — same as run_source but with the Trace counter enabled.
// Used by the `trace` subcommand. Hot-path runs use the un-traced version.
// ---------------------------------------------------------------------------

fn run_source_traced(src: &str) -> (Value, Trace) {
    let toks = tokenize_sexp(src);
    let wrapped: String;
    let toks = if count_top_level(&toks) == 1 {
        toks
    } else {
        wrapped = format!("(do {})", src);
        tokenize_sexp(&wrapped)
    };
    let mut k = Kernel::new();
    k.trace = Some(Trace::new());
    let (root, _) = read_sexp(&mut k, &toks, 0);
    let mut a = Arena::new();
    let env = a.new_frame(None);
    k.active_roots = vec![root];
    let value = walk(&mut k, &mut a, root, env);
    k.substrate_gc(&[value.clone()], Some((&a, env)));
    let trace = k.trace.take().unwrap_or_default();
    (value, trace)
}

// ---------------------------------------------------------------------------
// CLI subcommands — list / execute / query / trace / fetch
// ---------------------------------------------------------------------------
//
// Parallels scripts/form_cli.py at the native binary altitude. The point
// per lc-native-kernel-binary: end-to-end host-native kernel binaries that
// can access I/O, binary form objects, substrate API, and network resources
// — functionally equivalent to the Python runtime.

const RECIPES_DIR: &str = "recipes";

fn cli_help() {
    println!(
        "form-kernel-rust — native macOS / Linux Form kernel binary

Subcommands:
  --binary <file.fkb>                 execute a Form binary artifact
  --emit-binary <out.fkb> <file.fk...> write a Form binary artifact
  list <library.json>                  print library meta + recipes
  execute <library.json> <recipe> [args...]   run a recipe natively
  query <path>                         parse any file as a Form object tree
  trace [--expr \"...\" | <file.fk>]     run with arm-dispatch tracing
  fetch <url>                          GET a URL (network resource)

Source adapter modes:
  <file.fk> [more.fk ...]              run .fk files
  --expr \"<form-expression>\"          evaluate a Form expression
  --bench                              benchmark run
  --numeric-bench                      numeric kernel comparison"
    );
}

fn cli_list(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust list <library.json>");
        return 2;
    }
    let path = &args[0];
    let bytes = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", path, e);
            return 1;
        }
    };
    let lib: serde_json::Value = match serde_json::from_str(&bytes) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("parse {}: {}", path, e);
            return 1;
        }
    };
    let meta = &lib["library_meta"];
    println!(
        "library: {}  v{}",
        meta["name"].as_str().unwrap_or("?"),
        meta["version"].as_str().unwrap_or("?")
    );
    println!("  path: {}", path);
    if let Some(langs) = lib["language_cells"].as_array() {
        let names: Vec<String> = langs
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect();
        println!("  language_cells: {}", names.join(", "));
    }
    let recipes = lib["recipes"].as_array().cloned().unwrap_or_default();
    println!("  recipes ({}):", recipes.len());
    for r in &recipes {
        let name = r["name"].as_str().unwrap_or("?");
        let bp = &r["blueprint"];
        let in_types: Vec<String> = bp["input_types"]
            .as_array()
            .map(|a| {
                a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let out_type = bp["output_type"].as_str().unwrap_or("?");
        let hint = r["node_id_hint"].as_str().unwrap_or("?");
        // Check if a .fk variant exists in the recipes/ directory
        let fk_path = format!("{}/{}.fk", RECIPES_DIR, name);
        let runnable = std::path::Path::new(&fk_path).exists();
        let marker = if runnable { "▶" } else { "·" };
        println!(
            "    {} {:<18} ({}) → {}  @recipe({})",
            marker,
            name,
            in_types.join(", "),
            out_type,
            hint
        );
    }
    0
}

fn cli_execute(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: form-kernel-rust execute <library.json> <recipe> [arg-json ...]");
        return 2;
    }
    let library_path = &args[0];
    let recipe_name = &args[1];
    let call_args = &args[2..];

    // Verify the recipe exists in the library (for the @recipe() hint)
    let lib_bytes = match fs::read_to_string(library_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", library_path, e);
            return 1;
        }
    };
    let lib: serde_json::Value = match serde_json::from_str(&lib_bytes) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("parse {}: {}", library_path, e);
            return 1;
        }
    };
    let found = lib["recipes"]
        .as_array()
        .map(|rs| {
            rs.iter()
                .any(|r| r["name"].as_str() == Some(recipe_name.as_str()))
        })
        .unwrap_or(false);
    if !found {
        eprintln!("recipe '{}' not in library {}", recipe_name, library_path);
        return 2;
    }

    // Load the .fk implementation. Today recipes live in
    // form/form-kernel-rust/recipes/<name>.fk — hand-authored
    // until the Form→fk auto-generator lands. Honest GAP-NK1.
    let fk_path = format!("{}/{}.fk", RECIPES_DIR, recipe_name);
    let fk_src = match fs::read_to_string(&fk_path) {
        Ok(s) => s,
        Err(_) => {
            eprintln!(
                "form-kernel-rust: no .fk implementation for '{}'.

The library declares the recipe; the Rust kernel needs an .fk source.
Expected at: {}
Today these are hand-authored. The Form→fk auto-generator (consuming
tongue_caches.form from the library and emitting S-expression source)
is named in lc-native-kernel-binary as the next breath.",
                recipe_name, fk_path
            );
            return 2;
        }
    };

    // Build a call expression that wraps the recipe definition + invocation.
    // Convention: the .fk file defines the recipe with `(defn recipe_name ...)`;
    // we append a call form using the JSON-parsed args.
    let mut argv_form = String::new();
    for a in call_args {
        // Each arg is JSON; convert to .fk syntax.
        let v: serde_json::Value = match serde_json::from_str(a) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("parse arg {:?}: {}", a, e);
                return 2;
            }
        };
        argv_form.push(' ');
        argv_form.push_str(&json_to_fk(&v));
    }
    let full_src = format!("{}\n({}{})", fk_src, recipe_name, argv_form);

    let value = run_source(&full_src);
    println!("{}", value.display());
    0
}

fn json_to_fk(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::Null => "null".to_string(),
        serde_json::Value::Bool(b) => {
            if *b {
                "true".to_string()
            } else {
                "false".to_string()
            }
        }
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => format!("{:?}", s),
        serde_json::Value::Array(xs) => {
            let parts: Vec<String> = xs.iter().map(json_to_fk).collect();
            format!("(list {})", parts.join(" "))
        }
        serde_json::Value::Object(_) => {
            // Object → list-of-pairs would need a per-recipe convention;
            // honest about the gap for now.
            "null".to_string()
        }
    }
}

fn cli_query(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust query <path>");
        return 2;
    }
    let path = &args[0];
    let text = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", path, e);
            return 1;
        }
    };

    let lang = if path.ends_with(".json") || path.ends_with(".recipelib.json") {
        "json"
    } else if path.ends_with(".fk") {
        "fk"
    } else {
        "raw"
    };

    let tree = match lang {
        "json" => match serde_json::from_str::<serde_json::Value>(&text) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("parse {}: {}", path, e);
                return 1;
            }
        },
        "fk" => {
            // Parse via the kernel's reader, return a structural sketch.
            // Full Form-object tree requires walking by_id with categories;
            // a flat sketch is the first move.
            let toks = tokenize_sexp(&text);
            let mut k = Kernel::new();
            let (root, _) = read_sexp(&mut k, &toks, 0);
            serde_json::json!({
                "source_tongue": "fk",
                "source_path":   path,
                "root_node_id":  format!("{}.{}.{}.{}", root.pkg, root.level, root.ty, root.inst),
                "node_count":    k.by_id.len(),
                "string_count":  k.strs.len(),
            })
        }
        _ => serde_json::json!({
            "source_tongue": "raw",
            "source_path":   path,
            "bytes":         text.len(),
            "lines":         text.lines().count(),
            "note":          "no Language cell wired for this extension yet",
        }),
    };
    println!("{}", serde_json::to_string_pretty(&tree).unwrap());
    0
}

fn cli_trace(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust trace [--expr \"...\" | <file.fk>]");
        return 2;
    }
    let src = if args[0] == "--expr" {
        if args.len() < 2 {
            eprintln!("--expr requires an argument");
            return 2;
        }
        args[1].clone()
    } else {
        match fs::read_to_string(&args[0]) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("read {}: {}", args[0], e);
                return 1;
            }
        }
    };

    let start = Instant::now();
    let (value, trace) = run_source_traced(&src);
    let elapsed = start.elapsed();

    let report = serde_json::json!({
        "result":            value.display(),
        "elapsed_us":        elapsed.as_micros(),
        "elapsed_human":     format!("{:?}", elapsed),
        "trace":             trace.to_json(),
    });
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
    0
}

fn cli_fetch(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust fetch <url>");
        return 2;
    }
    let url = &args[0];
    match ureq::get(url).call() {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.into_string().unwrap_or_default();
            let report = serde_json::json!({
                "url":     url,
                "status":  status,
                "body":    body,
                "bytes":   body.len(),
            });
            println!("{}", serde_json::to_string_pretty(&report).unwrap());
            0
        }
        Err(e) => {
            eprintln!("fetch {}: {}", url, e);
            1
        }
    }
}

fn cli_binary(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust --binary <file.fkb>");
        return 2;
    }
    let bytes = match fs::read(&args[0]) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("read {}: {}", args[0], e);
            return 1;
        }
    };
    let mut k = Kernel::new();
    let root = match deserialize_artifact(&mut k, &bytes) {
        Ok(root) => root,
        Err(e) => {
            eprintln!("form-kernel-rust: {}", e);
            return 1;
        }
    };
    let value = execute_root(&mut k, root);
    println!("{}", value.display());
    0
}

fn cli_emit_binary(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: form-kernel-rust --emit-binary <out.fkb> <file.fk> [more.fk ...]");
        return 2;
    }
    let mut parts = Vec::new();
    for path in &args[1..] {
        match fs::read_to_string(path) {
            Ok(s) => parts.push(s),
            Err(e) => {
                eprintln!("read {}: {}", path, e);
                return 1;
            }
        }
    }
    let src = parts.join("\n");
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, &src);
    let bytes = serialize_artifact(&k, root);
    if let Err(e) = fs::write(&args[0], bytes) {
        eprintln!("write {}: {}", args[0], e);
        return 1;
    }
    0
}

fn install_panic_hook() {
    // Override Rust's default panic handler so Form authors see a clean
    // "parse error at line X col Y: ..." message instead of Rust's internal
    // backtrace. Kernel devs can set RUST_BACKTRACE=1 to get the full
    // story when debugging the kernel itself.
    std::panic::set_hook(Box::new(|info| {
        let msg = info
            .payload()
            .downcast_ref::<String>()
            .map(|s| s.as_str())
            .or_else(|| info.payload().downcast_ref::<&str>().copied())
            .unwrap_or("unknown error");
        eprintln!("form-kernel-rust: {}", msg);
    }));
}

fn main_with_args(args: Vec<String>) -> i32 {
    if args.is_empty() {
        cli_help();
        return 2;
    }

    match args[0].as_str() {
        "--help" | "help" => {
            cli_help();
            0
        }
        "--bench" => {
            run_bench();
            0
        }
        "--numeric-bench" => {
            formats::run_numeric_bench();
            0
        }
        "--binary" => cli_binary(&args[1..]),
        "--emit-binary" => cli_emit_binary(&args[1..]),
        "list" => cli_list(&args[1..]),
        "execute" => cli_execute(&args[1..]),
        "query" => cli_query(&args[1..]),
        "trace" => cli_trace(&args[1..]),
        "fetch" => cli_fetch(&args[1..]),
        _ => {
            // Source adapter: --expr or <file.fk> [more.fk ...]
            let src = if args[0] == "--expr" {
                if args.len() < 2 {
                    eprintln!("--expr requires an argument");
                    std::process::exit(2);
                }
                args[1].clone()
            } else {
                let mut parts = Vec::with_capacity(args.len());
                for path in &args {
                    match fs::read_to_string(path) {
                        Ok(s) => parts.push(s),
                        Err(e) => {
                            eprintln!("read {}: {}", path, e);
                            std::process::exit(1);
                        }
                    }
                }
                parts.join("\n")
            };
            let result = run_source(&src);
            println!("{}", result.display());
            0
        }
    }
}

fn main() {
    install_panic_hook();

    let args: Vec<String> = env::args().skip(1).collect();
    let handle = std::thread::Builder::new()
        .name("form-kernel-rust".to_string())
        .stack_size(FORM_KERNEL_STACK_BYTES)
        .spawn(move || main_with_args(args))
        .unwrap_or_else(|e| {
            eprintln!("form-kernel-rust: failed to start execution worker: {}", e);
            std::process::exit(1);
        });
    let exit_code = match handle.join() {
        Ok(code) => code,
        Err(_) => 1,
    };
    std::process::exit(exit_code);
}

// ---------------------------------------------------------------------------
// Form binary artifact format
// ---------------------------------------------------------------------------
// Each node record is tagged. Leaves store their local 4-tuple value.
// Composites store the full category node followed by children. That keeps
// temporary, unregistered blueprint/recipe categories scoped to the artifact
// shape instead of treating their context-local NodeID numbers as global.

fn push_u32(bytes: &mut Vec<u8>, v: u32) {
    bytes.push((v >> 24) as u8);
    bytes.push((v >> 16) as u8);
    bytes.push((v >> 8) as u8);
    bytes.push(v as u8);
}

fn read_u32(bytes: &[u8], pos: usize) -> (u32, usize) {
    let v = ((bytes[pos] as u32) << 24)
        | ((bytes[pos + 1] as u32) << 16)
        | ((bytes[pos + 2] as u32) << 8)
        | (bytes[pos + 3] as u32);
    (v, pos + 4)
}

const FORM_BINARY_LEAF: u32 = 0;
const FORM_BINARY_COMPOSITE: u32 = 1;

fn serialize_nid(k: &Kernel, nid: NodeID, bytes: &mut Vec<u8>) {
    if let Some(recipe) = k.by_id.get(&nid) {
        push_u32(bytes, FORM_BINARY_COMPOSITE);
        serialize_nid(k, recipe.category, bytes);
        push_u32(bytes, recipe.children.len() as u32);
        for &c in &recipe.children {
            serialize_nid(k, c, bytes);
        }
    } else {
        push_u32(bytes, FORM_BINARY_LEAF);
        push_u32(bytes, nid.pkg);
        push_u32(bytes, nid.level);
        push_u32(bytes, nid.ty);
        push_u32(bytes, nid.inst);
    }
}

fn deserialize_nid(k: &mut Kernel, bytes: &[u8], pos: usize, scope: u32) -> (NodeID, usize) {
    let (tag, p) = read_u32(bytes, pos);
    if tag == FORM_BINARY_LEAF {
        let (pkg, p) = read_u32(bytes, p);
        let (level, p) = read_u32(bytes, p);
        let (ty, p) = read_u32(bytes, p);
        let (inst, p) = read_u32(bytes, p);
        return (
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        );
    }
    let (category, p) = deserialize_nid(k, bytes, p, scope);
    let (count, mut p) = read_u32(bytes, p);
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid(k, bytes, p, scope);
        children.push(c);
        p = np;
    }
    (k.intern(category, children), p)
}

const FORM_BINARY_MAGIC_V1: &[u8] = b"FORMBIN1";
const FORM_BINARY_MAGIC: &[u8] = b"FORMBIN2";

fn serialize_artifact(k: &Kernel, root: NodeID) -> Vec<u8> {
    let mut bytes = FORM_BINARY_MAGIC.to_vec();
    push_u32(&mut bytes, k.strs.len() as u32);
    for s in &k.strs {
        let raw = s.as_bytes();
        push_u32(&mut bytes, raw.len() as u32);
        bytes.extend_from_slice(raw);
    }
    serialize_nid(k, root, &mut bytes);
    bytes
}

fn deserialize_artifact(k: &mut Kernel, bytes: &[u8]) -> Result<NodeID, String> {
    let is_v1 = bytes.len() >= FORM_BINARY_MAGIC_V1.len()
        && &bytes[..FORM_BINARY_MAGIC_V1.len()] == FORM_BINARY_MAGIC_V1;
    let is_v2 = bytes.len() >= FORM_BINARY_MAGIC.len()
        && &bytes[..FORM_BINARY_MAGIC.len()] == FORM_BINARY_MAGIC;
    if !is_v1 && !is_v2 {
        return Err("form binary: bad magic".to_string());
    }
    let mut pos = if is_v1 {
        FORM_BINARY_MAGIC_V1.len()
    } else {
        FORM_BINARY_MAGIC.len()
    };
    let (string_count, p) = read_u32(bytes, pos);
    pos = p;
    let mut strings = Vec::with_capacity(string_count as usize);
    for _ in 0..string_count {
        let (len, p) = read_u32(bytes, pos);
        pos = p;
        let end = pos + len as usize;
        if end > bytes.len() {
            return Err("form binary: truncated string".to_string());
        }
        let value = std::str::from_utf8(&bytes[pos..end])
            .map_err(|e| format!("form binary: invalid utf8: {}", e))?
            .to_string();
        strings.push(value);
        pos = end;
    }
    let scope = k.next_import_scope();
    let (root, end) = if is_v1 {
        deserialize_nid_with_strings_v1(k, bytes, pos, &strings, scope)?
    } else {
        deserialize_nid_with_strings(k, bytes, pos, &strings, scope)?
    };
    if end != bytes.len() {
        return Err("form binary: trailing bytes".to_string());
    }
    Ok(root)
}

fn deserialize_nid_with_strings(
    k: &mut Kernel,
    bytes: &[u8],
    pos: usize,
    strings: &[String],
    scope: u32,
) -> Result<(NodeID, usize), String> {
    let (tag, p) = read_u32(bytes, pos);
    if tag == FORM_BINARY_LEAF {
        let (pkg, p) = read_u32(bytes, p);
        let (level, p) = read_u32(bytes, p);
        let (ty, p) = read_u32(bytes, p);
        let (inst, p) = read_u32(bytes, p);
        if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
            let value = strings
                .get(inst as usize)
                .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
            return Ok((k.intern_string(value), p));
        }
        return Ok((
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        ));
    }
    let (category, p) = deserialize_nid_with_strings(k, bytes, p, strings, scope)?;
    let (count, mut p) = read_u32(bytes, p);
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid_with_strings(k, bytes, p, strings, scope)?;
        children.push(c);
        p = np;
    }
    Ok((k.intern(category, children), p))
}

fn deserialize_nid_with_strings_v1(
    k: &mut Kernel,
    bytes: &[u8],
    pos: usize,
    strings: &[String],
    scope: u32,
) -> Result<(NodeID, usize), String> {
    let (pkg, p) = read_u32(bytes, pos);
    let (level, p) = read_u32(bytes, p);
    let (ty, p) = read_u32(bytes, p);
    let (inst, p) = read_u32(bytes, p);
    let (count, mut p) = read_u32(bytes, p);
    if count == 0 {
        if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
            let value = strings
                .get(inst as usize)
                .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
            return Ok((k.intern_string(value), p));
        }
        return Ok((
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        ));
    }
    let category = if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
        let value = strings
            .get(inst as usize)
            .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
        k.intern_string(value)
    } else {
        NodeID {
            pkg,
            level,
            ty,
            inst,
        }
    };
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid_with_strings_v1(k, bytes, p, strings, scope)?;
        children.push(c);
        p = np;
    }
    Ok((k.intern(category, children), p))
}
