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
use std::io::{Read, Seek, SeekFrom, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::Command;
use std::sync::mpsc;
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant};

mod bp_table;
mod formats;
mod inductive;
mod quotient;

// --- Socket natives — L1 physical layer (TCP) ---------------------------
// Sibling parity with form-kernel-go + form-kernel-ts. Handles are
// monotone i64s; the kernel never reveals the underlying TcpListener /
// TcpStream to Form code, only the handle. -1 always means error.
enum SocketKind {
    Listener(TcpListener),
    Stream(Mutex<TcpStream>),
}

struct SocketTable {
    handles: HashMap<i64, Arc<SocketKind>>,
    next: i64,
}

fn socket_table() -> &'static Mutex<SocketTable> {
    static T: OnceLock<Mutex<SocketTable>> = OnceLock::new();
    T.get_or_init(|| {
        Mutex::new(SocketTable {
            handles: HashMap::new(),
            next: 0,
        })
    })
}

fn socket_register(s: SocketKind) -> i64 {
    let mut t = socket_table().lock().unwrap();
    t.next += 1;
    let h = t.next;
    t.handles.insert(h, Arc::new(s));
    h
}

fn socket_lookup(h: i64) -> Option<Arc<SocketKind>> {
    let t = socket_table().lock().unwrap();
    t.handles.get(&h).cloned()
}

fn socket_drop(h: i64) -> bool {
    let mut t = socket_table().lock().unwrap();
    t.handles.remove(&h).is_some()
}

// --- Postgres natives — the DB carrier of the storage port --------------
// Form-rendered SQL executed against a real Postgres. Handles are monotone
// i64s; the kernel never reveals the postgres::Client to Form, only the
// handle. -1 = error. Effectful, per-kernel reference impl — the SQL strings
// are already three-way verified by db-schema.fk + emits/sql.fk; only
// execution lives here. See docs/coherence-substrate/cell-store-architecture.md
// (the DB is the production carrier; the FS log store is dev/test).
struct PgTable {
    handles: HashMap<i64, Arc<Mutex<postgres::Client>>>,
    next: i64,
}

fn pg_table() -> &'static Mutex<PgTable> {
    static T: OnceLock<Mutex<PgTable>> = OnceLock::new();
    T.get_or_init(|| {
        Mutex::new(PgTable {
            handles: HashMap::new(),
            next: 0,
        })
    })
}

fn pg_register(c: postgres::Client) -> i64 {
    let mut t = pg_table().lock().unwrap();
    t.next += 1;
    let h = t.next;
    t.handles.insert(h, Arc::new(Mutex::new(c)));
    h
}

fn pg_lookup(h: i64) -> Option<Arc<Mutex<postgres::Client>>> {
    let t = pg_table().lock().unwrap();
    t.handles.get(&h).cloned()
}

fn pg_drop(h: i64) -> bool {
    let mut t = pg_table().lock().unwrap();
    t.handles.remove(&h).is_some()
}

// Render one column of a postgres row to a string, by its SQL type. Covers the
// substrate's portable column set (text/varchar, the integer family, bool).
// NULL → "". Unknown types → "?". try_get keeps a type mismatch from panicking.
fn pg_cell_to_string(row: &postgres::Row, ci: usize) -> String {
    let ty = row.columns()[ci].type_().name().to_string();
    match ty.as_str() {
        "text" | "varchar" | "bpchar" | "name" => row
            .try_get::<usize, Option<String>>(ci)
            .ok()
            .flatten()
            .unwrap_or_default(),
        "int8" => row
            .try_get::<usize, Option<i64>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "int4" => row
            .try_get::<usize, Option<i32>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "int2" => row
            .try_get::<usize, Option<i16>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "bool" => row
            .try_get::<usize, Option<bool>>(ci)
            .ok()
            .flatten()
            .map(|v| if v { "t".to_string() } else { "f".to_string() })
            .unwrap_or_default(),
        _ => "?".to_string(),
    }
}

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
const RB_FIELD: u32 = 88;
const RB_CARRIER: u32 = 89;
const RB_TOPOLOGY: u32 = 90;
const RB_FIBER: u32 = 91;
const RB_REGION: u32 = 92;
const RB_BOUNDARY: u32 = 93;
const RB_NEIGHBORHOOD: u32 = 94;
const RB_MATCH_FIELD: u32 = 95;
const RB_DELTA: u32 = 96;
const RB_RESOLVE: u32 = 97;
const RB_COMMIT: u32 = 98;
const RB_STEP: u32 = 99;
const RB_LIFT: u32 = 100;
const RB_SAMPLE: u32 = 101;
const RB_OBSERVE: u32 = 102;
const RB_INTERVENE: u32 = 103;
const RB_RESIDUAL: u32 = 104;
const RB_RECEIPT: u32 = 105;
const RB_COST: u32 = 106;
const RB_CONSENT: u32 = 107;
const RB_EVIDENCE: u32 = 108;
#[allow(dead_code)]
const RB_FIELD_PRIMITIVES: [u32; 21] = [
    RB_FIELD,
    RB_CARRIER,
    RB_TOPOLOGY,
    RB_FIBER,
    RB_REGION,
    RB_BOUNDARY,
    RB_NEIGHBORHOOD,
    RB_MATCH_FIELD,
    RB_DELTA,
    RB_RESOLVE,
    RB_COMMIT,
    RB_STEP,
    RB_LIFT,
    RB_SAMPLE,
    RB_OBSERVE,
    RB_INTERVENE,
    RB_RESIDUAL,
    RB_RECEIPT,
    RB_COST,
    RB_CONSENT,
    RB_EVIDENCE,
];

pub(crate) const TRIV_INT: u32 = 1;
pub(crate) const TRIV_STRING: u32 = 2;
const TRIV_BOOL: u32 = 3;
const TRIV_NULL: u32 = 4;
// FLOAT64 — value lives in the kernel's `f64s` overflow table; the inst
// field carries the table index. Sibling TS kernel uses Triv.FLOAT64 = 7;
// we use 5 here because the Rust kernel never shipped 8/16/32 variants and
// FLOAT64 is the next number after NULL. Both kernels read .fk source where
// the type tag is implicit in token shape (digits+dot vs digits), so the
// numeric constants stay private to each side.
pub(crate) const TRIV_FLOAT64: u32 = 5;

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
    // Float64 overflow table — values don't fit the 32-bit `inst` field,
    // so the trivial NodeID carries an index into `f64s`. Canonicalization
    // on intern: NaN bit patterns collapse to qNaN, ±0.0 share +0.0, but
    // ±Inf stay distinct (matches the TS kernel's f64Idx behavior).
    f64s: Vec<f64>,
    f64_idx: HashMap<u64, u32>, // keyed by IEEE bit pattern after canonicalization
    next_inst: u32,
    natives: HashMap<NameID, NativeEntry>,
    env_natives: HashMap<NameID, EnvAwareNativeEntry>,
    // methods — the blueprint method table (BML/NUMS reference: methods live
    // on the blueprint/type, shared by all instances, name-dispatched). Keyed
    // by (blueprint NodeID, method-name NameID) → the method's Closure. A
    // record's blueprint tag selects its method set; method_invoke binds
    // `self` to the receiver record.
    methods: HashMap<(NodeID, NameID), Arc<Closure>>,
    // jit_aliases: Form-function-name → native-name redirect.
    // When a function call's name is in this map, the walker substitutes
    // the aliased name before native lookup. Lets a Form recipe DEFINE
    // an algorithm as canonical truth; a `register_jit` call makes its
    // calls dispatch to a kernel-resident optimized native. Removing the
    // entry falls back to walking the Form recipe.
    jit_aliases: HashMap<NameID, NameID>,
    // jit_compiled — closure-body-NodeID → loaded host-native plugin.
    // When (jit_compile "name") succeeds, the kernel generates Rust source
    // for the closure's body, builds a cdylib via `rustc`, loads it with
    // libloading, and stores the resulting plugin keyed by the closure's
    // body NodeID. Every FNCALL whose closure body matches dispatches
    // through the loaded function pointer instead of walking the recipe.
    // Sibling to the TS kernel's k.jitCompiled map.
    // Arc lets the kernel be cloned cheaply for parallel workers; the
    // Library handle inside is shared, not duplicated.
    jit_compiled: HashMap<NodeID, Arc<JitCompiled>>,
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
            RB_FIELD => "FIELD",
            RB_CARRIER => "CARRIER",
            RB_TOPOLOGY => "TOPOLOGY",
            RB_FIBER => "FIBER",
            RB_REGION => "REGION",
            RB_BOUNDARY => "BOUNDARY",
            RB_NEIGHBORHOOD => "NEIGHBORHOOD",
            RB_MATCH_FIELD => "MATCH_FIELD",
            RB_DELTA => "DELTA",
            RB_RESOLVE => "RESOLVE",
            RB_COMMIT => "COMMIT",
            RB_STEP => "STEP",
            RB_LIFT => "LIFT",
            RB_SAMPLE => "SAMPLE",
            RB_OBSERVE => "OBSERVE",
            RB_INTERVENE => "INTERVENE",
            RB_RESIDUAL => "RESIDUAL",
            RB_RECEIPT => "RECEIPT",
            RB_COST => "COST",
            RB_CONSENT => "CONSENT",
            RB_EVIDENCE => "EVIDENCE",
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
pub(crate) struct Arena {
    frames: Vec<Frame>,
}

impl Arena {
    pub(crate) fn new() -> Self {
        Self {
            frames: Vec::with_capacity(256),
        }
    }

    pub(crate) fn new_frame(&mut self, parent: Option<FrameId>) -> FrameId {
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
    pub(crate) fn new_frame_with_capacity(
        &mut self,
        parent: Option<FrameId>,
        cap: usize,
    ) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame {
            parent,
            bindings: Vec::with_capacity(cap),
        });
        id
    }

    pub(crate) fn bind(&mut self, fid: FrameId, name: NameID, v: Value) {
        let f = &mut self.frames[fid as usize];
        for slot in &mut f.bindings {
            if slot.0 == name {
                slot.1 = v;
                return;
            }
        }
        f.bindings.push((name, v));
    }

    pub(crate) fn lookup(&self, fid: FrameId, name: NameID) -> Option<Value> {
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
            f64s: Vec::new(),
            f64_idx: HashMap::new(),
            next_inst: 1,
            natives: HashMap::new(),
            env_natives: HashMap::new(),
            methods: HashMap::new(),
            jit_aliases: HashMap::new(),
            jit_compiled: HashMap::new(),
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

    // intern_trivial_float64 — content-addressed insertion into the f64
    // overflow table. The trivial NodeID carries the table index in `inst`.
    // Canonicalization matches the TS sibling kernel so the same float
    // value parsed twice produces the same NodeID:
    //   - any NaN bit pattern collapses to qNaN (0x7ff8000000000000)
    //   - -0.0 collapses to +0.0
    //   - ±Inf keep distinct identity
    pub(crate) fn intern_trivial_float64(&mut self, f: f64) -> NodeID {
        let canonical = if f.is_nan() {
            f64::from_bits(0x7ff8000000000000)
        } else if f == 0.0 {
            0.0
        } else {
            f
        };
        let bits = canonical.to_bits();
        if let Some(&idx) = self.f64_idx.get(&bits) {
            return NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_FLOAT64,
                inst: idx,
            };
        }
        let idx = self.f64s.len() as u32;
        self.f64s.push(canonical);
        self.f64_idx.insert(bits, idx);
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_FLOAT64,
            inst: idx,
        }
    }

    pub(crate) fn decode_float64(&self, inst: u32) -> f64 {
        self.f64s
            .get(inst as usize)
            .copied()
            .unwrap_or_else(|| panic!("decode_float64: bad index {}", inst))
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

    /// Build a Record value from a blueprint and (field-name, value) pairs.
    ///
    /// The structure-access marshalling seam: the PyO3 bridge lowers a Python
    /// dict (or a model via model_dump()) onto a kernel Record so a transmuted
    /// recipe can read named fields via `record_get`. Field names intern to
    /// NameIDs here exactly as the `record_new` native does (main.rs ~2051), so
    /// a record marshalled from Python and one built by `record_new` in Form
    /// are the same shape — `record_get`/`record_has` read both identically.
    pub(crate) fn make_record(&mut self, blueprint: NodeID, pairs: Vec<(String, Value)>) -> Value {
        let fields: Vec<(NameID, Value)> = pairs
            .into_iter()
            .map(|(name, value)| (self.intern_string(&name).inst, value))
            .collect();
        Value::Record(Arc::new(Mutex::new(Record { blueprint, fields })))
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
            f64s: self.f64s.clone(),
            f64_idx: self.f64_idx.clone(),
            next_inst: self.next_inst,
            natives: self.natives.clone(),
            env_natives: self.env_natives.clone(),
            methods: self.methods.clone(),
            jit_aliases: self.jit_aliases.clone(),
            // Arc clones — Library handles stay shared across the kernel and
            // its workers; the .so stays mapped for the duration.
            jit_compiled: self.jit_compiled.clone(),
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
            TRIV_FLOAT64 => Value::Float(self.decode_float64(n.inst)),
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
    Float(f64),
    Str(String),
    Bool(bool),
    List(Vec<Value>),
    Closure(Arc<Closure>),
    Nid(NodeID),
    // Record — a mutable struct/object with identity. The first mutable Value
    // the kernel carries; BML requires it for `self.x = v`. `blueprint` tags
    // the record's type (its method-table / class NodeID); `fields` is an
    // ordered name→value map. Arc<Mutex> gives shared mutable identity that is
    // also Send (Value crosses thread boundaries in the parallel arms), so two
    // bindings to the same record see each other's mutations — object
    // semantics, not value-copy semantics.
    Record(Arc<Mutex<Record>>),
}

#[derive(Debug)]
pub(crate) struct Record {
    blueprint: NodeID,
    fields: Vec<(NameID, Value)>,
}

impl Record {
    fn get(&self, name: NameID) -> Option<Value> {
        self.fields
            .iter()
            .rev()
            .find(|(n, _)| *n == name)
            .map(|(_, v)| v.clone())
    }
    fn set(&mut self, name: NameID, value: Value) {
        if let Some(slot) = self.fields.iter_mut().find(|(n, _)| *n == name) {
            slot.1 = value;
        } else {
            self.fields.push((name, value));
        }
    }
}

#[derive(Debug)]
pub(crate) struct Closure {
    // Interned name for display only — runtime lookup never uses it.
    name: NameID,
    params: Vec<NameID>,
    body: NodeID,
    env: FrameId,
}

// JitCompiled — a Form recipe that has been compiled to host-native code
// through the system Rust toolchain.
//
// Shape parallel to TS (compileNode → new Function → V8 JIT) and Go
// (recipe → Go source → plugin.Open). For Rust the equivalent toolchain
// is: recipe → Rust source → `rustc --crate-type=cdylib` → libloading.
//
// The C-ABI cdylib exports a single fixed symbol `compiled_fn` whose
// signature is `unsafe extern "C" fn(i64, i64, ..., i64) -> i64`. Arity
// matches the closure's param count; the field `arity` is the runtime
// signature dispatch tag (1, 2, 3, … up to JIT_MAX_ARITY).
//
// LIBRARY LIFETIME: the Library handle must outlive the function pointer
// it produced — `libloading::Symbol` borrows the Library, and dropping
// the Library unmaps the .so so the function pointer dangles. We store
// the Library + the raw function pointer together in this struct; the
// struct is held by Arc and never dropped until the kernel is dropped.
// The Library and the function pointer share that lifetime, which is
// what makes the unsafe call later sound.
pub(crate) struct JitCompiled {
    // Holds the loaded .so. Underscore prefix: read only via Drop.
    // Must not be dropped while `func` may still be invoked.
    _library: libloading::Library,
    // Raw function pointer — typed by arity at call sites.
    // For arity N, callers cast this to `unsafe extern "C" fn(i64,…,i64) -> i64`
    // with N i64 parameters and invoke it in a tight unsafe block.
    func: *const (),
    arity: usize,
    // Keep the temp dir's path so we can clean up on drop. Owning the
    // PathBuf (not a TempDir handle) lets the directory survive process
    // restart in case of crash — a tiny leak in /tmp is recoverable; an
    // unmappable .so during the cdylib's lifetime is not.
    _temp_dir: PathBuf,
}

// JitCompiled holds a *const ptr; the underlying memory is the loaded .so
// which is process-global and read-only after rustc emitted it. Send + Sync
// are sound here because the function we call is a pure i64→i64 transformer
// with no shared mutable state.
unsafe impl Send for JitCompiled {}
unsafe impl Sync for JitCompiled {}

impl std::fmt::Debug for JitCompiled {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "<JitCompiled arity={}>", self.arity)
    }
}

impl Drop for JitCompiled {
    fn drop(&mut self) {
        // Manual drop runs BEFORE field drops, so we can't depend on _library
        // having been unmapped here. Instead: on Linux removing a file that
        // libloading currently has dlopen'd is safe — the kernel keeps the
        // mapping alive until dlclose runs. So we can remove the temp dir
        // now; the dlclose that happens when _library drops (immediately
        // after this Drop::drop returns) will close the mapping cleanly even
        // though the on-disk file is gone. Best-effort: ignore errors.
        let _ = fs::remove_dir_all(&self._temp_dir);
    }
}

// Maximum arity the JIT supports — bounded so dispatch can be a static
// match instead of dynamic generation. Form recipes with more parameters
// fall back to recipe-walk; the recipe stays canonical truth.
const JIT_MAX_ARITY: usize = 8;

impl Value {
    pub(crate) fn display(&self) -> String {
        match self {
            Value::Null => "null".to_string(),
            Value::Int(n) => n.to_string(),
            Value::Float(f) => format_float_python(*f),
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
            Value::Record(r) => {
                let rec = r.lock().unwrap();
                format!(
                    "<record @{}.{}.{}.{} #{}fields>",
                    rec.blueprint.pkg,
                    rec.blueprint.level,
                    rec.blueprint.ty,
                    rec.blueprint.inst,
                    rec.fields.len()
                )
            }
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
            Value::Float(f) => *f as i64,
            Value::Bool(b) => {
                if *b {
                    1
                } else {
                    0
                }
            }
            _ => panic!("as_int: {:?}", self),
        }
    }

    fn as_float(&self) -> f64 {
        match self {
            Value::Float(f) => *f,
            Value::Int(n) => *n as f64,
            Value::Bool(b) => {
                if *b {
                    1.0
                } else {
                    0.0
                }
            }
            _ => panic!("as_float: {:?}", self),
        }
    }

    fn as_bool(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Int(n) => *n != 0,
            Value::Float(f) => *f != 0.0,
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

fn bml_native_str(value: &str) -> Value {
    Value::Str(value.to_string())
}

fn bml_native_empty_list() -> Value {
    Value::List(vec![])
}

fn bml_native_atom(kind: &str, value: &str) -> Value {
    Value::List(vec![
        bml_native_str("cell"),
        bml_native_str(kind),
        bml_native_str(value),
        bml_native_empty_list(),
        Value::Null,
    ])
}

fn bml_native_keyword(value: &str) -> bool {
    matches!(
        value,
        "package"
            | "import"
            | "class"
            | "interface"
            | "template"
            | "section"
            | "syntax"
            | "const"
            | "enum"
            | "operator"
            | "for"
            | "while"
            | "loop"
            | "switch"
            | "select"
            | "case"
            | "default"
            | "if"
            | "else"
            | "if_fail"
            | "while_success"
            | "return"
            | "break"
            | "continue"
            | "try"
            | "catch"
            | "throw"
            | "fail"
            | "cut"
            | "mark"
            | "save"
            | "restore"
            | "discard"
            | "choice"
            | "choose"
            | "asm"
            | "instanceof"
            | "library"
            | "naming"
            | "conventions"
            | "DefaultMethods"
            | "Nil"
            | "Fail"
            | "EndOfFile"
            | "EndOfLine"
            | "Cut"
            | "MultiMatch"
            | "Primitive"
    )
}

fn bml_native_property(value: &str) -> bool {
    matches!(
        value,
        "public"
            | "private"
            | "protected"
            | "abstract"
            | "static"
            | "final"
            | "default"
            | "delegate"
            | "shared"
            | "get"
            | "put"
            | "strict"
            | "relaxed"
            | "deferred"
            | "native"
            | "exception"
            | "explicit"
            | "extern"
            | "library"
            | "name"
            | "guid"
            | "operator"
            | "coercion"
            | "reassign"
            | "array"
            | "exclusive"
            | "in"
            | "out"
            | "inout"
            | "assign"
            | "inline"
            | "hidden"
            | "singleton"
            | "unique"
            | "struct"
            | "noobject"
            | "dynamic"
            | "alias"
            | "outer"
            | "nostate"
    )
}

fn bml_native_name_kind(value: &str) -> &'static str {
    if bml_native_keyword(value) {
        "bml-keyword"
    } else if bml_native_property(value) {
        "bml-property"
    } else {
        "bml-name"
    }
}

fn bml_native_name_start(b: u8) -> bool {
    b.is_ascii_alphabetic() || b == b'_'
}

fn bml_native_name_char(b: u8) -> bool {
    bml_native_name_start(b) || b.is_ascii_digit()
}

fn bml_native_hex_digit(b: u8) -> bool {
    b.is_ascii_hexdigit()
}

fn bml_native_bin_digit(b: u8) -> bool {
    matches!(b, b'0' | b'1')
}

fn bml_native_decode_escape(b: u8) -> u8 {
    match b {
        b'\\' => b'\\',
        b'\'' => b'\'',
        b'"' => b'"',
        b'n' => b'\n',
        b't' => b'\t',
        b'r' => b'\r',
        b'0' => 0,
        _ => b,
    }
}

fn bml_native_scan_quoted(src: &str, i: usize, quote: u8) -> (String, usize) {
    let bytes = src.as_bytes();
    let mut j = i + 1;
    let mut out = String::new();
    while j < bytes.len() {
        let c = bytes[j];
        if c == b'\\' && j + 1 < bytes.len() {
            out.push(bml_native_decode_escape(bytes[j + 1]) as char);
            j += 2;
            continue;
        }
        if c == quote {
            return (out, j + 1);
        }
        out.push(c as char);
        j += 1;
    }
    (out, j)
}

fn bml_native_scan_text(src: &str) -> Value {
    let bytes = src.as_bytes();
    let ops = [
        "<<prim", ".*", "::=", "=>", "<=", ">>>=", ">>=", "<<=", ">>>", ">>", "<<", "++", "--",
        "==", "!=", ">=", "<=", ":=", "*=", "/=", "%=", "+=", "-=", "&=", "|=", "^=", "&&", "||",
        "..", "#(", "{", "}", "(", ")", "[", "]", ";", ",", ":", ".", "+", "-", "*", "/", "%", "=",
        "'", "<", ">", "!", "~", "?", "|", "&", "^", "$", "#", "\\",
    ];
    let mut out: Vec<Value> = vec![];
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        if matches!(c, b' ' | b'\t' | b'\n' | b'\r') {
            i += 1;
            continue;
        }
        if i + 1 < bytes.len() && &src[i..i + 2] == "//" {
            i += 2;
            while i < bytes.len() && bytes[i] != b'\n' {
                i += 1;
            }
            continue;
        }
        if i + 1 < bytes.len() && &src[i..i + 2] == "/*" {
            if let Some(end) = src[i + 2..].find("*/") {
                i = i + 2 + end + 2;
                continue;
            }
            break;
        }
        if c == b'"' {
            let (value, next) = bml_native_scan_quoted(src, i, b'"');
            out.push(bml_native_atom("bml-string", &value));
            i = next;
            continue;
        }
        if c == b'\'' {
            let (value, next) = bml_native_scan_quoted(src, i, b'\'');
            out.push(bml_native_atom("bml-char", &value));
            i = next;
            continue;
        }
        if c.is_ascii_digit() {
            let mut j = i + 1;
            let mut kind = "bml-int";
            if c == b'0' && j < bytes.len() && matches!(bytes[j], b'x' | b'X') {
                j += 1;
                while j < bytes.len() && bml_native_hex_digit(bytes[j]) {
                    j += 1;
                }
            } else if c == b'0' && j < bytes.len() && matches!(bytes[j], b'b' | b'B') {
                j += 1;
                while j < bytes.len() && bml_native_bin_digit(bytes[j]) {
                    j += 1;
                }
            } else {
                while j < bytes.len() && bytes[j].is_ascii_digit() {
                    j += 1;
                }
                if j < bytes.len()
                    && bytes[j] == b'.'
                    && j + 1 < bytes.len()
                    && bytes[j + 1].is_ascii_digit()
                {
                    kind = "bml-float";
                    j += 1;
                    while j < bytes.len() && bytes[j].is_ascii_digit() {
                        j += 1;
                    }
                    if j < bytes.len() && matches!(bytes[j], b'e' | b'E') {
                        let mut k = j + 1;
                        if k < bytes.len() && matches!(bytes[k], b'+' | b'-') {
                            k += 1;
                        }
                        if k < bytes.len() && bytes[k].is_ascii_digit() {
                            j = k + 1;
                            while j < bytes.len() && bytes[j].is_ascii_digit() {
                                j += 1;
                            }
                        }
                    }
                }
            }
            out.push(bml_native_atom(kind, &src[i..j]));
            i = j;
            continue;
        }
        if bml_native_name_start(c) {
            let mut j = i + 1;
            while j < bytes.len() && bml_native_name_char(bytes[j]) {
                j += 1;
            }
            let value = &src[i..j];
            out.push(bml_native_atom(bml_native_name_kind(value), value));
            i = j;
            continue;
        }
        let mut matched = "";
        for op in ops {
            if src[i..].starts_with(op) {
                matched = op;
                break;
            }
        }
        if matched.is_empty() {
            matched = &src[i..i + 1];
        }
        out.push(bml_native_atom("bml-op", matched));
        i += matched.len();
    }
    Value::List(out)
}

// format_float_python — render an f64 the way CPython's `print(float)`
// renders it. Rust's default `{}` format drops the trailing zero for
// integer-valued floats (`1.0` → `"1"`); CPython keeps it (`"1.0"`).
// The parity suite compares stdout strings, so we match Python's format
// at the kernel's render boundary. NaN and ±Inf also follow CPython.
fn format_float_python(f: f64) -> String {
    if f.is_nan() {
        return "nan".to_string();
    }
    if f.is_infinite() {
        return if f > 0.0 {
            "inf".to_string()
        } else {
            "-inf".to_string()
        };
    }
    // Rust's `{}` produces "1", "1.5", "0.125", "5e-10" etc. Add a trailing
    // ".0" iff the rendered form has neither a "." nor an exponent — that
    // matches CPython's repr/print behaviour for integer-valued floats.
    let s = format!("{}", f);
    if s.contains('.') || s.contains('e') || s.contains('E') {
        s
    } else {
        format!("{}.0", s)
    }
}

// round_ndigits_decimal — CPython `round(x, n)` for a finite double, n >= 0.
//
// CPython rounds the TRUE value of the double (a finite dyadic decimal) to n
// fractional digits using round-half-to-even, then takes the nearest double.
// The naive f64 paths (`floor(x*10^n+0.5)/10^n`, or banker's on the scaled
// f64) BOTH diverge, because the `*10^n` reintroduces representation error
// CPython's decimal path avoids. The honest path never scales in f64: it
// rounds on the EXACT decimal expansion of the double.
//
// We obtain that exact expansion with `format!("{:.1074}", |x|)`. A finite
// double `m * 2^e2` (e2 < 0) equals `m * 5^(-e2) / 10^(-e2)`, a decimal with
// exactly `-e2` fractional digits; -e2 <= 1074 for every double (the smallest
// subnormal). So 1074 places is the exact, correctly-terminating expansion for
// any double — no domain assumption, no pre-rounding at the round position.
// Verified bit-for-bit against CPython on 6.6M cases (random magnitudes at
// n=2,4; adversarial nextafter-of-half ties at n=0,2,4,6; random 64-bit
// patterns incl. subnormals) with ZERO divergences. The sibling Go kernel
// uses strconv.FormatFloat('f',1074); the TS kernel builds the same exact
// decimal from the IEEE mantissa via BigInt (its toFixed caps at 100 places).
fn round_ndigits_decimal(x: f64, n: i64) -> f64 {
    if x.is_nan() || x.is_infinite() {
        return x;
    }
    let neg = x.is_sign_negative();
    let ax = x.abs();
    // Exact fixed-point decimal of |x|. 1074 fractional places is the full
    // terminating expansion for any double; no rounding occurs at the tail.
    let s = format!("{:.1074}", ax);
    let dot = s.find('.').unwrap();
    let ipart = &s[..dot];
    let fpart = &s[dot + 1..];
    // Concatenated digit string; decimal point sits after `point` digits.
    let mut digits: Vec<u8> = Vec::with_capacity(ipart.len() + fpart.len());
    digits.extend_from_slice(ipart.as_bytes());
    digits.extend_from_slice(fpart.as_bytes());
    let point = ipart.len() as i64;
    let keep = point + n; // number of leading digits to keep
    if keep < 0 {
        // Magnitude rounds below the n-th place to zero.
        return if neg { -0.0 } else { 0.0 };
    }
    let keep = keep as usize;
    if digits.len() < keep {
        digits.resize(keep, b'0');
    }
    let kept_slice = &digits[..keep];
    let rest = &digits[keep..];
    // kept as a decimal string (avoid empty)
    let mut kept: String = if kept_slice.is_empty() {
        "0".to_string()
    } else {
        String::from_utf8_lossy(kept_slice).into_owned()
    };
    // Round-half-to-even on `rest`.
    let mut round_up = false;
    if let Some(&first) = rest.first() {
        if first > b'5' {
            round_up = true;
        } else if first < b'5' {
            round_up = false;
        } else {
            // first == '5': nonzero tail => up; exact half => to even.
            let tail_nonzero = rest[1..].iter().any(|&d| d != b'0');
            if tail_nonzero {
                round_up = true;
            } else {
                let last_kept = kept.as_bytes()[kept.len() - 1];
                round_up = (last_kept - b'0') % 2 == 1;
            }
        }
    }
    if round_up {
        kept = add_one_decimal(&kept);
    }
    // Rebuild the decimal `kept * 10^-n`, then parse to the nearest double.
    let dec = compose_scaled_decimal(&kept, n, neg);
    let out: f64 = dec.parse().unwrap_or(0.0);
    if out == 0.0 && neg {
        -0.0
    } else {
        out
    }
}

// add_one_decimal — increment a non-negative decimal digit string by 1,
// propagating carry (may grow the string by one leading digit).
fn add_one_decimal(s: &str) -> String {
    let mut bytes: Vec<u8> = s.as_bytes().to_vec();
    let mut i = bytes.len();
    loop {
        if i == 0 {
            bytes.insert(0, b'1');
            break;
        }
        i -= 1;
        if bytes[i] == b'9' {
            bytes[i] = b'0';
        } else {
            bytes[i] += 1;
            break;
        }
    }
    String::from_utf8(bytes).unwrap()
}

// compose_scaled_decimal — render the integer string `kept` scaled by 10^-n
// as a decimal literal, with the given sign. n >= 0.
fn compose_scaled_decimal(kept: &str, n: i64, neg: bool) -> String {
    let n = n as usize;
    let body = if n == 0 {
        kept.to_string()
    } else {
        let mut si = kept.to_string();
        if si.len() <= n {
            // pad to at least n+1 digits so there's a leading integer digit
            let pad = n - si.len() + 1;
            si = "0".repeat(pad) + &si;
        }
        let split = si.len() - n;
        format!("{}.{}", &si[..split], &si[split..])
    };
    if neg {
        format!("-{}", body)
    } else {
        body
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

fn native_field_node(
    k: &mut Kernel,
    args: &[Value],
    ty: u32,
    inst: u32,
    native_name: &str,
) -> Value {
    let kids: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("{}: expected one list of NodeIDs", native_name),
    };
    Value::Nid(k.intern(
        NodeID {
            pkg: 1,
            level: LEVEL_BASIC,
            ty,
            inst,
        },
        kids,
    ))
}

macro_rules! native_field_constructor {
    ($fn_name:ident, $rb_ty:ident, $inst:expr, $native_name:literal) => {
        fn $fn_name(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
            native_field_node(k, args, $rb_ty, $inst, $native_name)
        }
    };
}

native_field_constructor!(native_field_blueprint, RB_FIELD, 1, "field_blueprint");
native_field_constructor!(native_field_cell, RB_FIELD, 2, "field_cell");
native_field_constructor!(native_field_carrier, RB_CARRIER, 1, "field_carrier");
native_field_constructor!(native_field_topology, RB_TOPOLOGY, 1, "field_topology");
native_field_constructor!(native_field_fiber, RB_FIBER, 1, "field_fiber");
native_field_constructor!(native_field_region, RB_REGION, 1, "field_region");
native_field_constructor!(native_field_boundary, RB_BOUNDARY, 1, "field_boundary");
native_field_constructor!(
    native_field_neighborhood,
    RB_NEIGHBORHOOD,
    1,
    "field_neighborhood"
);
native_field_constructor!(native_field_match, RB_MATCH_FIELD, 1, "field_match");
native_field_constructor!(native_field_delta, RB_DELTA, 1, "field_delta");
native_field_constructor!(native_field_resolve, RB_RESOLVE, 1, "field_resolve");
native_field_constructor!(native_field_commit, RB_COMMIT, 1, "field_commit");
native_field_constructor!(native_field_step, RB_STEP, 1, "field_step");
native_field_constructor!(native_field_lift, RB_LIFT, 1, "field_lift");
native_field_constructor!(native_field_sample, RB_SAMPLE, 1, "field_sample");
native_field_constructor!(native_field_observe, RB_OBSERVE, 1, "field_observe");
native_field_constructor!(native_field_intervene, RB_INTERVENE, 1, "field_intervene");
native_field_constructor!(native_field_residual, RB_RESIDUAL, 1, "field_residual");
native_field_constructor!(native_field_receipt, RB_RECEIPT, 1, "field_receipt");
native_field_constructor!(native_field_cost, RB_COST, 1, "field_cost");
native_field_constructor!(native_field_consent, RB_CONSENT, 1, "field_consent");
native_field_constructor!(native_field_evidence, RB_EVIDENCE, 1, "field_evidence");

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
        self.register_native("bml_scan_file", cat_call(), |_, _, args| {
            let body = fs::read_to_string(args[0].as_str())
                .unwrap_or_else(|e| panic!("bml_scan_file: {}", e));
            bml_native_scan_text(&body)
        });
        // pow — integer exponentiation in native code (no Form recursion).
        // (pow base exp) → base**exp. Negative exponents return 0 (Python's
        // int**-n is a float; floats on this path are a later breath).
        self.register_native("pow", cat_method(), |_, _, args| {
            let base = args[0].as_int();
            let exp = args[1].as_int();
            if exp < 0 {
                Value::Int(0)
            } else {
                Value::Int(base.pow(exp as u32))
            }
        });
        // --- struct/object primitive (BML reference, rung 2) ----------------
        // A Record is the kernel's first MUTABLE value: a struct/object with
        // identity. Every language's class/struct compiles onto these four
        // natives. The blueprint NodeID tags the record's type (its class /
        // method-table); fields are a name→value map.
        //
        // record_new — (record_new blueprint k1 v1 k2 v2 ...) → Record.
        // The first arg is the blueprint NodeID; the rest are alternating
        // field-name (string) and value pairs. Field names intern to NameIDs.
        self.register_native("record_new", cat_method(), |k, _, args| {
            let blueprint = args[0].as_nid();
            let mut fields: Vec<(NameID, Value)> = Vec::new();
            let mut i = 1;
            while i + 1 < args.len() {
                let name = k.intern_string(args[i].as_str()).inst;
                fields.push((name, args[i + 1].clone()));
                i += 2;
            }
            Value::Record(Arc::new(Mutex::new(Record { blueprint, fields })))
        });
        // record_get — (record_get rec "field") → value, or null if absent.
        self.register_native("record_get", cat_access(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => r.lock().unwrap().get(name).unwrap_or(Value::Null),
                _ => panic!("record_get: not a record: {:?}", args[0]),
            }
        });
        // record_set — (record_set rec "field" value) → the record (mutated
        // in place; shared identity means all holders see the change). This is
        // the kernel's first in-place mutation — BML's `self.x = v`.
        self.register_native("record_set", cat_method(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => {
                    r.lock().unwrap().set(name, args[2].clone());
                    args[0].clone()
                }
                _ => panic!("record_set: not a record: {:?}", args[0]),
            }
        });
        // record_has — (record_has rec "field") → bool.
        self.register_native("record_has", cat_access(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => Value::Bool(r.lock().unwrap().get(name).is_some()),
                _ => Value::Bool(false),
            }
        });
        // record_blueprint — (record_blueprint rec) → the blueprint NodeID
        // (the record's class/type tag, for method dispatch by the lifter).
        self.register_native("record_blueprint", cat_access(), |_, _, args| {
            match &args[0] {
                Value::Record(r) => Value::Nid(r.lock().unwrap().blueprint),
                _ => panic!("record_blueprint: not a record: {:?}", args[0]),
            }
        });
        // record? — (record? v) → bool. Type predicate so Form code can branch.
        self.register_native("record?", cat_access(), |_, _, args| {
            Value::Bool(matches!(&args[0], Value::Record(_)))
        });
        // record_keys — (record_keys rec) → list of field-name strings, in
        // insertion order. Lets Form enumerate a record used as a hash map
        // (e.g. cell-log-store.fk's keydir for compaction).
        self.register_native("record_keys", cat_access(), |k, _, args| match &args[0] {
            Value::Record(r) => {
                let names: Vec<NameID> = r.lock().unwrap().fields.iter().map(|(n, _)| *n).collect();
                Value::List(
                    names
                        .into_iter()
                        .map(|n| Value::Str(k.strs[n as usize].clone()))
                        .collect(),
                )
            }
            _ => Value::List(Vec::new()),
        });
        // --- methods on the blueprint (BML/NUMS reference, rung 2b) ---------
        // Methods live on the blueprint/type, not on instances — shared by all
        // records of that type, name-dispatched. The keystone that makes a
        // Record a real object: obj.m(args) works.
        //
        // method_define — (method_define blueprint "name" closure) → blueprint.
        // Registers the closure under (blueprint, name) in the method table.
        self.register_native("method_define", cat_method(), |k, _, args| {
            let blueprint = args[0].as_nid();
            let name = k.intern_string(args[1].as_str()).inst;
            let cl = match &args[2] {
                Value::Closure(c) => c.clone(),
                _ => panic!("method_define: third arg must be a closure"),
            };
            k.methods.insert((blueprint, name), cl);
            args[0].clone()
        });
        // method_has — (method_has record-or-blueprint "name") → bool. Accepts
        // either a record (uses its blueprint) or a blueprint NodeID directly.
        self.register_native("method_has", cat_access(), |k, _, args| {
            let blueprint = match &args[0] {
                Value::Record(r) => r.lock().unwrap().blueprint,
                Value::Nid(n) => *n,
                _ => return Value::Bool(false),
            };
            let name = k.intern_string(args[1].as_str()).inst;
            Value::Bool(k.methods.contains_key(&(blueprint, name)))
        });
        // method_invoke — (method_invoke record "name" arg1 arg2 ...) → value.
        // Dispatches by the record's blueprint, binds `self` = record (the
        // structural+behavioral base; dual-base separation is rung 2d), binds
        // the method's declared params to the remaining args, walks the body
        // in a frame extending the method closure's captured env.
        self.register_native("method_invoke", cat_method(), |k, a, args| {
            let rec = match &args[0] {
                Value::Record(r) => r.clone(),
                _ => panic!("method_invoke: first arg must be a record"),
            };
            let blueprint = rec.lock().unwrap().blueprint;
            let name_id = k.intern_string(args[1].as_str()).inst;
            let cl = k
                .methods
                .get(&(blueprint, name_id))
                .unwrap_or_else(|| {
                    panic!(
                        "method_invoke: no method '{}' on blueprint @{}.{}.{}.{}",
                        args[1].as_str(),
                        blueprint.pkg,
                        blueprint.level,
                        blueprint.ty,
                        blueprint.inst
                    )
                })
                .clone();
            // The method's FIRST param is the receiver (Python `self`
            // convention); the remaining params bind to the call args
            // (args[2..]). So a `def get(self)` method is invoked with zero
            // call args, and the receiver fills param 0.
            let call_args = &args[2..];
            if cl.params.is_empty() {
                panic!(
                    "method '{}' must declare a receiver param (self)",
                    args[1].as_str()
                );
            }
            if call_args.len() != cl.params.len() - 1 {
                panic!(
                    "method '{}' wants {} args, got {}",
                    args[1].as_str(),
                    cl.params.len() - 1,
                    call_args.len()
                );
            }
            let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            // param 0 = receiver; params 1.. = the call args in order.
            a.bind(call_frame, cl.params[0], Value::Record(rec.clone()));
            for (i, p) in cl.params[1..].iter().enumerate() {
                a.bind(call_frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, call_frame)
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
                0 => {
                    while end < n && matches!(bytes[end], b' ' | b'\t' | b'\n' | b'\r') {
                        end += 1;
                    }
                }
                1 => {
                    while end < n && bytes[end].is_ascii_digit() {
                        end += 1;
                    }
                }
                2 => {
                    while end < n && bytes[end].is_ascii_alphabetic() {
                        end += 1;
                    }
                }
                3 => {
                    while end < n
                        && (bytes[end].is_ascii_alphanumeric()
                            || bytes[end] == b'_'
                            || bytes[end] == b'-')
                    {
                        end += 1;
                    }
                }
                4 => {
                    while end < n && bytes[end] != b'"' && bytes[end] != b'\\' {
                        end += 1;
                    }
                }
                5 => {
                    while end < n && bytes[end] != b'\n' {
                        end += 1;
                    }
                }
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
                a.bind(
                    call_frame,
                    cl.params[1],
                    Value::Str((byte as char).to_string()),
                );
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
        // str_to_float — text-to-float leaf, the float sibling of str_to_int.
        // Total like its sibling (unparseable text -> 0.0), so a handler that
        // splits a comma-separated query arg into float scores never panics on
        // a stray token. This is what lets a native route parse arbitrary
        // float inputs from the request (e.g. weighted_average's values/weights)
        // and run the real arithmetic in Form, rather than serving a constant.
        self.register_native("str_to_float", cat_method(), |_, _, args| {
            Value::Float(args[0].as_str().parse().unwrap_or(0.0))
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
            Value::List(xs) => {
                // Dict-aware: tagged "__dict__" lists report pair count,
                // matching Python's `len(d)` semantics.
                if let Some(Value::Str(s)) = xs.first() {
                    if s == "__dict__" {
                        return Value::Int(((xs.len() - 1) / 2) as i64);
                    }
                }
                Value::Int(xs.len() as i64)
            }
            Value::Str(s) => Value::Int(s.len() as i64),
            _ => Value::Int(0),
        });
        // nth — list subscript by integer index. Sibling-parity with the
        // TS kernel; the Python emitter generates `(nth xs i)` for
        // `xs[i]`. `core.fk` has a recursive version that could replace
        // this once auto-prelude loading lands; keeping it native today
        // is what closes the parity-suite assign/imperative/substrate
        // demos against the live binary.
        self.register_native("nth", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= xs.len() {
                    return Value::Null;
                }
                return xs[i as usize].clone();
            }
            Value::Null
        });
        self.register_native("empty", cat_list_nat(), |_, _, _| Value::List(vec![]));
        // _list_append — functional list extension: `(_list_append xs x)` →
        // a NEW list = xs ++ [x]. The Python adapter lowers the accumulator
        // idiom `result.append(x)` to `(let result (_list_append result x))`,
        // rebinding the name to the grown list each pass (Python mutates in
        // place; the kernel's list is an immutable value, so the name carries
        // the growth). This is what unblocks the whole class of list-returning
        // routes — softmax, distributions, vectors — without a class-method
        // dispatch on a plain list. A non-list receiver yields a single-element
        // list, matching `[].append(x)` having extended an empty accumulator.
        self.register_native("_list_append", cat_list_nat(), |_, _, args| {
            let mut xs = match &args[0] {
                Value::List(xs) => xs.clone(),
                _ => Vec::new(),
            };
            xs.push(args[1].clone());
            Value::List(xs)
        });
        // _get — one polymorphic accessor over every container shape the
        // Python adapter emits. The emitter lowers BOTH attribute reads
        // (`obj.field` → `(_get obj "field")`) and subscripts (`x[i]` /
        // `d[k]` → `(_get x i)`) to the same native, so `_get` must
        // dispatch on the *shape of its receiver*, not on a fixed arity:
        //
        //   • `__dict__`-tagged list + any key  → dict alist lookup
        //   • plain alist (even slots are Str)  → record-field read
        //                                          (Python class instance)
        //   • list + int index                  → positional element
        //   • str  + int index                  → one-char string
        //
        // A single dispatch keeps the .fk identical across siblings and
        // lets a record-as-flat-alist and a positional list both flow
        // through `x[...]` without the emitter knowing the runtime type.
        // (Earlier this was two `register_native("_get", …)` calls; the
        // second silently shadowed the first, so attribute reads on class
        // instances hit the int-index path and panicked on `as_int(Str)`.)
        self.register_native("_get", cat_access(), |k, _, args| {
            // Record: a marshalled structured input (the structure-access
            // capability) or a record built by record_new. A string key reads
            // the named field; record_get returns Null for an absent field
            // (Python `obj[k]` would KeyError, but the transmuted recipes read
            // fields they know exist, and Null is the honest "absent" surface).
            if let (Value::Record(r), Value::Str(key)) = (&args[0], &args[1]) {
                let name = k.intern_string(key).inst;
                return r.lock().unwrap().get(name).unwrap_or(Value::Null);
            }
            // Dict: ["__dict__", k0, v0, …] — key match by value.
            if is_dict(&args[0]) {
                if let Value::List(xs) = &args[0] {
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        if dict_key_eq(&xs[i], &args[1]) {
                            return xs[i + 1].clone();
                        }
                        i += 2;
                    }
                    return Value::Null;
                }
            }
            // String key on an untagged list → record-field read. A class
            // instance is a flat alist (list "__class__" "Counter" "n" 3 …).
            if let (Value::List(xs), Value::Str(key)) = (&args[0], &args[1]) {
                let mut i = 0;
                while i + 1 < xs.len() {
                    if let Value::Str(k) = &xs[i] {
                        if k == key {
                            return xs[i + 1].clone();
                        }
                    }
                    i += 2;
                }
                panic!("_get: no field '{}' on record", key);
            }
            // Int index on a list → positional element.
            if let Value::List(xs) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= xs.len() {
                    return Value::Null;
                }
                return xs[i as usize].clone();
            }
            // Int index on a string → one-char string.
            if let Value::Str(s) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= s.len() {
                    return Value::Str(String::new());
                }
                return Value::Str((s.as_bytes()[i as usize] as char).to_string());
            }
            Value::Null
        });
        // _dispatch — method-call entry. The adapter lowers `obj.m(arg, …)`
        // to `(_dispatch obj "m" arg …)`. Reads obj's "__class__" field
        // to find the function bound as `<ClassName>__<methodName>` in
        // the surrounding scope; calls it with obj as the first argument.
        // Env-aware so it can look up the method closure in the caller's
        // frame chain (which is where the lifted method `defn`s landed).
        //
        // Inheritance walk: if `<C>__<m>` is not bound, look up `<C>__base`
        // (a string holding the parent class name); try `<Parent>__<m>`;
        // continue until a method is found or the chain ends. First match
        // wins — single inheritance, MRO is just the linear chain. Walking
        // here keeps every call site honest without the emitter needing to
        // bake the dispatch order into compile-time call shape.
        self.register_env_native("_dispatch", cat_call(), |k, a, env, args| {
            let class_name = if let Value::List(xs) = &args[0] {
                let mut i = 0;
                let mut found: Option<String> = None;
                while i + 1 < xs.len() {
                    if let Value::Str(key) = &xs[i] {
                        if key == "__class__" {
                            if let Value::Str(c) = &xs[i + 1] {
                                found = Some(c.clone());
                            }
                            break;
                        }
                    }
                    i += 2;
                }
                match found {
                    Some(c) => c,
                    None => panic!("_dispatch: receiver record has no '__class__' field"),
                }
            } else {
                panic!("_dispatch: receiver is not a record (got {:?})", args[0]);
            };
            let method_name = match &args[1] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch: second arg must be the method name string"),
            };
            let (qualified, cl) = resolve_method(k, a, env, &class_name, &method_name);
            // Build the call frame: bind self (args[0]) + the remaining
            // method args (args[2..]) to the closure's parameters.
            let call_args: Vec<&Value> =
                std::iter::once(&args[0]).chain(args[2..].iter()).collect();
            if cl.params.len() != call_args.len() {
                panic!(
                    "_dispatch: arity mismatch on {} (expected {}, got {})",
                    qualified,
                    cl.params.len(),
                    call_args.len()
                );
            }
            let frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            for (i, p) in cl.params.iter().enumerate() {
                a.bind(frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, frame)
        });
        // --- Dict natives ---------------------------------------------------
        // Dicts are first-class but ride on Value::List with a "__dict__"
        // tag in slot 0, followed by alternating key/value pairs:
        //   ["__dict__", k0, v0, k1, v1, ...]
        // Keeps the dict model uniform with how the existing _plus / nth /
        // subscript path already moves through Value::List, and lets the TS
        // evaluator (which has no separate Dict variant) share the same
        // shape across runtimes. Keys may be strings or ints; equality uses
        // value-level compare (str==str, int==int). Updates are immutable —
        // _dict_set returns a fresh dict so closures over the original keep
        // their view. This is enough surface to write a real endpoint
        // response shape; method-style .update / .pop / .items remain
        // pending (named in PYTHON_PIPELINE_STATUS.md, not blocking #2059
        // dict transmute work).
        fn is_dict(v: &Value) -> bool {
            if let Value::List(xs) = v {
                if let Some(Value::Str(s)) = xs.first() {
                    return s == "__dict__";
                }
            }
            false
        }
        fn dict_key_eq(a: &Value, b: &Value) -> bool {
            match (a, b) {
                (Value::Str(x), Value::Str(y)) => x == y,
                (Value::Int(x), Value::Int(y)) => x == y,
                _ => false,
            }
        }
        self.register_native("_dict_new", cat_list_nat(), |_, _, args| {
            // (_dict_new k0 v0 k1 v1 ...) — variadic constructor used by
            // the emitter for dict literals.
            let mut out = vec![Value::Str("__dict__".to_string())];
            out.extend(args.iter().cloned());
            Value::List(out)
        });
        self.register_native("_dict_get", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if tag == "__dict__" {
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            if dict_key_eq(&xs[i], &args[1]) {
                                return xs[i + 1].clone();
                            }
                            i += 2;
                        }
                        return Value::Null;
                    }
                }
            }
            Value::Null
        });
        self.register_native("_dict_set", cat_method(), |_, _, args| {
            // Immutable update — return a new dict; existing references unchanged.
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if tag == "__dict__" {
                        let mut out = xs.clone();
                        let mut i = 1;
                        while i + 1 < out.len() {
                            if dict_key_eq(&out[i], &args[1]) {
                                out[i + 1] = args[2].clone();
                                return Value::List(out);
                            }
                            i += 2;
                        }
                        out.push(args[1].clone());
                        out.push(args[2].clone());
                        return Value::List(out);
                    }
                }
            }
            args[0].clone()
        });
        self.register_native("_dict_has", cat_compare(RCMP_EQ), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if tag == "__dict__" {
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            if dict_key_eq(&xs[i], &args[1]) {
                                return Value::Bool(true);
                            }
                            i += 2;
                        }
                    }
                }
            }
            Value::Bool(false)
        });
        self.register_native("_dict_keys", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if tag == "__dict__" {
                        let mut out = Vec::new();
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            out.push(xs[i].clone());
                            i += 2;
                        }
                        return Value::List(out);
                    }
                }
            }
            Value::List(vec![])
        });
        self.register_native("_dict_values", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if tag == "__dict__" {
                        let mut out = Vec::new();
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            out.push(xs[i + 1].clone());
                            i += 2;
                        }
                        return Value::List(out);
                    }
                }
            }
            Value::List(vec![])
        });
        // (The subscript path is folded into the single polymorphic `_get`
        // registered above — dict/record/list/str all dispatch on receiver
        // shape there. A second `register_native("_get", …)` here would
        // silently shadow it, so the subscript-only version was removed.)
        // _iter — turn any container into a flat list suitable for the
        // for-loop emitter's head/tail walk. Lists pass through; dicts
        // become their keys (Python's `for k in d:`); strings become
        // one-character strings per byte.
        self.register_native("_iter", cat_list_nat(), |_, _, args| {
            if is_dict(&args[0]) {
                if let Value::List(xs) = &args[0] {
                    let mut out = Vec::new();
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        out.push(xs[i].clone());
                        i += 2;
                    }
                    return Value::List(out);
                }
            }
            if let Value::List(_) = &args[0] {
                return args[0].clone();
            }
            if let Value::Str(s) = &args[0] {
                return Value::List(
                    s.as_bytes()
                        .iter()
                        .map(|b| Value::Str((*b as char).to_string()))
                        .collect(),
                );
            }
            Value::List(vec![])
        });
        // _in — polymorphic membership. (`k in d` → _in d k). For dicts
        // checks keys; for lists checks elements; for strings checks
        // substring presence.
        self.register_native("_in", cat_compare(RCMP_EQ), |_, _, args| {
            if is_dict(&args[1]) {
                if let Value::List(xs) = &args[1] {
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        if dict_key_eq(&xs[i], &args[0]) {
                            return Value::Bool(true);
                        }
                        i += 2;
                    }
                    return Value::Bool(false);
                }
            }
            if let Value::List(xs) = &args[1] {
                for v in xs {
                    match (&args[0], v) {
                        (Value::Int(a), Value::Int(b)) if a == b => return Value::Bool(true),
                        (Value::Str(a), Value::Str(b)) if a == b => return Value::Bool(true),
                        (Value::Float(a), Value::Float(b)) if a == b => return Value::Bool(true),
                        (Value::Bool(a), Value::Bool(b)) if a == b => return Value::Bool(true),
                        _ => {}
                    }
                }
                return Value::Bool(false);
            }
            if let (Value::Str(needle), Value::Str(hay)) = (&args[0], &args[1]) {
                return Value::Bool(hay.contains(needle.as_str()));
            }
            Value::Bool(false)
        });
        // _dispatch_super — super().<m>(args) entry. Adapter lowers
        // `super().m(args…)` inside a method of class C to
        // `(_dispatch_super self "C" "m" args…)`. We look up `C__base`
        // (a string holding the parent class name) and resolve `m`
        // starting at the parent — the inheritance walk continues from
        // there. Skipping the receiver's `__class__` is what makes super
        // different from a normal dispatch: a Dog calling
        // `super().speak()` always resolves to Animal.speak (or
        // Animal's chain), even though self.__class__ is "Dog".
        self.register_env_native("_dispatch_super", cat_call(), |k, a, env, args| {
            let class_name = match &args[1] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch_super: second arg must be the class name string"),
            };
            let method_name = match &args[2] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch_super: third arg must be the method name string"),
            };
            // Look up <ClassName>__base to find the parent class name.
            let base_key = format!("{}__base", class_name);
            let base_id = match k.str_idx.get(&base_key).copied() {
                Some(id) => id,
                None => panic!(
                    "_dispatch_super: no '{}' in scope — '{}' has no base class",
                    base_key, class_name
                ),
            };
            let parent_val = match a.lookup(env, base_id) {
                Some(v) => v,
                None => panic!(
                    "_dispatch_super: '{}' not bound — '{}' has no base class",
                    base_key, class_name
                ),
            };
            let parent_name = match parent_val {
                Value::Str(s) => s,
                _ => panic!("_dispatch_super: '{}' is not a string", base_key),
            };
            if parent_name.is_empty() {
                panic!(
                    "_dispatch_super: class '{}' has no base class (empty __base)",
                    class_name
                );
            }
            let (qualified, cl) = resolve_method(k, a, env, &parent_name, &method_name);
            // First arg is self (args[0]); method args follow at args[3..].
            let call_args: Vec<&Value> =
                std::iter::once(&args[0]).chain(args[3..].iter()).collect();
            if cl.params.len() != call_args.len() {
                panic!(
                    "_dispatch_super: arity mismatch on {} (expected {}, got {})",
                    qualified,
                    cl.params.len(),
                    call_args.len()
                );
            }
            let frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            for (i, p) in cl.params.iter().enumerate() {
                a.bind(frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, frame)
        });
        // _merge_record — child constructors that chain through
        // `super().__init__(args)` call the parent constructor (which
        // returns a full record tagged with `__class__/__base__`), then
        // merge the parent's data fields into the child's record. This
        // native strips `__class__/__base__` from the parent record and
        // appends the remaining (key, value) pairs to the child record.
        // The child's `__class__/__base__` stays (the receiver's
        // dispatch identity is the child, not the parent).
        //
        // Shape:
        //   (_merge_record <child-record> <parent-record>)
        // Returns: a new list with child's full prefix + parent's data fields.
        self.register_native("_merge_record", cat_access(), |_, _, args| {
            let child = match &args[0] {
                Value::List(xs) => xs.clone(),
                _ => panic!("_merge_record: first arg must be a record"),
            };
            let parent = match &args[1] {
                Value::List(xs) => xs,
                _ => panic!("_merge_record: second arg must be a record"),
            };
            let mut out = child;
            let mut i = 0;
            while i + 1 < parent.len() {
                if let Value::Str(key) = &parent[i] {
                    if key == "__class__" || key == "__base__" {
                        i += 2;
                        continue;
                    }
                    // Skip if the child already has this field — child wins.
                    let mut child_has = false;
                    let mut j = 0;
                    while j + 1 < out.len() {
                        if let Value::Str(k2) = &out[j] {
                            if k2 == key {
                                child_has = true;
                                break;
                            }
                        }
                        j += 2;
                    }
                    if !child_has {
                        out.push(parent[i].clone());
                        out.push(parent[i + 1].clone());
                    }
                }
                i += 2;
            }
            Value::List(out)
        });
        // --- Substrate read primitives — kernel reaches the REST surface ----
        // The body's substrate lives behind /api/substrate/*. Until now the
        // kernel could compute over data it was handed but could not pull
        // its own data from the lattice. http_get + _json_get + _json_to_dict
        // are the smallest closing breath that lets a .fk recipe stand up
        // a `?lattice` or `?cell` query end-to-end without a Python shim.
        //
        // Why three minimal natives and not a fat client: the substrate's
        // REST surface is already designed for outside callers (Pydantic
        // response models, content-type JSON). The kernel just needs to
        // speak HTTP + JSON well enough to consume those responses; the
        // structural reasoning still happens in Form code over the dict
        // values that come back.
        //
        // http_get(url) → str|null. Blocking GET via the existing ureq
        // dependency that already powers the `fetch` CLI subcommand. No
        // headers, no auth, no body — the surface stays /api/substrate/*
        // shaped (public read, no credentials). null on transport error
        // so Form-side caller can match and decide.
        self.register_native("http_get", cat_call(), |_, _, args| {
            let url = args[0].as_str();
            match ureq::get(url).call() {
                Ok(resp) => match resp.into_string() {
                    Ok(body) => Value::Str(body),
                    Err(_) => Value::Null,
                },
                Err(_) => Value::Null,
            }
        });
        // _json_get(json_str, key) → str|int|float|bool|null. Parse a top-level
        // JSON object and extract `obj[key]`. Returns null when key is missing
        // or the JSON is malformed — same shape http_get uses, so Form code can
        // chain (let body (http_get url)) (let n (_json_get body "key")).
        // Only top-level keys; nested traversal lives in Form code via repeated
        // _json_get on the sub-string.
        self.register_native("_json_get", cat_access(), |_, _, args| {
            let body = args[0].as_str();
            let key = args[1].as_str();
            let parsed: serde_json::Value = match serde_json::from_str(body) {
                Ok(v) => v,
                Err(_) => return Value::Null,
            };
            let val = match parsed.get(key) {
                Some(v) => v,
                None => return Value::Null,
            };
            match val {
                serde_json::Value::Null => Value::Null,
                serde_json::Value::Bool(b) => Value::Bool(*b),
                serde_json::Value::Number(n) => {
                    if let Some(i) = n.as_i64() {
                        Value::Int(i)
                    } else if let Some(f) = n.as_f64() {
                        Value::Float(f)
                    } else {
                        Value::Null
                    }
                }
                serde_json::Value::String(s) => Value::Str(s.clone()),
                // For arrays/objects, return the re-serialized JSON string
                // so Form code can re-parse with another _json_get call.
                // Keeps the native surface flat (no recursive Value structure
                // beyond what the kernel already has) and matches the way
                // jq pipelines compose at the shell.
                _ => Value::Str(val.to_string()),
            }
        });
        // _json_to_dict(json_str) → __dict__-tagged list (the kernel's dict
        // shape). Convenience for the common case where the response is a
        // small flat object — e.g. /api/substrate/lattice/stats returns
        // {blueprints_total, recipes_total, cells_total} and the calling
        // Form code wants to address it like a dict.
        // Only top-level keys; nested objects/arrays come back as JSON
        // string values (consistent with _json_get).
        self.register_native("_json_to_dict", cat_method(), |_, _, args| {
            let body = args[0].as_str();
            let parsed: serde_json::Value = match serde_json::from_str(body) {
                Ok(v) => v,
                Err(_) => return Value::Null,
            };
            let obj = match parsed.as_object() {
                Some(o) => o,
                None => return Value::Null,
            };
            let mut out = vec![Value::Str("__dict__".to_string())];
            for (k, v) in obj {
                out.push(Value::Str(k.clone()));
                out.push(match v {
                    serde_json::Value::Null => Value::Null,
                    serde_json::Value::Bool(b) => Value::Bool(*b),
                    serde_json::Value::Number(n) => {
                        if let Some(i) = n.as_i64() {
                            Value::Int(i)
                        } else if let Some(f) = n.as_f64() {
                            Value::Float(f)
                        } else {
                            Value::Null
                        }
                    }
                    serde_json::Value::String(s) => Value::Str(s.clone()),
                    _ => Value::Str(v.to_string()),
                });
            }
            Value::List(out)
        });
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
        // sum — integer (or float-aware) total of a list. Sibling-parity
        // with the TS kernel. The earlier compost note pointed at core.fk's
        // `(defn sum (xs) (foldl plus 0 xs))`, but core.fk is not in the
        // bootstrap load path today; restoring the native is what keeps
        // the parity gate honest until auto-prelude lands.
        self.register_native("sum", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                // If any element is a float, promote the running total
                // to float — matches Python's behaviour for sum([1, 2.5]).
                let any_float = xs.iter().any(|v| matches!(v, Value::Float(_)));
                if any_float {
                    let mut total = 0.0f64;
                    for v in xs {
                        total += v.as_float();
                    }
                    return Value::Float(total);
                }
                let mut total: i64 = 0;
                for v in xs {
                    total += v.as_int();
                }
                return Value::Int(total);
            }
            Value::Int(0)
        });
        self.register_native("abs", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Float(f.abs()),
            _ => {
                let n = args[0].as_int();
                Value::Int(if n < 0 { -n } else { n })
            }
        });
        // Polymorphic `+` for Python compilation: int+int→add,
        // str+str→concat, list+list→concat. The compile-time emitter
        // can't always determine operand types (variables, function
        // returns); _plus dispatches at runtime instead.
        self.register_native("_plus", cat_method(), |_, _, args| {
            match (&args[0], &args[1]) {
                (Value::Int(a), Value::Int(b)) => Value::Int(a + b),
                // Float promotion — matches Python: int+float→float,
                // float+int→float, float+float→float.
                (Value::Float(a), Value::Float(b)) => Value::Float(a + b),
                (Value::Int(a), Value::Float(b)) => Value::Float(*a as f64 + b),
                (Value::Float(a), Value::Int(b)) => Value::Float(a + *b as f64),
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
                (Value::Str(a), Value::Float(b)) => {
                    let mut s = a.clone();
                    s.push_str(&format_float_python(*b));
                    Value::Str(s)
                }
                (Value::Float(a), Value::Str(b)) => {
                    let mut s = format_float_python(*a);
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
        // range(a, b, s)  → [a, a+s, a+2s, ..., < b] (or > b for negative step)
        // Opens `for i in range(N):` end-to-end through the kernel —
        // the most common Python loop idiom. Same semantics as CPython's
        // range builtin (returning an eager list rather than a lazy
        // iterator, which the kernel doesn't yet have iterators for).
        // Sibling-parity with TS kernel; the earlier compost note pointed
        // at core.fk's recursive (start, end) variant, but core.fk isn't
        // bootstrap-loaded today, so keeping range native is what keeps
        // python_range_demo running end-to-end against the native binary.
        self.register_native("range", cat_list_nat(), |_, _, args| {
            let (start, stop, step) = match args.len() {
                1 => (0i64, args[0].as_int(), 1i64),
                2 => (args[0].as_int(), args[1].as_int(), 1i64),
                _ => (args[0].as_int(), args[1].as_int(), args[2].as_int()),
            };
            let mut out: Vec<Value> = Vec::new();
            if step == 0 {
                return Value::List(out);
            }
            if step > 0 {
                let mut i = start;
                while i < stop {
                    out.push(Value::Int(i));
                    i += step;
                }
            } else {
                let mut i = start;
                while i > stop {
                    out.push(Value::Int(i));
                    i += step;
                }
            }
            Value::List(out)
        });
        // ── Python `math` module — a tight kernel-native shape ─────
        // The Python adapter rewrites `math.sqrt(x)` → `(math_sqrt x)`,
        // `math.pi` → `(math_pi)`, etc. at parse time, so imports
        // compile to nothing at runtime. Sibling-parity with the TS
        // kernel; the entries are tight (sqrt, pi, floor, ceil, pow) —
        // demonstrably useful for substrate code without enlarging the
        // bootstrap surface. Each entry returns the same shape CPython
        // produces so the parity gate's string compare stays honest:
        // sqrt/pi/pow → Float; floor/ceil → Int (CPython 3 behaviour).
        self.register_native("math_sqrt", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().sqrt())
        });
        self.register_native("math_pi", cat_method(), |_, _, _args| {
            Value::Float(std::f64::consts::PI)
        });
        self.register_native("math_floor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_float().floor() as i64)
        });
        self.register_native("math_ceil", cat_method(), |_, _, args| {
            Value::Int(args[0].as_float().ceil() as i64)
        });
        self.register_native("math_pow", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().powf(args[1].as_float()))
        });
        self.register_native("math_log", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().ln())
        });
        self.register_native("math_exp", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().exp())
        });
        // round_ndigits(x, n) — CPython `round(x, n)` for floats, EXACTLY.
        // The Python adapter lowers `round(x, n)` → `(round_ndigits x n)`.
        // Rounds the exact decimal value of the double half-to-even at n
        // fractional places (n >= 0), matching CPython bit-for-bit. Sibling-
        // parity with the Go + TS kernels. See round_ndigits_decimal above.
        self.register_native("round_ndigits", cat_method(), |_, _, args| {
            Value::Float(round_ndigits_decimal(args[0].as_float(), args[1].as_int()))
        });
        // ── Python `typing` module — opaque sentinels ─────────────────
        // Every typing import (List, Optional, Dict, Tuple, Any, Callable,
        // Union, Iterable, Iterator, Mapping, Sequence, Set, FrozenSet)
        // binds to this one native. Type annotations are parse-and-ignored
        // at compile time, so this never fires in real code; its existence
        // makes the `from typing import …` binding round-trip honest. Any
        // accidental runtime reference returns the same opaque string
        // across CPython, TS eval, and Rust kernel.
        self.register_native("typing_opaque", cat_method(), |_, _, _args| {
            Value::Str("<typing>".to_string())
        });
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
        // random_bytes(n) — open the doorway. Reads n bytes from
        // /dev/urandom every call. Different per invocation, per kernel
        // process. lc-divergence-is-the-doorway: this native intentionally
        // violates sibling parity when invoked — the divergence is the
        // substrate's signal of live field-touch.
        self.register_native("random_bytes", cat_call(), |_, _, args| {
            let n = args[0].as_int();
            if n <= 0 {
                return Value::List(Vec::new());
            }
            let mut buf = vec![0u8; n as usize];
            match fs::OpenOptions::new().read(true).open("/dev/urandom") {
                Ok(mut f) => match f.read_exact(&mut buf) {
                    Ok(_) => Value::List(buf.into_iter().map(|b| Value::Int(b as i64)).collect()),
                    Err(_) => Value::Null,
                },
                Err(_) => Value::Null,
            }
        });
        // ---- bitwise primitives -----------------------------------
        // True kernel primitives — cannot be expressed in pure Form
        // without exponential cost. Operate on 32-bit-unsigned semantics
        // (high bits masked out) so SHA-256-style recipes can compose
        // round functions over machine-word integers consistently.
        // Sibling parity: same masking, same shift semantics, on all
        // three kernels.
        self.register_native("band", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() & args[1].as_int())
        });
        self.register_native("bor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() | args[1].as_int())
        });
        self.register_native("bxor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() ^ args[1].as_int())
        });
        self.register_native("bnot_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            Value::Int((!a) as i64)
        });
        self.register_native("shl_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.wrapping_shl(n) as i64)
        });
        self.register_native("shr_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.wrapping_shr(n) as i64)
        });
        self.register_native("rotr_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.rotate_right(n) as i64)
        });
        // add_u32: modular 32-bit addition — the addition discipline
        // SHA-256's round constants and message schedule both require.
        self.register_native("add_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let b = args[1].as_int() as u32;
            Value::Int(a.wrapping_add(b) as i64)
        });
        // sha256_bytes / bytes_sum / bytes_hash were temporarily added
        // as natives here but composted: those are composites, not
        // primitives. SHA-256 lives in form-stdlib/sha256.fk as a Form
        // recipe over the bitwise primitives above. The real JIT path
        // (Form recipe → host machine code via cranelift/Go-source/JS
        // emission) is the next walk; this kernel currently relies on
        // recipe-walk for composite operations.
        // register_jit form-name-str native-name-str → 1 on bind, 0 if
        // native-name has no registered native (refuse silent miss).
        // Inserts (form-name → native-name) into k.jit_aliases. After this,
        // every (form-name ...) call goes through the aliased native instead
        // of walking the Form definition. Form recipes are canonical truth;
        // register_jit is the opt-in that promotes a recipe to host-native
        // execution. Removing the entry restores the Form walk.
        //
        // Discipline: the Form recipe MUST exist (or fall back to closure
        // lookup at call time); the alias is a dispatch hint, not the
        // definition. A demo: define `(defn my-count xs ...)` in Form, then
        // `(register_jit "my-count" "len")` makes (my-count xs) dispatch
        // through native `len`. Same NodeID-attested result; faster path.
        self.register_native("register_jit", cat_witness(), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let native_name = args[1].as_str().to_string();
            let native_id = k.intern_string(&native_name).inst;
            let exists =
                k.natives.contains_key(&native_id) || k.env_natives.contains_key(&native_id);
            if !exists {
                return Value::Int(0);
            }
            let form_id = k.intern_string(&form_name).inst;
            k.jit_aliases.insert(form_id, native_id);
            Value::Int(1)
        });
        // unregister_jit form-name-str → 1 if removed, 0 if no alias was
        // bound. Restores the Form-recipe walk path for that name.
        self.register_native("unregister_jit", cat_witness(), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            if k.jit_aliases.remove(&form_id).is_some() {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        // recipe_to_bytes nid → list-of-bytes (or null on error).
        //   Serializes a Recipe subtree to the .fkb wire format (string
        //   table + tree) as a byte list — usable over ANY byte channel
        //   (socket, in-memory list, registry message) without needing
        //   a file. Sibling-parity with read_form_binary semantics: the
        //   same bytes deserialize back to the same content-addressed
        //   structure in any kernel.
        self.register_native("recipe_to_bytes", cat_witness(), |k, _, args| {
            let bytes = serialize_artifact(k, args[0].as_nid());
            Value::List(bytes.into_iter().map(|b| Value::Int(b as i64)).collect())
        });
        // bytes_to_recipe bytes-list → nid (or null on parse error).
        //   Inverse of recipe_to_bytes. The bytes are the .fkb wire
        //   format from any sibling kernel. The receiver re-interns the
        //   structure locally and returns its NodeID — same content
        //   produces the same NodeID under the substrate's content-
        //   addressing.
        self.register_native("bytes_to_recipe", cat_witness(), |k, _, args| {
            let bytes: Vec<u8> = match &args[0] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => return Value::Null,
            };
            match deserialize_artifact(k, &bytes) {
                Ok(root) => Value::Nid(root),
                Err(_) => Value::Null,
            }
        });
        // jit_compile form-name-str → 1 if a host-JIT compile succeeded,
        //   0 if no compiler is available on this kernel build OR the
        //   recipe contains a shape outside the JIT subset OR rustc isn't
        //   in PATH OR the .so failed to load, -1 if the name isn't bound
        //   to a closure in the caller env.
        //
        // The Rust path mirrors the user-named shape: emit valid Rust
        // source from the Form recipe, invoke the system `rustc
        // --crate-type=cdylib`, load the resulting plugin.so via
        // libloading, and dispatch subsequent calls through the loaded
        // function pointer. Form recipe stays canonical truth — every
        // failure mode honestly returns 0, and recipe-walk continues
        // producing the same observable result.
        self.register_env_native("jit_compile", cat_witness(), |k, a, env, args| {
            if args.is_empty() {
                return Value::Int(-1);
            }
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            let v = match a.lookup(env, form_id) {
                Some(v) => v,
                None => return Value::Int(-1),
            };
            let cl = match v {
                Value::Closure(c) => c,
                _ => return Value::Int(-1),
            };
            // Already compiled? Idempotent: return 1.
            if k.jit_compiled.contains_key(&cl.body) {
                return Value::Int(1);
            }
            // Emit Rust source for the recipe.
            let src = match emit_rust_source(k, cl.name, &cl.params, cl.body) {
                Some(s) => s,
                None => return Value::Int(0),
            };
            // Compile + load. Any failure → honest 0.
            let jc = match compile_rust_cdylib(&src, cl.params.len()) {
                Some(j) => j,
                None => return Value::Int(0),
            };
            k.jit_compiled.insert(cl.body, Arc::new(jc));
            Value::Int(1)
        });
        // jit_aliased? form-name-str → 1 if a JIT alias is currently bound
        // for this name, else 0. Lets Form code introspect dispatch routing.
        self.register_native("jit_aliased?", cat_compare(RCMP_EQ), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            if k.jit_aliases.contains_key(&form_id) {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        // seeded_bytes(seed, count) — deterministic LCG byte stream.
        // Same (seed, count) → byte-identical output across Go / Rust / TS.
        // Used by the private-channel protocol to transmit megabytes of
        // content by transmitting only (seed, count) on the wire; receiver
        // reconstructs locally. Compression ratio: arbitrary / 16 bytes.
        // LCG: glibc rand(): state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        self.register_native("seeded_bytes", cat_call(), |_, _, args| {
            let seed = args[0].as_int() as u32;
            let count = args[1].as_int();
            if count <= 0 {
                return Value::List(Vec::new());
            }
            let mut state: u32 = seed;
            let n = count as usize;
            let mut out: Vec<Value> = Vec::with_capacity(n);
            for _ in 0..n {
                state = state.wrapping_mul(1103515245).wrapping_add(12345) & 0x7FFFFFFF;
                out.push(Value::Int((state & 0xFF) as i64));
            }
            Value::List(out)
        });
        // sum_bytes_list(list) — sum all integer elements. Used for fast
        // verification that two cells' large byte-lists agree without
        // materializing them through the Form recursion. O(n) compiled.
        self.register_native("sum_bytes_list", cat_call(), |_, _, args| match &args[0] {
            Value::List(xs) => {
                let mut s: i64 = 0;
                for v in xs {
                    s = s.wrapping_add(v.as_int());
                }
                Value::Int(s)
            }
            _ => Value::Int(0),
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
        self.register_native("read_form_binary", cat_call(), |k, _, args| match fs::read(
            args[0].as_str(),
        ) {
            Ok(bytes) => match deserialize_artifact(k, &bytes) {
                Ok(root) => Value::Nid(root),
                Err(_) => Value::Null,
            },
            Err(_) => Value::Null,
        });
        self.register_native("write_form_binary", cat_call(), |k, _, args| {
            let bytes = serialize_artifact(k, args[1].as_nid());
            match fs::write(args[0].as_str(), &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
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

        // --- Filesystem CRUD natives — real directories + files --------
        // Sibling parity across Go/Rust/TS. Predicates return 1/0;
        // mutations return 0 on success, -1 on error; fs_list returns a
        // List of name-strings or Null on error.
        self.register_native("fs_exists", cat_call(), |_, _, args| {
            if fs::metadata(args[0].as_str()).is_ok() {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        self.register_native("fs_is_dir", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if meta.is_dir() => Value::Int(1),
                _ => Value::Int(0),
            }
        });
        self.register_native(
            "fs_mkdir",
            cat_call(),
            |_, _, args| match fs::create_dir_all(args[0].as_str()) {
                Ok(_) => Value::Int(0),
                Err(_) => Value::Int(-1),
            },
        );
        self.register_native("fs_rmdir", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if meta.is_dir() => match fs::remove_dir_all(args[0].as_str()) {
                    Ok(_) => Value::Int(0),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("fs_remove", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if !meta.is_dir() => match fs::remove_file(args[0].as_str()) {
                    Ok(_) => Value::Int(0),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("fs_rename", cat_call(), |_, _, args| {
            match fs::rename(args[0].as_str(), args[1].as_str()) {
                Ok(_) => Value::Int(0),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("fs_list", cat_call(), |_, _, args| {
            match fs::read_dir(args[0].as_str()) {
                Ok(rd) => {
                    // sort by name for cross-kernel parity (Go's os.ReadDir
                    // is name-sorted; Rust/Node are OS-arbitrary).
                    let mut names: Vec<String> = rd
                        .flatten()
                        .map(|e| e.file_name().to_string_lossy().to_string())
                        .collect();
                    names.sort();
                    Value::List(names.into_iter().map(Value::Str).collect())
                }
                Err(_) => Value::Null,
            }
        });

        // --- Socket natives — L1 physical layer for inter-cell IO ------
        // Sibling parity across Go/Rust/TS. Handle = int (≥ 0 success,
        // -1 error). Connection table is a module-level OnceLock<Mutex>.
        // (socket_listen port)             → handle | -1
        // (socket_accept listener-handle)  → conn-handle | -1   (BLOCKS)
        // (socket_connect host port)       → conn-handle | -1
        // (socket_send conn bytes-string)  → bytes-sent | -1
        // (socket_recv conn max-bytes)     → received-string ("" on close)
        // (socket_close handle)            → 0 | -1
        self.register_native("socket_listen", cat_call(), |_, _, args| {
            let port = args[0].as_int();
            match TcpListener::bind(format!("127.0.0.1:{}", port)) {
                Ok(ln) => Value::Int(socket_register(SocketKind::Listener(ln))),
                Err(_) => Value::Int(-1),
            }
        });
        // (socket_port listener-handle) → bound TCP port | -1. Reports the
        // OS-assigned port of an ephemeral (port 0) listener — the basis of
        // single-process loopback.
        self.register_native("socket_port", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Listener(ln) => match ln.local_addr() {
                    Ok(addr) => Value::Int(addr.port() as i64),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_accept", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Listener(ln) => match ln.accept() {
                    Ok((stream, _)) => {
                        Value::Int(socket_register(SocketKind::Stream(Mutex::new(stream))))
                    }
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_connect", cat_call(), |_, _, args| {
            let host = args[0].as_str().to_string();
            let port = args[1].as_int();
            match TcpStream::connect(format!("{}:{}", host, port)) {
                Ok(stream) => Value::Int(socket_register(SocketKind::Stream(Mutex::new(stream)))),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("socket_send", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let bytes = args[1].as_str().as_bytes().to_vec();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Stream(m) => {
                    let mut g = m.lock().unwrap();
                    match g.write(&bytes) {
                        Ok(n) => Value::Int(n as i64),
                        Err(_) => Value::Int(-1),
                    }
                }
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_recv", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let max = args[1].as_int();
            if max <= 0 {
                return Value::Str(String::new());
            }
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Str(String::new()),
            };
            match &*s {
                SocketKind::Stream(m) => {
                    let mut g = m.lock().unwrap();
                    let mut buf = vec![0u8; max as usize];
                    match g.read(&mut buf) {
                        Ok(n) if n > 0 => {
                            Value::Str(String::from_utf8_lossy(&buf[..n]).to_string())
                        }
                        _ => Value::Str(String::new()),
                    }
                }
                _ => Value::Str(String::new()),
            }
        });
        self.register_native("socket_close", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            if h < 0 {
                return Value::Int(-1);
            }
            if socket_drop(h) {
                Value::Int(0)
            } else {
                Value::Int(-1)
            }
        });

        // --- Postgres natives — the DB carrier of the storage port ------
        // (pg_connect dsn)        → handle | -1
        // (pg_exec handle sql)    → rows-affected | -1   (DDL / INSERT / UPDATE)
        // (pg_query handle sql)   → result-string | "ERR" (tab-separated cols,
        //                            newline-separated rows; "" = zero rows)
        // (pg_close handle)       → 0 | -1
        // DSN is libpq form: "host=127.0.0.1 port=5432 user=u dbname=d ...".
        self.register_native("pg_connect", cat_call(), |_, _, args| {
            let dsn = args[0].as_str().to_string();
            match postgres::Client::connect(&dsn, postgres::NoTls) {
                Ok(c) => Value::Int(pg_register(c)),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("pg_exec", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let sql = args[1].as_str().to_string();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => return Value::Int(-1),
            };
            let mut g = client.lock().unwrap();
            match g.execute(&sql, &[]) {
                Ok(n) => Value::Int(n as i64),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("pg_query", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let sql = args[1].as_str().to_string();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => return Value::Str("ERR".to_string()),
            };
            let mut g = client.lock().unwrap();
            let rows = match g.query(&sql, &[]) {
                Ok(r) => r,
                Err(_) => return Value::Str("ERR".to_string()),
            };
            // Encode rows as tab-separated columns, newline-separated rows.
            // Columns are rendered to text via their SQL type (text/int8/bool
            // cover the substrate's portable column set). NULL → empty string.
            let mut out = String::new();
            for (ri, row) in rows.iter().enumerate() {
                if ri > 0 {
                    out.push('\n');
                }
                for ci in 0..row.len() {
                    if ci > 0 {
                        out.push('\t');
                    }
                    out.push_str(&pg_cell_to_string(row, ci));
                }
            }
            Value::Str(out)
        });
        self.register_native("pg_close", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            if h < 0 {
                return Value::Int(-1);
            }
            if pg_drop(h) {
                Value::Int(0)
            } else {
                Value::Int(-1)
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
        // bp — resolve a Blueprint name to its NodeID via the generated
        // BP_ENTRIES table. Unknown name → undefined node (1,2,0,0).
        // Sibling parity with form-kernel-go + form-kernel-ts.
        self.register_native("bp", cat_witness(), |_, _, args| {
            let name = args[0].as_str();
            for (entry_name, [pkg, level, ty, inst]) in self::bp_table::BP_ENTRIES {
                if *entry_name == name {
                    return Value::Nid(NodeID {
                        pkg: *pkg,
                        level: *level,
                        ty: *ty,
                        inst: *inst,
                    });
                }
            }
            // Fail loud — never invent a NodeID for an unknown name. The old
            // silent fallback to {1,2,0,0} collapsed every unregistered name
            // onto one NodeID, so distinct blueprints collided invisibly. An
            // unregistered name is a missing registration, not a valid shape.
            // Sibling parity: Go panics, TS throws.
            panic!(
                "bp: unregistered blueprint name {:?} — register it: \
                 python3 scripts/scan_form_blueprints.py register {} (bp tables then regenerate). \
                 The substrate never invents a NodeID for an unknown name.",
                name, name
            )
        });
        self.register_native("intern_trivial_int", cat_witness(), |k, _, args| {
            Value::Nid(k.intern_trivial_int(args[0].as_int()))
        });
        self.register_native("intern_trivial_string", cat_witness(), |k, _, args| {
            let s = args[0].as_str().to_string();
            Value::Nid(k.intern_string(&s))
        });
        // intern_trivial_float — content-address an IEEE-754 f64 into the
        // overflow table and return its trivial NodeID. The string argument is
        // the float's source text (e.g. "0.5"); a parse failure lands on +0.0
        // so the witness is total like str_to_int's unwrap_or(0). Sibling of
        // intern_trivial_int / intern_trivial_string: the interning primitive
        // (intern_trivial_float64) already existed for the .fk-source reader;
        // this exposes it to Form code so the python-bmf float-literal lift can
        // build a PY-BMF-FLOAT leaf the walker reads back as Value::Float.
        self.register_native("intern_trivial_float", cat_witness(), |k, _, args| {
            let f: f64 = args[0].as_str().parse().unwrap_or(0.0);
            Value::Nid(k.intern_trivial_float64(f))
        });
        self.register_native("float_value", cat_method(), |k, _, args| {
            let n = args[0].as_nid();
            match n.ty {
                TRIV_FLOAT64 => Value::Float(k.decode_float64(n.inst)),
                _ => panic!("float_value expects a float NodeID"),
            }
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
        self.register_native(
            "field_blueprint",
            cat_field_primitive(RB_FIELD),
            native_field_blueprint,
        );
        self.register_native(
            "field_cell",
            cat_field_primitive(RB_FIELD),
            native_field_cell,
        );
        self.register_native(
            "field_carrier",
            cat_field_primitive(RB_CARRIER),
            native_field_carrier,
        );
        self.register_native(
            "field_topology",
            cat_field_primitive(RB_TOPOLOGY),
            native_field_topology,
        );
        self.register_native(
            "field_fiber",
            cat_field_primitive(RB_FIBER),
            native_field_fiber,
        );
        self.register_native(
            "field_region",
            cat_field_primitive(RB_REGION),
            native_field_region,
        );
        self.register_native(
            "field_boundary",
            cat_field_primitive(RB_BOUNDARY),
            native_field_boundary,
        );
        self.register_native(
            "field_neighborhood",
            cat_field_primitive(RB_NEIGHBORHOOD),
            native_field_neighborhood,
        );
        self.register_native(
            "field_match",
            cat_field_primitive(RB_MATCH_FIELD),
            native_field_match,
        );
        self.register_native(
            "field_delta",
            cat_field_primitive(RB_DELTA),
            native_field_delta,
        );
        self.register_native(
            "field_resolve",
            cat_field_primitive(RB_RESOLVE),
            native_field_resolve,
        );
        self.register_native(
            "field_commit",
            cat_field_primitive(RB_COMMIT),
            native_field_commit,
        );
        self.register_native(
            "field_step",
            cat_field_primitive(RB_STEP),
            native_field_step,
        );
        self.register_native(
            "field_lift",
            cat_field_primitive(RB_LIFT),
            native_field_lift,
        );
        self.register_native(
            "field_sample",
            cat_field_primitive(RB_SAMPLE),
            native_field_sample,
        );
        self.register_native(
            "field_observe",
            cat_field_primitive(RB_OBSERVE),
            native_field_observe,
        );
        self.register_native(
            "field_intervene",
            cat_field_primitive(RB_INTERVENE),
            native_field_intervene,
        );
        self.register_native(
            "field_residual",
            cat_field_primitive(RB_RESIDUAL),
            native_field_residual,
        );
        self.register_native(
            "field_receipt",
            cat_field_primitive(RB_RECEIPT),
            native_field_receipt,
        );
        self.register_native(
            "field_cost",
            cat_field_primitive(RB_COST),
            native_field_cost,
        );
        self.register_native(
            "field_consent",
            cat_field_primitive(RB_CONSENT),
            native_field_consent,
        );
        self.register_native(
            "field_evidence",
            cat_field_primitive(RB_EVIDENCE),
            native_field_evidence,
        );
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
        // file_append_bytes path bytes-list → new-file-size | -1. Atomic
        // O_APPEND write — the missing primitive for a log-structured store.
        // Unlike write_file_bytes (which truncates), this appends at end-of-
        // file and returns the new total size. Creates the file if absent.
        self.register_native("file_append_bytes", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let bytes: Vec<u8> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => return Value::Int(-1),
            };
            let mut f = match fs::OpenOptions::new().append(true).create(true).open(&path) {
                Ok(f) => f,
                Err(_) => return Value::Int(-1),
            };
            if f.write_all(&bytes).is_err() {
                return Value::Int(-1);
            }
            match f.metadata() {
                Ok(meta) => Value::Int(meta.len() as i64),
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

        // --- BMF native rule runtime (Path C) ---------------------------
        //
        // bmf_apply_rule_native — additive fast path for engine.fk's
        // apply-object-rule. Sibling port of Go's implementation; the
        // returned Recipe shape (caps alist with "objects" + "result"
        // keys, bmf-match-source captures + span, the result bmf-object
        // as ("cell" rule-name recipe source inverse)) is byte-identical
        // under node_eq to what apply-object-rule produces.
        //
        // POC scope this breath — flat sequence of object-literal
        // matchers, no captures, no choice, no star/opt/cut. Every other
        // shape PANICS loudly so callers can't silently fall off the fast
        // path. Captures + choice + star/opt are queued for a later
        // breath; see docs/coherence-substrate/bmf-native-runtime.form.
        self.register_native("bmf_apply_rule_native", cat_witness(), |k, a, args| {
            if args.len() != 2 {
                panic!("bmf_apply_rule_native: expects (rule object-stream)");
            }
            let rule = &args[0];
            let stream = &args[1];
            let rule_list = match rule {
                Value::List(xs) if xs.len() >= 3 => xs.clone(),
                _ => panic!("bmf_apply_rule_native: rule must be (name pattern action ...)"),
            };
            let rule_name = rule_list[0].clone();
            let pattern = rule_list[1].clone();
            let action = rule_list[2].clone();
            let rule_inverse = if rule_list.len() > 3 {
                rule_list[3].clone()
            } else {
                Value::Null
            };
            // Pattern must be a tagged list.
            let pattern_list = match &pattern {
                Value::List(xs) if !xs.is_empty() => xs.clone(),
                _ => panic!("bmf_apply_rule_native: pattern must be a tagged list"),
            };
            let tag = match &pattern_list[0] {
                Value::Str(s) => s.clone(),
                _ => panic!("bmf_apply_rule_native: pattern must be a tagged list"),
            };
            if tag != "sequence" {
                panic!("bmf_apply_rule_native: TODO: pattern tag '{}' not yet supported (POC: 'sequence' of 'object' literals only)", tag);
            }
            // Validate every child is an "object" literal — no nesting yet.
            let children: Vec<Value> = pattern_list[1..].to_vec();
            for (i, child) in children.iter().enumerate() {
                let kids = match child {
                    Value::List(xs) if xs.len() >= 3 => xs,
                    _ => panic!("bmf_apply_rule_native: child {} malformed", i),
                };
                let ctag = match &kids[0] {
                    Value::Str(s) => s.clone(),
                    _ => panic!("bmf_apply_rule_native: child {} malformed", i),
                };
                if ctag != "object" {
                    panic!("bmf_apply_rule_native: TODO: sequence child '{}' not yet supported (POC: 'object' literals only)", ctag);
                }
            }
            // State-machine walk: consume one stream object per literal child.
            let stream_list = match stream {
                Value::List(xs) => xs.clone(),
                _ => panic!("bmf_apply_rule_native: object-stream must be a list"),
            };
            let mut consumed: usize = 0;
            for child in &children {
                let cl = match child {
                    Value::List(xs) => xs,
                    _ => unreachable!(),
                };
                let want_kind = match &cl[1] {
                    Value::Str(s) => s.clone(),
                    _ => String::new(),
                };
                let want_value = match &cl[2] {
                    Value::Str(s) => s.clone(),
                    _ => String::new(),
                };
                if consumed >= stream_list.len() {
                    return Value::List(vec![
                        Value::Str("fail".to_string()),
                        Value::Str("expected BMF object".to_string()),
                    ]);
                }
                let obj = &stream_list[consumed];
                let obj_list = match obj {
                    Value::List(xs) if xs.len() >= 3 => xs,
                    _ => panic!("bmf_apply_rule_native: stream item is not a cell"),
                };
                let head = match &obj_list[0] {
                    Value::Str(s) => s.clone(),
                    _ => panic!("bmf_apply_rule_native: stream item is not a cell"),
                };
                if head != "cell" {
                    panic!("bmf_apply_rule_native: stream item is not a cell");
                }
                let got_kind = match &obj_list[1] {
                    Value::Str(s) => s.clone(),
                    _ => String::new(),
                };
                let got_value = match &obj_list[2] {
                    Value::Str(s) => s.clone(),
                    _ => String::new(),
                };
                if got_kind != want_kind {
                    return Value::List(vec![
                        Value::Str("fail".to_string()),
                        Value::Str(format!("object kind mismatch: expected {}", want_kind)),
                    ]);
                }
                if !want_value.is_empty() && got_value != want_value {
                    return Value::List(vec![
                        Value::Str("fail".to_string()),
                        Value::Str(format!("object value mismatch: expected {}", want_value)),
                    ]);
                }
                consumed += 1;
            }
            // Build captures-as-collection. POC scope: no named captures,
            // so the collection wraps an empty objects list — same shape
            // Form's (bmf-caps-to-collection (cap-empty 0)) produces.
            let empty_collection = Value::List(vec![
                Value::Str("bmf-collection".to_string()),
                Value::List(vec![]),
            ]);
            // Consumed prefix slice — what Form's (take N stream) returns.
            let span = Value::List(stream_list[..consumed].to_vec());
            // bmf-match-source captures span.
            let match_source = Value::List(vec![
                Value::Str("bmf-match-source".to_string()),
                empty_collection.clone(),
                span,
            ]);
            // Invoke the action closure: (rule-action captures-collection)
            // → recipe. The only Form re-entry; everything above is native.
            let cl = match &action {
                Value::Closure(c) => c.clone(),
                _ => panic!("bmf_apply_rule_native: rule action must be a closure"),
            };
            if cl.params.len() != 1 {
                panic!(
                    "bmf_apply_rule_native: action closure takes {} params, expected 1",
                    cl.params.len()
                );
            }
            let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            a.bind(call_frame, cl.params[0], empty_collection.clone());
            let recipe = walk(k, a, cl.body, call_frame);
            // Result bmf-object — ("cell" rule-name recipe source inverse).
            let result_object = Value::List(vec![
                Value::Str("cell".to_string()),
                rule_name,
                recipe,
                match_source,
                rule_inverse,
            ]);
            // caps alist — cons "result" then "objects" so the alist
            // order matches engine.fk's (cap-set (cap-set ... "objects" ...) "result").
            let caps = Value::List(vec![
                Value::List(vec![Value::Str("result".to_string()), result_object]),
                Value::List(vec![Value::Str("objects".to_string()), empty_collection]),
            ]);
            let rest = Value::List(stream_list[consumed..].to_vec());
            Value::List(vec![Value::Str("match".to_string()), caps, rest])
        });

        // --- Debug / inspection -----------------------------------------
        // `trace` — print-and-return. Drop into any Form expression to
        // inspect a value mid-computation without breaking control flow.
        // Output goes to stderr so it doesn't pollute the result on stdout.
        //   (let result (trace (filter even? xs)))
        //   (trace "label" value)   ; with a label prefix
        // `now_unix_ms` — current wall-clock as a millisecond unix timestamp.
        // External effect (reads the host clock) so it's cat_call. Sibling
        // parity holds on shape, NOT on value: every kernel returns an int,
        // every kernel's int is > a recent past epoch — but the exact
        // milliseconds diverge between invocations. Bands check shape only.
        self.register_native("now_unix_ms", cat_call(), |_, _, _| {
            use std::time::{SystemTime, UNIX_EPOCH};
            let ms = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_millis() as i64)
                .unwrap_or(0);
            Value::Int(ms)
        });

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
// resolve_method — walk the inheritance chain to find a method closure.
//
// Starts at `class_name`; tries `<C>__<m>`; if not bound, looks up
// `<C>__base` (a string) and tries the parent. First match wins.
// Single-inheritance only — MRO is the linear chain. Panics with the
// full chain walked when no method is found.
// ---------------------------------------------------------------------------

fn resolve_method(
    k: &mut Kernel,
    a: &mut Arena,
    env: FrameId,
    class_name: &str,
    method_name: &str,
) -> (String, Arc<Closure>) {
    let mut current = class_name.to_string();
    let mut chain: Vec<String> = vec![current.clone()];
    loop {
        let qualified = format!("{}__{}", current, method_name);
        if let Some(name_id) = k.str_idx.get(&qualified).copied() {
            if let Some(val) = a.lookup(env, name_id) {
                if let Value::Closure(c) = val {
                    return (qualified, c);
                }
            }
        }
        // Method not found on `current` — walk to base.
        let base_key = format!("{}__base", current);
        let base_id = match k.str_idx.get(&base_key).copied() {
            Some(id) => id,
            None => {
                panic!(
                    "_dispatch: no method '{}' in inheritance chain [{}]",
                    method_name,
                    chain.join(" -> ")
                );
            }
        };
        let parent_val = match a.lookup(env, base_id) {
            Some(v) => v,
            None => {
                panic!(
                    "_dispatch: no method '{}' in inheritance chain [{}]",
                    method_name,
                    chain.join(" -> ")
                );
            }
        };
        let parent_name = match parent_val {
            Value::Str(s) => s,
            _ => panic!("_dispatch: '{}' is not a string", base_key),
        };
        if parent_name.is_empty() {
            panic!(
                "_dispatch: no method '{}' in inheritance chain [{}]",
                method_name,
                chain.join(" -> ")
            );
        }
        current = parent_name;
        chain.push(current.clone());
    }
}

// ---------------------------------------------------------------------------
// Form → Rust source JIT
// ---------------------------------------------------------------------------
//
// Sibling to the TS kernel's compileNode (recipe → JS via `new Function`).
// Pipeline:
//   1. emit_rust_function_source(k, name, params, body) → Rust source string,
//      or None if the recipe contains a node the emitter can't yet handle.
//   2. compile_rust_cdylib(src) → JitCompiled (Library + fn ptr), or None
//      on rustc failure / load failure.
//   3. dispatch at FNCALL: when the closure body NodeID is in k.jit_compiled
//      and all args are Int, call the function pointer directly.
//
// What the emitter handles structurally (every other shape falls back to a
// `compile_fail` return that aborts the compile, so the kernel never silently
// emits broken Rust):
//   - i64 arithmetic: add / sub / mul / div / mod
//   - i64 comparisons: eq / ne / lt / le / gt / ge   (yields bool)
//   - logic on bool: and / or / not
//   - if / if-else
//   - let-bindings (body is the bound value's continuation in the block)
//   - recursive free-function calls (recipes that reference each other)
//   - parameter references
//   - integer literals
//
// Lists, native calls, substrate reflection: out of scope by design — the
// walker still owns those. The compile is best-effort acceleration; failure
// is honest (returns 0 from jit_compile, recipe-walk continues).

/// Result of trying to emit a Rust expression for a Form node.
/// `Int(src)` → expression evaluates to i64.
/// `Bool(src)` → expression evaluates to bool.
/// We track the type at emit time so comparisons-in-if and i64 returns get
/// the right casts.
enum EmittedExpr {
    Int(String),
    Bool(String),
}

impl EmittedExpr {
    fn into_i64(self) -> String {
        match self {
            EmittedExpr::Int(s) => s,
            // bool→i64 via `if b { 1 } else { 0 }` keeps it C-ABI clean.
            EmittedExpr::Bool(s) => format!("(if ({}) {{ 1i64 }} else {{ 0i64 }})", s),
        }
    }

    fn into_bool(self) -> String {
        match self {
            EmittedExpr::Bool(s) => s,
            // i64→bool via `!= 0` lets Form's truthy-int convention survive.
            EmittedExpr::Int(s) => format!("(({}) != 0i64)", s),
        }
    }

    fn src(&self) -> &str {
        match self {
            EmittedExpr::Int(s) | EmittedExpr::Bool(s) => s.as_str(),
        }
    }
}

/// Tracks compile-time scope while emitting. `vars` maps NameID → Rust
/// variable name; `siblings` maps NameID → arity (so a recursive call can
/// emit a direct Rust function call to a sibling defn).
struct EmitScope<'a> {
    vars: HashMap<NameID, String>,
    siblings: &'a HashMap<NameID, (String, usize)>,
    uid: u32,
}

impl<'a> EmitScope<'a> {
    fn new(siblings: &'a HashMap<NameID, (String, usize)>) -> Self {
        Self {
            vars: HashMap::new(),
            siblings,
            uid: 0,
        }
    }

    fn fresh(&mut self, hint: &str) -> String {
        self.uid += 1;
        let sanitized: String = hint
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '_' {
                    c
                } else {
                    '_'
                }
            })
            .collect();
        format!("v_{}_{}", sanitized, self.uid)
    }
}

/// Sanitize an arbitrary string for use as a Rust identifier.
fn sanitize_rust_ident(s: &str) -> String {
    let cleaned: String = s
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    if cleaned.is_empty() {
        return "fn_".to_string();
    }
    // Rust keywords / leading-digit guard.
    if cleaned
        .chars()
        .next()
        .map(|c| c.is_ascii_digit())
        .unwrap_or(false)
    {
        format!("f_{}", cleaned)
    } else {
        format!("fn_{}", cleaned)
    }
}

/// Collect every recipe-defined sibling function discoverable from the
/// closure body. Walks BLOCK.DO/SEQ/LET-trees looking for FNDEFs at any
/// position so mutually-recursive recipes still resolve.
///
/// Returns a map of NameID → (sanitized Rust identifier, arity, body NodeID).
/// The siblings get emitted as Rust `fn name(arg0: i64, ...) -> i64` at the
/// top of the generated .rs file so calls between them link cleanly.
fn collect_siblings(
    k: &Kernel,
    body: NodeID,
    target: NameID,
    target_arity: usize,
    target_body: NodeID,
) -> HashMap<NameID, (String, usize, NodeID)> {
    let mut out: HashMap<NameID, (String, usize, NodeID)> = HashMap::new();
    // The target itself is always a sibling — recursive calls dispatch to
    // its own Rust definition (which IS `compiled_fn` exported with C ABI).
    out.insert(
        target,
        (
            sanitize_rust_ident(k.name_str(target)),
            target_arity,
            target_body,
        ),
    );
    let mut visit: Vec<NodeID> = vec![body];
    let mut seen: HashSet<NodeID> = HashSet::new();
    while let Some(n) = visit.pop() {
        if !seen.insert(n) {
            continue;
        }
        if n.level == LEVEL_TRIVIAL {
            continue;
        }
        let cat = k.category(n);
        let kids = k.children(n);
        if cat.ty == RB_FNDEF && kids.len() >= 3 {
            let name = k.ident_id(kids[0]);
            let params: Vec<NameID> = k.children(kids[1]).iter().map(|p| p.inst).collect();
            let arity = params.len();
            let fbody = kids[2];
            out.entry(name)
                .or_insert_with(|| (sanitize_rust_ident(k.name_str(name)), arity, fbody));
        }
        for c in kids {
            visit.push(c);
        }
    }
    out
}

/// Emit a single Form expression as a Rust expression. Returns None when
/// the expression contains a shape outside the JIT subset.
fn emit_expr(k: &Kernel, n: NodeID, scope: &mut EmitScope<'_>) -> Option<EmittedExpr> {
    if n.level == LEVEL_TRIVIAL {
        return match n.ty {
            TRIV_INT => {
                let v = (n.inst as i32) as i64;
                Some(EmittedExpr::Int(format!("{}i64", v)))
            }
            TRIV_BOOL => Some(EmittedExpr::Bool(if n.inst != 0 {
                "true".to_string()
            } else {
                "false".to_string()
            })),
            // STRING / NULL / FLOAT64 — not on the JIT path.
            _ => None,
        };
    }
    let cat = k.category(n);
    let kids = k.children(n);
    match cat.ty {
        RB_IDENT => {
            let name = k.ident_id(n);
            if let Some(v) = scope.vars.get(&name) {
                Some(EmittedExpr::Int(v.clone()))
            } else {
                None
            }
        }
        RB_MATH => {
            if kids.is_empty() {
                return None;
            }
            let op = match cat.inst {
                RMATH_PLUS => "+",
                RMATH_MINUS => "-",
                RMATH_MULTIPLY => "*",
                RMATH_DIVIDE => "/",
                RMATH_MODULO => "%",
                _ => return None,
            };
            let mut parts: Vec<String> = Vec::with_capacity(kids.len());
            for c in &kids {
                parts.push(emit_expr(k, *c, scope)?.into_i64());
            }
            // Wrapping arithmetic — Form recipes treat i64 overflow as wrap,
            // matching the walker's `.wrapping_*` behavior and the TS kernel's
            // `| 0` semantics for i32. We use wrapping_* so panic-free hot loops.
            let wrap_method = match cat.inst {
                RMATH_PLUS => "wrapping_add",
                RMATH_MINUS => "wrapping_sub",
                RMATH_MULTIPLY => "wrapping_mul",
                RMATH_DIVIDE => "wrapping_div",
                RMATH_MODULO => "wrapping_rem",
                _ => return None,
            };
            let mut acc = parts[0].clone();
            for p in &parts[1..] {
                acc = format!("({}).{}({})", acc, wrap_method, p);
            }
            let _ = op; // kept for symbolic clarity; wrap_method is what we emit
            Some(EmittedExpr::Int(acc))
        }
        RB_COMPARE => {
            if kids.len() != 2 {
                return None;
            }
            let op = match cat.inst {
                RCMP_EQ => "==",
                RCMP_NE => "!=",
                RCMP_LT => "<",
                RCMP_LE => "<=",
                RCMP_GT => ">",
                RCMP_GE => ">=",
                _ => return None,
            };
            let a = emit_expr(k, kids[0], scope)?.into_i64();
            let b = emit_expr(k, kids[1], scope)?.into_i64();
            Some(EmittedExpr::Bool(format!("(({}) {} ({}))", a, op, b)))
        }
        RB_LOGIC => match cat.inst {
            RLOG_NOT => {
                if kids.len() != 1 {
                    return None;
                }
                let a = emit_expr(k, kids[0], scope)?.into_bool();
                Some(EmittedExpr::Bool(format!("(!({}))", a)))
            }
            RLOG_AND | RLOG_OR => {
                let op = if cat.inst == RLOG_AND { "&&" } else { "||" };
                let mut parts: Vec<String> = Vec::new();
                for c in &kids {
                    parts.push(emit_expr(k, *c, scope)?.into_bool());
                }
                Some(EmittedExpr::Bool(format!(
                    "({})",
                    parts.join(&format!(" {} ", op))
                )))
            }
            _ => None,
        },
        RB_COND => {
            match cat.inst {
                RCOND_IF => {
                    if kids.len() != 2 {
                        return None;
                    }
                    let c = emit_expr(k, kids[0], scope)?.into_bool();
                    let t = emit_expr(k, kids[1], scope)?.into_i64();
                    // No `else` in Form — TS encodes as `null`; we encode as 0
                    // (only sound when the recipe author never reads the result
                    // of a no-else `if`; fib/fact patterns always pair if with
                    // else, so this rarely fires).
                    Some(EmittedExpr::Int(format!(
                        "(if ({}) {{ {} }} else {{ 0i64 }})",
                        c, t
                    )))
                }
                RCOND_IF_ELSE => {
                    if kids.len() != 3 {
                        return None;
                    }
                    let c = emit_expr(k, kids[0], scope)?.into_bool();
                    let t = emit_expr(k, kids[1], scope)?.into_i64();
                    let e = emit_expr(k, kids[2], scope)?.into_i64();
                    Some(EmittedExpr::Int(format!(
                        "(if ({}) {{ {} }} else {{ {} }})",
                        c, t, e
                    )))
                }
                _ => None,
            }
        }
        RB_BLOCK => {
            // LET binds and the block evaluates to its last expression.
            // We emit a Rust block `{ let v = ...; ...; tail }`.
            match cat.inst {
                RBLK_LET => {
                    // LET shape in this kernel: kids = [name-trivial, value, ...continuation?]
                    // Form-on-top emits LET as a single (name, value) pair in
                    // most surfaces; multi-form continuations appear only inside DO.
                    if kids.len() < 2 {
                        return None;
                    }
                    let name_node = kids[0];
                    if name_node.level != LEVEL_TRIVIAL || name_node.ty != TRIV_STRING {
                        return None;
                    }
                    let name_id = name_node.inst;
                    let value_src = emit_expr(k, kids[1], scope)?.into_i64();
                    let var = scope.fresh(k.name_str(name_id));
                    // LET's expression value, in the walker, is the bound
                    // value itself. Subsequent forms in the surrounding DO
                    // pick up the binding via scope.vars.
                    scope.vars.insert(name_id, var.clone());
                    Some(EmittedExpr::Int(format!(
                        "{{ let {} = {}; {} }}",
                        var, value_src, var
                    )))
                }
                RBLK_DO | RBLK_SEQ => {
                    if kids.is_empty() {
                        return Some(EmittedExpr::Int("0i64".to_string()));
                    }
                    // DO produces a Rust block. Each inner form becomes a
                    // statement; the last is the block's expression value.
                    // LET inside DO binds for subsequent forms — we mutate
                    // scope.vars in-place, mirroring how the walker layers
                    // bindings into the same frame.
                    let mut stmts: Vec<String> = Vec::new();
                    let mut tail: Option<String> = None;
                    for (i, c) in kids.iter().enumerate() {
                        let is_last = i == kids.len() - 1;
                        // Inline LET specially so the binding stays in scope
                        // for siblings within the DO block.
                        let cat_c = k.category(*c);
                        if cat_c.ty == RB_BLOCK && cat_c.inst == RBLK_LET {
                            let kc = k.children(*c);
                            if kc.len() < 2
                                || kc[0].level != LEVEL_TRIVIAL
                                || kc[0].ty != TRIV_STRING
                            {
                                return None;
                            }
                            let name_id = kc[0].inst;
                            let value_src = emit_expr(k, kc[1], scope)?.into_i64();
                            let var = scope.fresh(k.name_str(name_id));
                            scope.vars.insert(name_id, var.clone());
                            if is_last {
                                stmts.push(format!("let {} = {};", var, value_src));
                                tail = Some(var);
                            } else {
                                stmts.push(format!("let {} = {};", var, value_src));
                            }
                        } else {
                            let expr = emit_expr(k, *c, scope)?.into_i64();
                            if is_last {
                                tail = Some(expr);
                            } else {
                                // Side-effect-bearing inner forms aren't in
                                // the JIT subset — only let-bindings, math,
                                // and tail expressions. A pure inner expression
                                // we can simply discard with `let _ = ...;`.
                                stmts.push(format!("let _ = {};", expr));
                            }
                        }
                    }
                    let body = format!(
                        "{{ {} {} }}",
                        stmts.join(" "),
                        tail.unwrap_or_else(|| "0i64".to_string())
                    );
                    Some(EmittedExpr::Int(body))
                }
                _ => None,
            }
        }
        RB_FNCALL => {
            if kids.is_empty() {
                return None;
            }
            let callee = kids[0];
            // Resolve callee name — either bare string-trivial (parser-fast
            // path) or an IDENT wrapping a string-trivial.
            let nameid = if callee.level == LEVEL_TRIVIAL && callee.ty == TRIV_STRING {
                callee.inst
            } else if k.category(callee).ty == RB_IDENT {
                k.ident_id(callee)
            } else {
                return None;
            };
            // Sibling Form fn?
            if let Some((rust_name, arity)) = scope.siblings.get(&nameid) {
                if kids.len() - 1 != *arity {
                    return None;
                }
                let mut args: Vec<String> = Vec::with_capacity(*arity);
                for a in &kids[1..] {
                    args.push(emit_expr(k, *a, scope)?.into_i64());
                }
                return Some(EmittedExpr::Int(format!(
                    "{}({})",
                    rust_name,
                    args.join(", ")
                )));
            }
            // Unknown callee — would need to call back into the walker, which
            // the JIT subset doesn't support. Caller falls back.
            None
        }
        // FNDEF appears inside DO blocks for nested recipes. The sibling
        // collector already discovered them and they get emitted as Rust
        // fns. An FNDEF expression itself evaluates to the closure value;
        // in the JIT subset we represent it as 0 (the def already happened
        // at the Rust top-level — this is a placeholder so DO continues).
        RB_FNDEF => Some(EmittedExpr::Int("0i64".to_string())),
        _ => None,
    }
}

/// Emit the full Rust source for a top-level closure. The exported symbol
/// `compiled_fn` carries the C ABI; internal sibling defns become regular
/// Rust functions in the same crate. Returns None if any node in the body
/// (or any reachable sibling body) is outside the JIT subset.
fn emit_rust_source(
    k: &Kernel,
    target_name: NameID,
    target_params: &[NameID],
    target_body: NodeID,
) -> Option<String> {
    let siblings_full = collect_siblings(
        k,
        target_body,
        target_name,
        target_params.len(),
        target_body,
    );
    // Strip body NodeIDs for the scope (the scope just needs name → (rust_name, arity)).
    let siblings: HashMap<NameID, (String, usize)> = siblings_full
        .iter()
        .map(|(k, (rn, ar, _))| (*k, (rn.clone(), *ar)))
        .collect();

    // Emit every sibling, target last.
    let mut emitted_fns: Vec<String> = Vec::new();
    let mut target_rust_name = String::new();
    for (name, (rust_name, arity, body)) in &siblings_full {
        let params: Vec<NameID> = if *name == target_name {
            target_params.to_vec()
        } else {
            // Sibling — find the FNDEF that registered it and pull params.
            // We re-traverse to recover the params list (small cost; emit is rare).
            find_fndef_params(k, target_body, *name)?
        };
        if params.len() != *arity {
            return None;
        }
        if params.len() > JIT_MAX_ARITY {
            return None;
        }
        let mut scope = EmitScope::new(&siblings);
        let mut param_decls: Vec<String> = Vec::new();
        for (i, p) in params.iter().enumerate() {
            let var = format!("a{}", i);
            scope.vars.insert(*p, var.clone());
            param_decls.push(format!("{}: i64", var));
        }
        let body_src = emit_expr(k, *body, &mut scope)?.into_i64();
        let is_target = *name == target_name;
        if is_target {
            target_rust_name = rust_name.clone();
            // Target gets two definitions: the internal one and a C-ABI
            // wrapper. This way recursive sibling calls go through the
            // internal Rust fn (zero-overhead), while the external loader
            // gets a stable symbol.
            emitted_fns.push(format!(
                "fn {}({}) -> i64 {{ {} }}",
                rust_name,
                param_decls.join(", "),
                body_src
            ));
        } else {
            emitted_fns.push(format!(
                "fn {}({}) -> i64 {{ {} }}",
                rust_name,
                param_decls.join(", "),
                body_src
            ));
        }
    }

    // C-ABI wrapper for the target. Arity-specific signature: callers
    // dispatch through a match on arity at the call site, casting the raw
    // pointer to the exactly-shaped `unsafe extern "C" fn(i64,…,i64) -> i64`.
    let arity = target_params.len();
    let params: Vec<String> = (0..arity).map(|i| format!("a{}: i64", i)).collect();
    let args: Vec<String> = (0..arity).map(|i| format!("a{}", i)).collect();
    let wrapper = format!(
        "#[no_mangle]\npub extern \"C\" fn compiled_fn({}) -> i64 {{ {}({}) }}",
        params.join(", "),
        target_rust_name,
        args.join(", ")
    );

    // Header: silence the unused-fn lint that fires when a sibling defn
    // isn't called by the body (rare but possible — author left a helper
    // they didn't end up using).
    let header = "#![allow(unused)]\n#![allow(dead_code)]\n";
    Some(format!(
        "{}\n{}\n\n{}\n",
        header,
        emitted_fns.join("\n\n"),
        wrapper
    ))
}

/// Walk the recipe tree starting at `root` and return the params NameIDs
/// for the FNDEF whose name matches `target`. Returns None if not found.
fn find_fndef_params(k: &Kernel, root: NodeID, target: NameID) -> Option<Vec<NameID>> {
    let mut visit: Vec<NodeID> = vec![root];
    let mut seen: HashSet<NodeID> = HashSet::new();
    while let Some(n) = visit.pop() {
        if !seen.insert(n) {
            continue;
        }
        if n.level == LEVEL_TRIVIAL {
            continue;
        }
        let cat = k.category(n);
        let kids = k.children(n);
        if cat.ty == RB_FNDEF && kids.len() >= 3 {
            let name = k.ident_id(kids[0]);
            if name == target {
                return Some(k.children(kids[1]).iter().map(|p| p.inst).collect());
            }
        }
        for c in kids {
            visit.push(c);
        }
    }
    None
}

/// Compile a Rust source string to a cdylib and load it. Returns None on
/// any failure — rustc not in PATH, compile error, library load error.
/// Caller treats None as honest "compile unavailable" and returns 0 from
/// jit_compile so Form code branches on availability.
fn compile_rust_cdylib(src: &str, arity: usize) -> Option<JitCompiled> {
    // Unique temp dir per compile — multiple JIT calls in one session
    // don't fight for the same lib.rs / plugin.so file.
    let mut temp = std::env::temp_dir();
    let nonce = format!(
        "form-rust-jit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
    );
    temp.push(nonce);
    if fs::create_dir_all(&temp).is_err() {
        return None;
    }
    let src_path = temp.join("lib.rs");
    let out_path = temp.join("plugin.so");
    if fs::write(&src_path, src).is_err() {
        return None;
    }
    // Invoke rustc. -C opt-level=2 is the sweet spot — most of the gain
    // for a small fraction of the compile cost. We pass --edition=2021
    // explicitly so the host's rustc default doesn't change behavior.
    let status = Command::new("rustc")
        .arg("--crate-type=cdylib")
        .arg("--edition=2021")
        .arg("-C")
        .arg("opt-level=2")
        .arg("-o")
        .arg(&out_path)
        .arg(&src_path)
        .stderr(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .status();
    let status = match status {
        Ok(s) => s,
        Err(_) => {
            // rustc not in PATH — cleanup and bail. The Form sample stays
            // honest: compile-attempted=1 (we tried), recipe walks instead.
            let _ = fs::remove_dir_all(&temp);
            return None;
        }
    };
    if !status.success() {
        let _ = fs::remove_dir_all(&temp);
        return None;
    }
    // Load the .so. libloading::Library::new is unsafe because the dynamic
    // linker can run arbitrary init code in the loaded image. We trust the
    // .so because we just emitted its source from a Form recipe and built
    // it with the same rustc this process trusts.
    let library = match unsafe { libloading::Library::new(&out_path) } {
        Ok(l) => l,
        Err(_) => {
            let _ = fs::remove_dir_all(&temp);
            return None;
        }
    };
    // Resolve the symbol. We immediately extract the raw pointer so the
    // Library can outlive the Symbol (Symbol borrows the Library, but the
    // raw pointer is just an address that's valid as long as the .so stays
    // mapped — and the Library staying alive guarantees that).
    let func_ptr: *const () = unsafe {
        let sym: libloading::Symbol<unsafe extern "C" fn() -> i64> =
            match library.get(b"compiled_fn") {
                Ok(s) => s,
                Err(_) => {
                    let _ = fs::remove_dir_all(&temp);
                    return None;
                }
            };
        // Cast through *const () so callers can re-cast to the arity-
        // specific signature. raw_pointer is the dlsym address.
        *sym.into_raw() as *const ()
    };
    Some(JitCompiled {
        _library: library,
        func: func_ptr,
        arity,
        _temp_dir: temp,
    })
}

/// Dispatch a call through a loaded JitCompiled. Returns None if the args
/// don't all unbox to i64 (the caller must fall back to recipe-walk).
///
/// SAFETY: We loaded the .so via libloading and the Library handle is kept
/// alive by Arc<JitCompiled>. The function signature is arity-specific i64→i64.
/// The cast and call happen inside a single unsafe block so the contract is
/// localized. The body of the function was emitted from a Form recipe via
/// our own emit_rust_source — same crate this kernel was built with — so
/// ABI compatibility is guaranteed.
fn jit_dispatch(jc: &JitCompiled, args: &[Value]) -> Option<Value> {
    if args.len() != jc.arity {
        return None;
    }
    let mut i64s: Vec<i64> = Vec::with_capacity(args.len());
    for a in args {
        match a {
            Value::Int(n) => i64s.push(*n),
            Value::Bool(b) => i64s.push(if *b { 1 } else { 0 }),
            _ => return None,
        }
    }
    let p = jc.func;
    let result: i64 = unsafe {
        match i64s.len() {
            0 => {
                let f: unsafe extern "C" fn() -> i64 = std::mem::transmute(p);
                f()
            }
            1 => {
                let f: unsafe extern "C" fn(i64) -> i64 = std::mem::transmute(p);
                f(i64s[0])
            }
            2 => {
                let f: unsafe extern "C" fn(i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1])
            }
            3 => {
                let f: unsafe extern "C" fn(i64, i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2])
            }
            4 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3])
            }
            5 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3], i64s[4])
            }
            6 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5])
            }
            7 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(
                    i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5], i64s[6],
                )
            }
            8 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(
                    i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5], i64s[6], i64s[7],
                )
            }
            _ => return None,
        }
    };
    Some(Value::Int(result))
}

// ---------------------------------------------------------------------------
// Walker — full RBasic dispatch
// ---------------------------------------------------------------------------

pub(crate) fn walk(k: &mut Kernel, a: &mut Arena, n: NodeID, env: FrameId) -> Value {
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
            let lv = walk(k, a, kids[0], env);
            let rv = walk(k, a, kids[1], env);
            // Width promotion: if either operand is Float, the result is
            // Float (matches Python `int + float → float`, and IEEE 754
            // arithmetic on mixed inputs). Pure int/int stays on the
            // fast i64 path.
            if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                let l = lv.as_float();
                let r = rv.as_float();
                Value::Float(match cat.inst {
                    RMATH_PLUS => l + r,
                    RMATH_MINUS => l - r,
                    RMATH_MULTIPLY => l * r,
                    RMATH_DIVIDE => l / r,
                    RMATH_MODULO => l - (l / r).floor() * r,
                    _ => panic!("math.f64: unknown op {}", cat.inst),
                })
            } else {
                let l = lv.as_int();
                let r = rv.as_int();
                Value::Int(match cat.inst {
                    RMATH_PLUS => l + r,
                    RMATH_MINUS => l - r,
                    RMATH_MULTIPLY => l * r,
                    RMATH_DIVIDE => l / r,
                    RMATH_MODULO => l % r,
                    _ => panic!("math: unknown op {}", cat.inst),
                })
            }
        }
        RB_COMPARE => {
            let lv = walk(k, a, kids[0], env);
            let rv = walk(k, a, kids[1], env);
            // Same width-promotion rule as math: float on either side
            // forces an IEEE comparison. Pure int/int stays integer.
            if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                let l = lv.as_float();
                let r = rv.as_float();
                Value::Bool(match cat.inst {
                    RCMP_EQ => l == r,
                    RCMP_NE => l != r,
                    RCMP_LT => l < r,
                    RCMP_LE => l <= r,
                    RCMP_GT => l > r,
                    RCMP_GE => l >= r,
                    _ => panic!("compare.f64: unknown op {}", cat.inst),
                })
            } else {
                let l = lv.as_int();
                let r = rv.as_int();
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
            let raw_name = k.ident_id(kids[0]);
            // JIT alias: if a Form function-name is JIT-registered, swap to
            // the aliased native-name before native lookup. Form recipes are
            // the canonical truth; `register_jit form-name native-name` opts
            // calls into a kernel-resident optimized native.
            let name = k.jit_aliases.get(&raw_name).copied().unwrap_or(raw_name);
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
            // Closure lookup uses the ORIGINAL function-name (not the JIT-
            // aliased one) — the user defined this function and wants to
            // call THEIR version when no JIT mapping resolved a native.
            let callee = a
                .lookup(env, raw_name)
                .unwrap_or_else(|| panic!("unbound function: {}", k.name_str(raw_name)));
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
            // We collect them into `arg_values` first so the JIT dispatch
            // path can use them directly without re-walking from the frame.
            // The clone is Arc<Closure> — bump-the-refcount, not deep.
            let cl2 = cl.clone();
            let mut arg_values: Vec<Value> = Vec::with_capacity(cl2.params.len());
            for (i, p) in cl2.params.iter().enumerate() {
                let arg = walk(k, a, kids[i + 1], env);
                arg_values.push(arg.clone());
                a.bind(call_frame, *p, arg);
            }
            let fn_name = k.name_str(cl.name).to_string();
            if let Some(t) = &mut k.trace {
                t.record_fn(&fn_name);
            }
            // JIT-compiled fast path: if (jit_compile "name") landed for
            // this closure's body, dispatch through the loaded function
            // pointer. Form recipe stays canonical truth; the .so is opt-in
            // bootstrap to host-native speed. Sibling-attested: TS uses
            // V8's `new Function`; Go uses `plugin.Open`; Rust uses
            // libloading over a rustc-produced cdylib. Same observable
            // result, three real host-native paths.
            //
            // We hold an Arc<JitCompiled> through the call so the Library
            // can't be dropped mid-call (kernel mutation is safe; the Arc
            // bumps refcount synchronously).
            if let Some(jc) = k.jit_compiled.get(&cl.body).cloned() {
                if let Some(v) = jit_dispatch(&jc, &arg_values) {
                    return v;
                }
                // Args don't unbox to i64 — fall back to the walker.
                // This preserves Form semantics for closures over non-int
                // values (lists, strings, closures) even after jit_compile
                // succeeded for the integer-only path.
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
                // Float: digits '.' digits, optionally with an exponent.
                // The dot must be followed by a digit so `(.foo bar)` and
                // bare integers stay legible. Sibling-parity: TS reader
                // recognises the same shape.
                let is_float =
                    i + 1 < bytes.len() && bytes[i] == b'.' && bytes[i + 1].is_ascii_digit();
                if is_float {
                    i += 1; // consume '.'
                    while i < bytes.len() && bytes[i].is_ascii_digit() {
                        i += 1;
                    }
                    // Optional exponent: [eE][+-]?[0-9]+
                    if i < bytes.len() && (bytes[i] == b'e' || bytes[i] == b'E') {
                        i += 1;
                        if i < bytes.len() && (bytes[i] == b'+' || bytes[i] == b'-') {
                            i += 1;
                        }
                        while i < bytes.len() && bytes[i].is_ascii_digit() {
                            i += 1;
                        }
                    }
                    toks.push(SexpTok {
                        kind: "FLOAT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                } else {
                    toks.push(SexpTok {
                        kind: "INT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                }
                col += (i - start) as u32;
            }
            b'-' if i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit() => {
                let start = i;
                i += 1;
                while i < bytes.len() && bytes[i].is_ascii_digit() {
                    i += 1;
                }
                let is_float =
                    i + 1 < bytes.len() && bytes[i] == b'.' && bytes[i + 1].is_ascii_digit();
                if is_float {
                    i += 1;
                    while i < bytes.len() && bytes[i].is_ascii_digit() {
                        i += 1;
                    }
                    if i < bytes.len() && (bytes[i] == b'e' || bytes[i] == b'E') {
                        i += 1;
                        if i < bytes.len() && (bytes[i] == b'+' || bytes[i] == b'-') {
                            i += 1;
                        }
                        while i < bytes.len() && bytes[i].is_ascii_digit() {
                            i += 1;
                        }
                    }
                    toks.push(SexpTok {
                        kind: "FLOAT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                } else {
                    toks.push(SexpTok {
                        kind: "INT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                }
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
        "FLOAT" => {
            let f: f64 = t.value.parse().unwrap_or_else(|e| {
                panic!(
                    "parse error: bad float literal {:?} at line {}, col {}: {}",
                    t.value, t.line, t.col, e
                )
            });
            (k.intern_trivial_float64(f), i + 1)
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
fn cat_field_primitive(ty: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty,
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

pub(crate) fn run_source(src: &str) -> Value {
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, src);
    execute_root(&mut k, root)
}

pub(crate) fn read_root_from_source(k: &mut Kernel, src: &str) -> NodeID {
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
  serve --port <p> --routes <file.fk> [--upstream <base-url>]\n                                       kernel front-door router: native Form handlers\n                                       for listed paths, fan-out to the Python upstream\n                                       for the rest (HTTP/1.0 proof-of-shape)

Source adapter modes:
  <file.fk> [more.fk ...]              run .fk files
  --expr \"<form-expression>\"          evaluate a Form expression
  --bench                              benchmark run
  --numeric-bench                      numeric kernel comparison"
    );
}

// ---------------------------------------------------------------------------
// `serve` — proof-of-shape kernel-as-HTTP-listener
// ---------------------------------------------------------------------------
//
// The deepest move toward Breath 8 of `form/kernel-roadmap.md`: a tiny
// HTTP/1.0 listener that lives *inside* the kernel binary, parses the
// request into Form values, looks up a handler closure from a routes.fk
// file's top-level `routes` binding, walks the closure, and writes the
// returned value back as the response body.
//
// This is gesture, not replacement. FastAPI remains the body's primary
// doorway; this exists so the body can feel "kernel CAN be the HTTP
// layer" before betting more of the stack on it. ~50 lines of raw
// `std::net` HTTP/1.0 — no hyper, no actix, no async runtime. The whole
// dependency footprint is what already shipped (ureq for `fetch`).
//
// routes.fk shape:
//   (defn route_hello () "Hello from the kernel")
//   (defn route_echo (q) (dict_get q "msg"))
//   (let routes (list
//     (list "/hello" route_hello)
//     (list "/echo"  route_echo)))
//
// A 1-arg handler receives the query as a List of (key value) pairs
// (an alist; `dict_get` reads from it). A 0-arg handler receives no
// argument. The walker turns either return value into a string for
// the response body via `Value::display()`.

// Per-worker thread stack. The kernel value-walk is a recursive tree-walker, so
// a deeply self-recursive native handler consumes real stack. 16 MiB comfortably
// exceeds the typical main-thread stack (~8 MiB), so a pooled worker handles at
// least the recursion depth the single-threaded serve path did before the pool.
const WORKER_STACK_SIZE: usize = 16 * 1024 * 1024;

// The route manifest a worker resolves from its own kernel+arena: a list of
// (path, handler-closure). Each closure's `env` is a frame index INTO THAT
// worker's arena, so route_pairs are NOT shareable across workers — every
// worker re-loads routes.fk into its own Kernel+Arena and resolves its own
// copy. This is the !Sync constraint the pool answers (lc-native-kernel-binary:
// the per-process intern table means a pool of kernel workers, not one shared
// mutable kernel).
type RoutePairs = Vec<(String, Arc<Closure>)>;

// Resolve the top-level `routes` binding from a kernel+arena that has already
// walked the manifest source. Pulled out of cli_serve so BOTH the single-path
// load and each worker's per-thread load run the SAME resolution shape. Returns
// the (path, closure) pairs, or an error string for the caller to report.
fn build_route_pairs(
    k: &mut Kernel,
    arena: &Arena,
    root_env: FrameId,
    routes_path: &str,
) -> Result<RoutePairs, String> {
    let routes_name = k.intern_string("routes").inst;
    let routes_val = match arena.lookup(root_env, routes_name) {
        Some(v) => v,
        None => {
            return Err(format!(
                "{} must bind a top-level `routes` list",
                routes_path
            ))
        }
    };
    match &routes_val {
        Value::List(xs) => xs
            .iter()
            .map(|row| match row {
                Value::List(ys) if ys.len() == 2 => {
                    let path = match &ys[0] {
                        Value::Str(s) => s.clone(),
                        _ => return Err("route key must be a string".to_string()),
                    };
                    let cl = match &ys[1] {
                        Value::Closure(c) => c.clone(),
                        _ => {
                            return Err(format!("route value for {} must be a closure", path))
                        }
                    };
                    Ok((path, cl))
                }
                _ => Err("each route must be (path closure)".to_string()),
            })
            .collect(),
        _ => Err("`routes` must be a list of (path closure) pairs".to_string()),
    }
}

// Build a worker's OWN Kernel + Arena from the manifest source, resolve its own
// route_pairs, and return all three. Called once per worker at startup (loading
// the source N times is fine — it is once-per-worker, not per-request). The
// returned arena owns the frames the route closures capture, so it must stay
// alive alongside the kernel for the worker's lifetime.
fn build_worker_kernel(
    src: &str,
    routes_path: &str,
) -> Result<(Kernel, Arena, RoutePairs), String> {
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, src);
    let mut arena = Arena::new();
    let root_env = arena.new_frame(None);
    k.active_roots = vec![root];
    let _ = walk(&mut k, &mut arena, root, root_env);
    let route_pairs = build_route_pairs(&mut k, &arena, root_env, routes_path)?;
    Ok((k, arena, route_pairs))
}

// Handle ONE request on a worker's own kernel+arena. This is the single factored
// serving shape (core-abstraction-first): the routing decision (native Form
// handler vs fan-out to the Python upstream vs 404) lives here ONCE, and both the
// worker pool (parallelism) and the keep-alive loop (multiple requests per
// connection) simply call it. Because `k` and `arena` belong to the calling
// worker alone, concurrent requests on different workers never share mutable
// kernel state — each request's value-walk is isolated.
//
// Returns whether the connection should be KEPT ALIVE for the next request:
// the client's intent (HTTP/1.1 default-keep-alive unless `Connection: close`;
// HTTP/1.0 close-unless-`keep-alive`) AND no server-side reason to close. An
// idle/EOF read, a 413 (body undrained — framing broken), and a handler error
// all return `false` so the keep-alive loop ends and the stream is dropped.
// `carry` holds bytes read past this request's end (pipelining) for the next
// call on the same connection.
fn handle_request(
    stream: &mut TcpStream,
    carry: &mut Vec<u8>,
    k: &mut Kernel,
    arena: &mut Arena,
    route_pairs: &RoutePairs,
    upstream: &Option<String>,
) -> bool {
    // Read the FULL request: the header block, then exactly Content-Length body
    // bytes if present (read_request honors Content-Length across as many socket
    // reads as the body needs — a body larger than one buffer is fully captured —
    // and carries any over-read bytes into `carry` for the next request on this
    // persistent connection). HTTP/1.1 keep-alive with Content-Length framing;
    // chunked transfer remains a named breath (KERNEL_AS_ROUTER.md request row).
    let (head, body_bytes) = match read_request(stream, carry) {
        RequestRead::Ok(h, b) => (h, b),
        RequestRead::TooLarge => {
            // Reject on the Content-Length header alone — the oversized body is
            // never drained, so the connection's framing is broken: close it.
            let status = "413 Payload Too Large".to_string();
            let msg = format!("request body exceeds {} bytes\n", MAX_BODY_BYTES);
            let _ = stream
                .write_all(http_response(&status, &msg, "local-control", false, "", &[]).as_bytes());
            return false;
        }
        RequestRead::Error => return false, // idle close / read-timeout / EOF — loop ends
    };
    // The client's keep-alive intent for THIS connection (server may still close
    // on an error below).
    let keep_alive = head_keep_alive(&head);
    let (method, target, path, mut request_data) = parse_request_line(&head);
    // Parse the body by Content-Type and MERGE its fields into the same alist
    // the handler reads (core-abstraction-first: ONE request-data shape, whether
    // a field arrived as a query param or a body field). Query fields come
    // first; body fields are appended. form-urlencoded fields land as plain
    // (k v) pairs; a JSON / other body lands as a single ("__body__", raw) pair.
    let content_type = parse_content_type(&head);
    request_data.extend(parse_request_body(&content_type, &body_bytes));
    // The full client request header list (request line excluded), captured once
    // so the fan-out arm can forward the client's end-to-end headers
    // (Authorization, Cookie, Accept*, …) to the upstream. Native handlers don't
    // read headers yet (a named-later breath — KERNEL_AS_ROUTER.md handler-inputs
    // row), but the fan-out arm needs them now to front authenticated routes.
    let req_headers = parse_headers(&head);

    // The router decision: a path with a native Form handler is served
    // entirely in the kernel; a path with no handler fans out to the
    // Python upstream (if --upstream is set) or 404s.
    let body: String;
    let status: String;
    let router: &str;
    // The response's Content-Type and other relayed headers: a fan-out fills
    // these from the UPSTREAM's real response (so a JSON/HTML route survives the
    // proxy and its Set-Cookie/Cache-Control reach the client); native/404
    // responses leave them empty, so the ONE emit shape (http_response) defaults
    // the type to text/plain and relays no extra headers — the router owns all
    // framing on those arms.
    let mut resp_content_type = String::new();
    let mut resp_headers: Vec<(String, String)> = Vec::new();
    if let Some((_, cl)) = route_pairs.iter().find(|(p, _)| *p == path) {
        // NATIVE: served entirely in Form, no Python in the path.
        // Build the request alist as Value::List of (key, value) pairs — query
        // params AND body fields, uniformly (form-urlencoded merged in;
        // JSON/other captured under "__body__"). The handler reads them the same
        // way regardless of how each field arrived.
        let q_alist = Value::List(
            request_data
                .iter()
                .map(|(k, v)| Value::List(vec![Value::Str(k.clone()), Value::Str(v.clone())]))
                .collect(),
        );
        let cl = cl.clone();
        let call_frame = arena.new_frame_with_capacity(Some(cl.env), cl.params.len());
        if cl.params.len() == 1 {
            arena.bind(call_frame, cl.params[0], q_alist);
        } else if cl.params.len() != 0 {
            let status = "500 Internal Server Error".to_string();
            let body = format!(
                "handler for {} wants {} params; serve passes 0 or 1\n",
                path,
                cl.params.len()
            );
            let _ = stream.write_all(
                http_response(&status, &body, "native-kernel-error", false, "", &[]).as_bytes(),
            );
            return false; // close on error — keep the framing unambiguous
        }
        let result = walk(k, arena, cl.body, call_frame);
        status = "200 OK".to_string();
        body = result.display();
        router = "native-kernel";
    } else if let Some(upstream_base) = upstream {
        // FAN-OUT: no native handler — forward to the Python upstream and
        // relay its response. The kernel owns the front door; Python is the
        // upstream for the not-yet-native tail. Each worker issues its own
        // independent fan-out hop. The client's METHOD, BODY, and end-to-end
        // request headers (Authorization, Cookie, Accept*, …) are forwarded so
        // an authenticated/content-typed route is fronted truthfully; the
        // UPSTREAM's response Content-Type + end-to-end headers (Set-Cookie,
        // Cache-Control, Location, …) are relayed back so the client receives
        // the upstream's real type and cookies, not a flattened text/plain.
        // Hop-by-hop headers are stripped both ways; the router owns the framing
        // on its client hop (Content-Length, Connection — http_response writes
        // those, the relayed set cannot clobber them).
        let fanout = fanout_request(upstream_base, &method, &target, &req_headers, &body_bytes);
        status = fanout.status;
        body = fanout.body;
        resp_content_type = fanout.content_type;
        resp_headers = fanout.headers;
        router = "fanout-python";
    } else {
        // No native handler and no upstream configured.
        status = "404 Not Found".to_string();
        body = format!("no route for {}\n", path);
        router = "local-control";
    }
    // Frame the response with an accurate Content-Length and the keep-alive
    // verdict, the upstream's Content-Type + relayed end-to-end headers on a
    // fan-out (empty -> text/plain + no extra headers on native/404). The router
    // owns Content-Length + Connection; the relayed set was already filtered to
    // exclude those. If the write fails the peer is gone — close the loop.
    if stream
        .write_all(
            http_response(
                &status,
                &body,
                router,
                keep_alive,
                &resp_content_type,
                &resp_headers,
            )
            .as_bytes(),
        )
        .is_err()
    {
        return false;
    }
    keep_alive
}

// How long an idle kept-alive connection may sit between requests before the
// server closes it and frees the worker. HTTP/1.1 keep-alive holds the socket
// open after a response so the next request reuses the same TCP connection
// (saving a handshake each time); without a cap an idle client would pin a
// worker forever and starve the pool (thread-per-connection: a worker serving
// one keep-alive client is unavailable to others until the connection closes or
// this timeout fires). 5s is a conservative default — long enough that a normal
// client's back-to-back requests stay on one connection, short enough that an
// abandoned connection frees its worker quickly. The production tuning knobs are
// THIS value and the worker count (cli_serve --workers).
const KEEPALIVE_IDLE_TIMEOUT: Duration = Duration::from_secs(5);

// Serve a connection's full keep-alive LIFETIME: repeatedly handle requests on
// the SAME TcpStream until the client closes it, an error/EOF arrives, the idle
// read-timeout fires, or a response forces close (client `Connection: close`,
// 413, handler error). This wraps the per-request handle_request in a loop —
// the per-request serving shape stays ONE factored function (core-abstraction-
// first); keep-alive is the loop around it, not a fork of the logic.
//
// An idle read-timeout (KEEPALIVE_IDLE_TIMEOUT) is set on the stream so a
// connection that goes quiet between requests does not pin this worker forever:
// the next read_request returns Error (the timeout surfaces as a read error),
// the loop ends, the stream drops, and the worker returns to the queue free to
// serve another connection.
fn serve_connection(
    mut stream: TcpStream,
    k: &mut Kernel,
    arena: &mut Arena,
    route_pairs: &RoutePairs,
    upstream: &Option<String>,
) {
    // Idle timeout so a held-open keep-alive connection cannot starve the pool.
    let _ = stream.set_read_timeout(Some(KEEPALIVE_IDLE_TIMEOUT));
    // Bytes already read past one request's end belong to the NEXT request on
    // this connection (pipelining) — carried across loop iterations so no byte
    // is dropped between requests.
    let mut carry: Vec<u8> = Vec::new();
    // Serve requests on this one connection until handle_request says to close.
    while handle_request(&mut stream, &mut carry, k, arena, route_pairs, upstream) {}
}

// One kernel worker. Builds its OWN Kernel + Arena (the routes.fk loaded once
// into it at startup — !Sync, never shared), then pulls accepted streams from
// the shared work queue and serves each connection's full keep-alive lifetime
// via serve_connection (which loops handle_request on the one stream). N of
// these run concurrently behind the accept loop; because each owns its kernel,
// concurrent requests never corrupt one another's state.
fn worker_loop(
    id: usize,
    src: Arc<String>,
    routes_path: Arc<String>,
    upstream: Arc<Option<String>>,
    rx: Arc<Mutex<mpsc::Receiver<TcpStream>>>,
) {
    let (mut k, mut arena, route_pairs) = match build_worker_kernel(&src, &routes_path) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("serve: worker {} failed to load routes: {}", id, e);
            return;
        }
    };
    loop {
        // Lock only to dequeue one stream, then release before serving so the
        // workers truly run in parallel (the lock guards the queue, not the
        // request handling).
        let stream = {
            let guard = match rx.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            guard.recv()
        };
        match stream {
            Ok(s) => serve_connection(s, &mut k, &mut arena, &route_pairs, &upstream),
            // Sender dropped (listener closed) — drain done, worker exits.
            Err(_) => return,
        }
    }
}

fn cli_serve(args: &[String]) -> i32 {
    // --port <p> --routes <file.fk> [--upstream <http-base-url>]
    let mut port: u16 = 8001;
    let mut routes_path: Option<String> = None;
    // --upstream <base-url> turns the listener into the front-door ROUTER:
    // a path with a native Form handler is served entirely in the kernel
    // (no Python in the path); a path with no native handler fans out to
    // the Python upstream (the running FastAPI app) over HTTP. Absent this
    // flag an unmatched path is a 404 — the original proof-of-shape behavior,
    // unchanged, so existing callers see no difference.
    let mut upstream: Option<String> = None;
    // --workers <n> sizes the pool of kernel workers behind the accept loop.
    // Each worker owns its own Kernel + Arena (the !Sync constraint), so the
    // pool gives REAL concurrency, not one shared mutable kernel serialized.
    // Default: the host's available parallelism (capped sane), so the box's
    // cores are used out of the box; 0 or unset falls back to the default.
    let mut workers: Option<usize> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--port" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --port requires an argument");
                    return 2;
                }
                port = match args[i + 1].parse() {
                    Ok(p) => p,
                    Err(_) => {
                        eprintln!("serve: --port must be a number");
                        return 2;
                    }
                };
                i += 2;
            }
            "--routes" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --routes requires an argument");
                    return 2;
                }
                routes_path = Some(args[i + 1].clone());
                i += 2;
            }
            "--upstream" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --upstream requires a base-url argument");
                    return 2;
                }
                upstream = Some(args[i + 1].trim_end_matches('/').to_string());
                i += 2;
            }
            "--workers" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --workers requires a number");
                    return 2;
                }
                workers = match args[i + 1].parse() {
                    Ok(w) => Some(w),
                    Err(_) => {
                        eprintln!("serve: --workers must be a number");
                        return 2;
                    }
                };
                i += 2;
            }
            other => {
                eprintln!("serve: unknown argument: {}", other);
                return 2;
            }
        }
    }
    let routes_path = match routes_path {
        Some(p) => p,
        None => {
            eprintln!("serve: --routes <file.fk> is required");
            return 2;
        }
    };
    let src = match fs::read_to_string(&routes_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("serve: read {}: {}", routes_path, e);
            return 1;
        }
    };

    // Validate the manifest ONCE up front (in the main thread) so a broken
    // routes.fk fails fast with a clear message before any worker spins up.
    // Each worker re-loads the same source into its OWN kernel+arena below.
    if let Err(e) = build_worker_kernel(&src, &routes_path) {
        eprintln!("serve: {}", e);
        return 1;
    }

    // Size the pool. Default to the host's available parallelism so the box's
    // cores are used; cap at 64 so a pathological --workers can't exhaust the
    // thread table; floor at 1 so the pool always has at least one worker.
    let default_workers = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4);
    let n_workers = workers.unwrap_or(default_workers).clamp(1, 64);

    let listener = match TcpListener::bind(("127.0.0.1", port)) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("serve: bind 127.0.0.1:{}: {}", port, e);
            return 1;
        }
    };

    // The shared work queue: the accept loop sends each accepted stream; the
    // receiver is shared across workers behind a Mutex (the classic std
    // threadpool — mpsc + Arc<Mutex<Receiver>>). The lock guards only the
    // dequeue; request handling runs lock-free on each worker's own kernel,
    // so N workers serve N requests truly in parallel.
    let (tx, rx) = mpsc::channel::<TcpStream>();
    let rx = Arc::new(Mutex::new(rx));
    let src = Arc::new(src);
    let routes_path_arc = Arc::new(routes_path);
    let upstream_arc = Arc::new(upstream);

    // Spawn the pool. Each worker builds its OWN Kernel + Arena from the source
    // (routes.fk loaded once per worker at startup), then drains the queue.
    // Workers get an EXPLICIT generous stack: the kernel's value-walk is a
    // recursive tree-walker, so a deeply self-recursive native handler needs
    // real stack depth. A spawned thread's default stack (~2 MiB on many
    // platforms) is smaller than the main thread's (~8 MiB), and a Rust stack
    // overflow ABORTS THE PROCESS (it is not a catchable panic) — so an
    // under-sized worker stack would let one pathological request take the
    // whole server down. WORKER_STACK_SIZE exceeds the typical main-thread
    // stack so a worker handles at least the recursion depth the single-thread
    // path did. (Unbounded recursion is still the handler's responsibility; the
    // generous stack matches the prior behavior rather than promising infinity.)
    let mut handles = Vec::with_capacity(n_workers);
    for id in 0..n_workers {
        let src = Arc::clone(&src);
        let routes_path = Arc::clone(&routes_path_arc);
        let upstream = Arc::clone(&upstream_arc);
        let rx = Arc::clone(&rx);
        let builder = thread::Builder::new()
            .name(format!("kernel-worker-{}", id))
            .stack_size(WORKER_STACK_SIZE);
        match builder.spawn(move || {
            worker_loop(id, src, routes_path, upstream, rx);
        }) {
            Ok(h) => handles.push(h),
            Err(e) => {
                eprintln!("serve: failed to spawn worker {}: {}", id, e);
                // Workers already spawned keep serving; a partial pool is
                // better than none. If NONE spawned, the accept loop's send
                // will fail and we stop cleanly below.
            }
        }
    }
    if handles.is_empty() {
        eprintln!("serve: no workers could be spawned");
        return 1;
    }

    // Re-resolve the route list once (in the main thread, throwaway kernel)
    // purely to print the startup banner — the workers hold the live copies.
    if let Ok((_, _, route_pairs)) = build_worker_kernel(&src, &routes_path_arc) {
        eprintln!(
            "form-kernel-rust serve: listening on 127.0.0.1:{} ({} worker{}, {} native route{})",
            port,
            n_workers,
            if n_workers == 1 { "" } else { "s" },
            route_pairs.len(),
            if route_pairs.len() == 1 { "" } else { "s" }
        );
        for r in &route_pairs {
            eprintln!("  {} -> native (Form handler)", r.0);
        }
    }
    match upstream_arc.as_ref() {
        Some(u) => eprintln!("  *  -> fan-out to Python upstream {}", u),
        None => eprintln!("  *  -> 404 (no --upstream; fan-out arm inactive)"),
    }

    // The accept loop is now thin: it only hands each accepted stream to the
    // pool. The kernel work happens on the workers, concurrently.
    for incoming in listener.incoming() {
        let stream = match incoming {
            Ok(s) => s,
            Err(_) => continue,
        };
        if tx.send(stream).is_err() {
            // All workers gone — nothing can serve; stop accepting.
            break;
        }
    }

    // Listener ended: drop the sender so workers see the channel close and
    // exit, then join them so no thread is leaked.
    drop(tx);
    for h in handles {
        let _ = h.join();
    }
    0
}

// Maximum request body the router will read into memory. A body larger than
// this is rejected with 413 rather than letting a malicious/huge Content-Length
// OOM the process. 1 MiB is generous for form posts and JSON payloads; true
// streaming bodies are a named-later breath (KERNEL_AS_ROUTER.md request row).
const MAX_BODY_BYTES: usize = 1024 * 1024;

// The outcome of reading a request: either the parsed (head, body), or a signal
// that the body exceeded MAX_BODY_BYTES (the caller answers 413), or a read
// error / empty peer (the caller drops the connection silently).
enum RequestRead {
    Ok(String, Vec<u8>),
    TooLarge,
    Error,
}

// Read a full HTTP request: the header block (up to the `\r\n\r\n` terminator)
// followed by exactly `Content-Length` body bytes if that header is present.
// The first read may already contain some or all of the body (it arrived in the
// same TCP segment), so bytes captured past the terminator are counted toward
// the body and only the remainder is read from the socket. Returns the raw head
// string (request line + headers, terminator excluded) and the body bytes.
//
// This replaces the old single 8 KiB read: it honors Content-Length across as
// many `read` calls as the body needs, so a body larger than one buffer is
// fully captured (the correctness property the single-buffer read failed).
//
// KEEP-ALIVE: `carry` holds bytes that arrived on this persistent connection
// but belong to the NEXT request — the classic pipelining hazard. A single
// `read` can pull the tail of request N AND the head (or all) of request N+1;
// those extra bytes must NOT be dropped between requests. So this fn (1) seeds
// its read buffer from `carry` before touching the socket, and (2) stashes any
// bytes captured past this request's end (header terminator + Content-Length)
// back into `carry` for the next call. The next iteration of the keep-alive
// loop therefore starts exactly at the next request's first byte. A clean EOF
// with no bytes buffered (idle connection closed or read-timeout fired) returns
// `Error`, which the keep-alive loop reads as "connection done — stop looping."
fn read_request(stream: &mut TcpStream, carry: &mut Vec<u8>) -> RequestRead {
    // Seed from any leftover bytes carried in from the previous request on this
    // same connection (drained out of `carry`), then read more as needed.
    let mut raw: Vec<u8> = std::mem::take(carry);
    let mut buf = [0u8; 8192];
    // Phase 1: read until the header terminator is seen (or EOF / cap). The
    // carried bytes may ALREADY contain the full header block, so check before
    // the first socket read — otherwise a pipelined request would block on a
    // read that never comes.
    let header_end: Option<usize> = if let Some(t) = find_header_end(&raw) {
        Some(t)
    } else {
        loop {
            match stream.read(&mut buf) {
                Ok(0) => break find_header_end(&raw), // peer closed; use what we have
                Ok(n) => {
                    raw.extend_from_slice(&buf[..n]);
                    if let Some(t) = find_header_end(&raw) {
                        break Some(t);
                    }
                    // Guard: the header block alone must not grow without bound.
                    if raw.len() > MAX_BODY_BYTES {
                        return RequestRead::TooLarge;
                    }
                }
                // A read error here also covers the idle read-timeout firing on
                // a kept-alive connection (WouldBlock/TimedOut) — the loop ends.
                Err(_) => return RequestRead::Error,
            }
        }
    };
    if raw.is_empty() {
        return RequestRead::Error; // nothing arrived at all (clean EOF / idle close)
    }
    // `header_end` is the index just past "\r\n\r\n" when found. The head text
    // (terminator excluded) is everything before it; if no terminator was seen
    // the whole buffer is the head and there is no body.
    let (head_end_excl_term, body_start) = match header_end {
        Some(t) => (t - 4, t),
        None => (raw.len(), raw.len()),
    };
    let head = String::from_utf8_lossy(&raw[..head_end_excl_term]).to_string();

    // Phase 2: if Content-Length says there's a body, read exactly that many
    // bytes, counting whatever already arrived past the header terminator. With
    // NO Content-Length there is no body — everything past the terminator
    // belongs to the NEXT request and is carried forward (not mis-read as this
    // request's body, which would corrupt a keep-alive connection).
    let total = match parse_content_length(&head) {
        Some(t) => {
            if t > MAX_BODY_BYTES {
                return RequestRead::TooLarge; // oversized — caller answers 413
            }
            t
        }
        None => 0,
    };
    let mut body: Vec<u8> = raw[body_start..].to_vec();
    while body.len() < total {
        match stream.read(&mut buf) {
            Ok(0) => break, // peer closed early; return the partial body honestly
            Ok(n) => body.extend_from_slice(&buf[..n]),
            Err(_) => break,
        }
    }
    // Any bytes captured past this request's body belong to the NEXT request on
    // the connection — carry them forward so the next read_request starts there.
    if body.len() > total {
        carry.extend_from_slice(&body[total..]);
        body.truncate(total);
    }
    RequestRead::Ok(head, body)
}

// Find the index just past the first "\r\n\r\n" header terminator, if present.
fn find_header_end(raw: &[u8]) -> Option<usize> {
    raw.windows(4)
        .position(|w| w == b"\r\n\r\n")
        .map(|i| i + 4)
}

// Parse a raw header block (the lines AFTER the request/status line, terminator
// excluded) into an ordered list of (name, value) pairs — names kept as sent so
// they relay verbatim, values trimmed. The first line (request line on the way
// up, status line on the way back) is the caller's; this skips it. This is the
// ONE header-capture shape both hops use: the request headers forwarded to the
// upstream and the upstream's response headers relayed to the client both come
// from here, so a header is never silently dropped because two code paths parsed
// the block differently.
fn parse_headers(head: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    for line in head.lines().skip(1) {
        if line.is_empty() {
            continue;
        }
        if let Some((name, value)) = line.split_once(':') {
            out.push((name.trim().to_string(), value.trim().to_string()));
        }
    }
    out
}

// HOP-BY-HOP headers (RFC 7230 §6.1) — meaningful only for a SINGLE transport
// hop, NEVER forwarded by a proxy to the next hop. The router is a hop on both
// sides: it owns its client-hop framing (Connection/Content-Length) and its
// upstream-hop framing independently, so these must be stripped in BOTH
// directions rather than blindly relayed. `Connection`, `Keep-Alive`,
// `Transfer-Encoding`, `Upgrade`, the `Proxy-*` pair, plus the rarely-seen TE /
// Trailer. Content-Length is handled separately (the router sets its own from
// the body it holds), so it is treated as framing the router owns, not relayed.
fn is_hop_by_hop(name: &str) -> bool {
    let n = name.trim();
    n.eq_ignore_ascii_case("connection")
        || n.eq_ignore_ascii_case("keep-alive")
        || n.eq_ignore_ascii_case("transfer-encoding")
        || n.eq_ignore_ascii_case("upgrade")
        || n.eq_ignore_ascii_case("proxy-authenticate")
        || n.eq_ignore_ascii_case("proxy-authorization")
        || n.eq_ignore_ascii_case("te")
        || n.eq_ignore_ascii_case("trailer")
}

// Whether a request header should be forwarded UP to the upstream. Strips the
// hop-by-hop set (the router owns its upstream-hop framing) AND the framing the
// router re-derives from the body it captured: `Host` is rewritten to the
// upstream host, and `Content-Length` is set from the captured body's true
// length (a forwarded client Content-Length could disagree with the bytes the
// router actually holds — double-framing). Everything end-to-end —
// Authorization, Cookie, Accept*, User-Agent, X-*, Content-Type, … — passes.
fn forward_request_header(name: &str) -> bool {
    let n = name.trim();
    !(is_hop_by_hop(n)
        || n.eq_ignore_ascii_case("host")
        || n.eq_ignore_ascii_case("content-length"))
}

// Whether an upstream RESPONSE header should be relayed DOWN to the client.
// Strips the hop-by-hop set AND the framing the router owns on its client hop:
// `Content-Length` (the router sets its own from the body it relays) and
// `Content-Type` (relayed via the dedicated content_type slot in the emit shape,
// so it is not duplicated here). Everything else end-to-end — Set-Cookie,
// Cache-Control, Location, ETag, X-*, … — passes through to the client.
fn relay_response_header(name: &str) -> bool {
    let n = name.trim();
    !(is_hop_by_hop(n)
        || n.eq_ignore_ascii_case("content-length")
        || n.eq_ignore_ascii_case("content-type"))
}

// Pull the Content-Length value out of a raw header block (case-insensitive
// header name). Returns None when absent or unparseable.
fn parse_content_length(head: &str) -> Option<usize> {
    for line in head.lines() {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("content-length") {
                return value.trim().parse::<usize>().ok();
            }
        }
    }
    None
}

// Pull the Content-Type value (lowercased, parameters stripped) out of a raw
// header block. "application/json; charset=utf-8" -> "application/json".
fn parse_content_type(head: &str) -> String {
    for line in head.lines() {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("content-type") {
                let v = value.trim();
                let main = v.split(';').next().unwrap_or(v);
                return main.trim().to_ascii_lowercase();
            }
        }
    }
    String::new()
}

// Decide whether the CLIENT wants the connection kept alive, per RFC 7230. The
// request line's HTTP version sets the default; an explicit `Connection` header
// overrides it:
//   HTTP/1.1 (and higher) -> keep-alive by default; close only if the client
//     sent `Connection: close`.
//   HTTP/1.0 -> close by default; keep-alive only if the client sent the
//     legacy `Connection: keep-alive`.
// The server may still force-close on top of this (e.g. an error whose framing
// is uncertain) — that is the caller's decision; this only reads client intent.
fn head_keep_alive(head: &str) -> bool {
    let request_line = head.lines().next().unwrap_or("");
    let is_http11_or_higher = request_line
        .rsplit(' ')
        .next()
        .map(|v| v == "HTTP/1.1" || (v.starts_with("HTTP/") && v > "HTTP/1.0"))
        .unwrap_or(false);
    // The Connection header value (lowercased) if present.
    let mut connection: Option<String> = None;
    for line in head.lines().skip(1) {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("connection") {
                connection = Some(value.trim().to_ascii_lowercase());
                break;
            }
        }
    }
    match connection.as_deref() {
        Some(v) if v.split(',').any(|t| t.trim() == "close") => false,
        Some(v) if v.split(',').any(|t| t.trim() == "keep-alive") => true,
        // No explicit token -> the HTTP version's default.
        _ => is_http11_or_higher,
    }
}

// Parse a request body into the SAME (key, value) alist shape the query string
// already uses, so a handler reads body fields exactly like query fields
// (core-abstraction-first: ONE request-data shape regardless of how the data
// arrived). The marshalling depends on Content-Type:
//   - application/x-www-form-urlencoded -> each `k=v&...` pair url-decoded into
//     the alist (reuses the query-pair parsing), so a form-POST handler sees its
//     fields uniformly with query params.
//   - application/json -> the raw JSON string is captured under the reserved key
//     `__body__` so a handler CAN read it via (assoc "__body__" q). A full
//     JSON->Form-value parse is a deeper, named-later breath; raw-capture is the
//     honest first step that already lets a handler process the payload.
//   - anything else (with a non-empty body) -> the raw bytes captured under
//     `__body__`. The handler always gets a well-formed alist.
fn parse_request_body(content_type: &str, body: &[u8]) -> Vec<(String, String)> {
    if body.is_empty() {
        return Vec::new();
    }
    if content_type == "application/x-www-form-urlencoded" {
        let s = String::from_utf8_lossy(body);
        let mut pairs = Vec::new();
        for pair in s.split('&') {
            if pair.is_empty() {
                continue;
            }
            let (k, v) = match pair.find('=') {
                Some(i) => (pair[..i].to_string(), pair[i + 1..].to_string()),
                None => (pair.to_string(), String::new()),
            };
            pairs.push((url_decode(&k), url_decode(&v)));
        }
        pairs
    } else {
        // application/json and everything else: capture the raw body so the
        // handler can process it. JSON is left as the raw string by design
        // (raw-capture, not yet a structural parse).
        vec![(
            "__body__".to_string(),
            String::from_utf8_lossy(body).to_string(),
        )]
    }
}

// Parse the request line "GET /path?k=v HTTP/1.0" into
// (method, target, path, query).
// Query string is decoded as a flat list of (key, value) pairs — sufficient
// for the proof-of-shape; no percent-decoding beyond '+' → ' '.
fn parse_request_line(req: &str) -> (String, String, String, Vec<(String, String)>) {
    let line = req.lines().next().unwrap_or("");
    let mut parts = line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let target = parts.next().unwrap_or("/").to_string();
    let (path, qs) = match target.find('?') {
        Some(i) => (target[..i].to_string(), target[i + 1..].to_string()),
        None => (target.clone(), String::new()),
    };
    let mut query = Vec::new();
    if !qs.is_empty() {
        for pair in qs.split('&') {
            let (k, v) = match pair.find('=') {
                Some(i) => (pair[..i].to_string(), pair[i + 1..].to_string()),
                None => (pair.to_string(), String::new()),
            };
            query.push((url_decode(&k), url_decode(&v)));
        }
    }
    (method, target, path, query)
}

fn url_decode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => {
                out.push(' ');
                i += 1;
            }
            b'%' if i + 2 < bytes.len() => {
                let hi = (bytes[i + 1] as char).to_digit(16);
                let lo = (bytes[i + 2] as char).to_digit(16);
                if let (Some(h), Some(l)) = (hi, lo) {
                    out.push(((h * 16 + l) as u8) as char);
                    i += 3;
                } else {
                    out.push(bytes[i] as char);
                    i += 1;
                }
            }
            other => {
                out.push(other as char);
                i += 1;
            }
        }
    }
    out
}

fn fanout_request(
    upstream: &str,
    method: &str,
    target: &str,
    req_headers: &[(String, String)],
    body: &[u8],
) -> FanoutResult {
    match fanout_request_result(upstream, method, target, req_headers, body) {
        Ok(v) => v,
        Err(e) => FanoutResult {
            status: "502 Bad Gateway".to_string(),
            content_type: String::new(),
            headers: Vec::new(),
            body: format!("fan-out upstream error: {}\n", e),
        },
    }
}

// The ONE response-emit shape — core-abstraction-first: every response (native,
// fan-out, error) is written here, so the framing the router owns is written in
// exactly one place and cannot diverge between arms.
//
// FRAMING THE ROUTER OWNS (always, on every response):
//   - Content-Length: ACCURATE, from the body it holds — that is what makes
//     keep-alive work without chunked encoding (the client knows precisely where
//     the body ends and the next response begins).
//   - Connection: `keep-alive` when the connection will serve more requests,
//     `close` on the final response (client asked to close, idle timeout, EOF,
//     or an error whose framing is uncertain).
//   - X-Form-Router: which arm served this (`native-kernel` / `fanout-python` /
//     a control marker).
// These are the router's client-hop framing; a relayed upstream header can NEVER
// clobber them (hop-by-hop + Content-Length/Content-Type are filtered out of
// `relayed` by relay_response_header before they reach here).
//
// `content_type` is the response's Content-Type: the upstream's real one on a
// fan-out (so a JSON/HTML route survives the proxy instead of being flattened to
// text/plain), or the native default `text/plain; charset=utf-8` when empty.
// `relayed` is the upstream's other end-to-end headers (Set-Cookie,
// Cache-Control, Location, ETag, X-*, …) on a fan-out, EMPTY for native/error
// responses. Chunked transfer encoding remains a named-later breath
// (KERNEL_AS_ROUTER.md HTTP-version row).
fn http_response(
    status: &str,
    body: &str,
    router: &str,
    keep_alive: bool,
    content_type: &str,
    relayed: &[(String, String)],
) -> String {
    let ct = if content_type.trim().is_empty() {
        "text/plain; charset=utf-8"
    } else {
        content_type.trim()
    };
    // Start with the framing the router owns, then append the relayed end-to-end
    // headers verbatim (each already filtered to exclude hop-by-hop and the
    // router-owned framing). Content-Type carries its own dedicated line.
    let mut out = format!(
        "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nX-Form-Router: {}\r\nConnection: {}\r\n",
        status,
        ct,
        body.as_bytes().len(),
        router,
        if keep_alive { "keep-alive" } else { "close" },
    );
    for (name, value) in relayed {
        out.push_str(&format!("{}: {}\r\n", name, value));
    }
    out.push_str("\r\n");
    out.push_str(body);
    out
}

// The fan-out hop's full result: the upstream's status line, its CONTENT-TYPE
// (so the client gets a JSON/HTML route's real type, not a flattened
// text/plain), its other RELAYABLE end-to-end response headers (Set-Cookie,
// Cache-Control, Location, …), and the body. Hop-by-hop and router-owned framing
// headers are already filtered out of `headers` (and Content-Type lifted into
// its own slot) so the caller relays them safely beside the router's own
// framing.
struct FanoutResult {
    status: String,
    content_type: String,
    headers: Vec<(String, String)>,
    body: String,
}

fn fanout_request_result(
    upstream: &str,
    method: &str,
    target: &str,
    req_headers: &[(String, String)],
    body: &[u8],
) -> Result<FanoutResult, String> {
    let (host, port, base_path) = parse_http_upstream(upstream)?;
    let request_target = format!(
        "{}{}",
        base_path,
        if target.starts_with('/') { target } else { "/" }
    );
    let mut stream = TcpStream::connect((host.as_str(), port))
        .map_err(|e| format!("connect {}:{}: {}", host, port, e))?;
    // Forward the request line with the ORIGINAL method. The router owns the
    // upstream-hop framing: `Host` is rewritten to the upstream, `Connection:
    // close` is the router's choice (it does not reuse the upstream connection —
    // a named-later breath), and Content-Length is set from the body the router
    // actually captured. The CLIENT's end-to-end headers (Authorization, Cookie,
    // Accept*, User-Agent, Content-Type, X-*, …) are then forwarded verbatim so
    // an authenticated/content-typed route is fronted truthfully; hop-by-hop and
    // router-owned framing headers are filtered by forward_request_header.
    let mut head = format!(
        "{} {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n",
        method, request_target, host
    );
    for (name, value) in req_headers {
        if forward_request_header(name) {
            head.push_str(&format!("{}: {}\r\n", name, value));
        }
    }
    // Content-Length from the captured body's TRUE length (never the client's
    // forwarded one, which could disagree with the bytes we hold). GET/HEAD with
    // no body send no Content-Length.
    if !body.is_empty() {
        head.push_str(&format!("Content-Length: {}\r\n", body.len()));
    }
    head.push_str("\r\n");
    let mut request: Vec<u8> = head.into_bytes();
    request.extend_from_slice(body);
    stream
        .write_all(&request)
        .map_err(|e| format!("write request: {}", e))?;
    let mut response_bytes = Vec::new();
    stream
        .read_to_end(&mut response_bytes)
        .map_err(|e| format!("read response: {}", e))?;
    let response = String::from_utf8_lossy(&response_bytes).to_string();
    let status = response
        .lines()
        .next()
        .and_then(|line| line.split_once(' ').map(|(_, rest)| rest.to_string()))
        .unwrap_or_else(|| "502 Bad Gateway".to_string());
    // Split the head block from the body. The head string (terminator excluded)
    // feeds parse_content_type / parse_headers — the SAME parsers the request
    // side uses (one header-capture shape, both directions).
    let (head_block, body_text) = match response.find("\r\n\r\n") {
        Some(i) => (&response[..i], response[i + 4..].to_string()),
        None => match response.find("\n\n") {
            Some(i) => (&response[..i], response[i + 2..].to_string()),
            None => (response.as_str(), String::new()),
        },
    };
    let content_type = parse_content_type(head_block);
    // Relay the upstream's other end-to-end response headers; hop-by-hop and the
    // router-owned framing (Content-Length, Content-Type) are filtered out so
    // they cannot clobber the framing http_response writes.
    let headers: Vec<(String, String)> = parse_headers(head_block)
        .into_iter()
        .filter(|(name, _)| relay_response_header(name))
        .collect();
    Ok(FanoutResult {
        status,
        content_type,
        headers,
        body: body_text,
    })
}

fn parse_http_upstream(upstream: &str) -> Result<(String, u16, String), String> {
    let rest = upstream
        .strip_prefix("http://")
        .ok_or_else(|| "only http:// upstream URLs are supported".to_string())?;
    let (host_port, path) = match rest.split_once('/') {
        Some((hp, p)) => (hp, format!("/{}", p.trim_end_matches('/'))),
        None => (rest, String::new()),
    };
    if host_port.is_empty() {
        return Err("upstream host is empty".to_string());
    }
    let (host, port) = match host_port.rsplit_once(':') {
        Some((h, p)) => {
            let port = p
                .parse::<u16>()
                .map_err(|_| format!("bad upstream port: {}", p))?;
            (h.to_string(), port)
        }
        None => (host_port.to_string(), 80),
    };
    if host.is_empty() {
        return Err("upstream host is empty".to_string());
    }
    Ok((host, port, path))
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
        "serve" => cli_serve(&args[1..]),
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
