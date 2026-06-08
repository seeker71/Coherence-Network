// formats.rs — substrate-resident numeric format library, Rust kernel.
//
// Numeric values are (semantic-kind, format-recipe, encoded-value) triples.
// Format-recipes are substrate cells with `storage-hint` and `arithmetic-hint`
// children. Adding a new format is a substrate write, not a kernel patch.
//
// This module is the Rust mirror of `form/form-kernel-ts/src/formats.ts`
// and `numeric.ts`. The canonical contract lives at
// `docs/coherence-substrate/numeric-formats.canonical.json`; every kernel reads
// it on startup so content-addressing produces identical NodeIDs across
// kernels for the same recipe structure.
//
// See docs/coherence-substrate/numeric-types-plan.md for the architecture.

use std::collections::HashMap;
use std::path::PathBuf;
use std::rc::Rc;
use std::time::Instant;

use serde::{Deserialize, Serialize};

use crate::{Kernel, NodeID, LEVEL_BASIC};

// ---------------------------------------------------------------------------
// Enums — match canonical JSON tables exactly. #[repr(u32)] keeps the
// projection to/from substrate codes a no-op cast.
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum SemanticKind {
    Cardinal = 1,
    Integer = 2,
    Rational = 3,
    Real = 4,
    Complex = 5,
    BitPattern = 6,
    LogValue = 7,
    Probability = 8,
    Interval = 9,
    Ordinal = 10,
    Amplitude = 11,
    Phase = 12,
    Measure = 13,
}

impl SemanticKind {
    pub fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "CARDINAL" => SemanticKind::Cardinal,
            "INTEGER" => SemanticKind::Integer,
            "RATIONAL" => SemanticKind::Rational,
            "REAL" => SemanticKind::Real,
            "COMPLEX" => SemanticKind::Complex,
            "BIT_PATTERN" => SemanticKind::BitPattern,
            "LOG_VALUE" => SemanticKind::LogValue,
            "PROBABILITY" => SemanticKind::Probability,
            "INTERVAL" => SemanticKind::Interval,
            "ORDINAL" => SemanticKind::Ordinal,
            "AMPLITUDE" => SemanticKind::Amplitude,
            "PHASE" => SemanticKind::Phase,
            "MEASURE" => SemanticKind::Measure,
            _ => return None,
        })
    }
}

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum EncodingKind {
    TwosComplement = 1,
    SignMagnitude = 2,
    Unsigned = 3,
    Ieee754 = 4,
    Posit = 5,
    LookupTable = 6,
    BlockFp = 7,
    LogSpace = 8,
    RationalPair = 9,
    ComplexPair = 10,
    RawBits = 11,
}

impl EncodingKind {
    pub fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "TWOS_COMPLEMENT" => EncodingKind::TwosComplement,
            "SIGN_MAGNITUDE" => EncodingKind::SignMagnitude,
            "UNSIGNED" => EncodingKind::Unsigned,
            "IEEE_754" => EncodingKind::Ieee754,
            "POSIT" => EncodingKind::Posit,
            "LOOKUP_TABLE" => EncodingKind::LookupTable,
            "BLOCK_FP" => EncodingKind::BlockFp,
            "LOG_SPACE" => EncodingKind::LogSpace,
            "RATIONAL_PAIR" => EncodingKind::RationalPair,
            "COMPLEX_PAIR" => EncodingKind::ComplexPair,
            "RAW_BITS" => EncodingKind::RawBits,
            _ => return None,
        })
    }
}

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum ArithHintCode {
    NativeFp = 1,
    NativeInt = 2,
    NativeIntNarrow = 3,
    Bigint = 4,
    TableLookupViaFp32 = 5,
    DequantFp32ThenNative = 6,
    SoftwareFpViaFp32 = 7,
    SoftwarePosit = 8,
    XorPopcount = 9,
    LogaddexpLogsubexp = 10,
    RationalBigint = 11,
}

impl ArithHintCode {
    pub fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "native-fp" => ArithHintCode::NativeFp,
            "native-int" => ArithHintCode::NativeInt,
            "native-int-narrow" => ArithHintCode::NativeIntNarrow,
            "bigint" => ArithHintCode::Bigint,
            "table-lookup-via-fp32" => ArithHintCode::TableLookupViaFp32,
            "dequant-fp32-then-native" => ArithHintCode::DequantFp32ThenNative,
            "software-fp-via-fp32" => ArithHintCode::SoftwareFpViaFp32,
            "software-posit" => ArithHintCode::SoftwarePosit,
            "xor-popcount" => ArithHintCode::XorPopcount,
            "logaddexp-logsubexp" => ArithHintCode::LogaddexpLogsubexp,
            "rational-bigint" => ArithHintCode::RationalBigint,
            _ => return None,
        })
    }
}

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum ArithOpCode {
    Add = 1,
    Sub = 2,
    Mul = 3,
    Div = 4,
    Mod = 5,
}

impl ArithOpCode {
    #[cfg(test)]
    pub fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "add" => ArithOpCode::Add,
            "sub" => ArithOpCode::Sub,
            "mul" => ArithOpCode::Mul,
            "div" => ArithOpCode::Div,
            "mod" => ArithOpCode::Mod,
            _ => return None,
        })
    }
}

// RBasic slots for the format-recipes and the format-driven numeric leaves.
// Cross-kernel agreement requires these constants to match the canonical JSON.
pub const RBASIC_FORMAT: u32 = 50;
#[allow(dead_code)]
pub const RBASIC_NUMERIC: u32 = 51;

// ---------------------------------------------------------------------------
// FormatRecipe — the in-Rust shadow of the substrate cell that defines a
// numeric format. The substrate holds the full recipe tree; this struct
// holds the same fields cached for fast in-kernel access.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct FormatRecipe {
    pub node_id: NodeID,
    pub name: String,
    pub bits: u32,
    #[cfg(test)]
    pub storage_hint: String,
    #[cfg(test)]
    pub arithmetic_hint: String,
    pub arith_hint_code: u32,
}

// ---------------------------------------------------------------------------
// Canonical JSON shape — read at runtime, never hardcoded.
// ---------------------------------------------------------------------------

#[derive(Deserialize, Serialize, Debug)]
pub struct CanonicalSpec {
    pub version: u32,
    pub formats: Vec<CanonicalFormat>,
    pub conformance_vectors: ConformanceVectors,
}

#[derive(Deserialize, Serialize, Debug)]
pub struct CanonicalFormat {
    pub name: String,
    pub semantic_kind: String,
    pub encoding: String,
    pub bits: u32,
    pub storage_hint: String,
    pub arithmetic_hint: String,
    #[serde(default)]
    pub mantissa_bits: Option<u32>,
    #[serde(default)]
    pub exponent_bits: Option<u32>,
    #[serde(default)]
    pub exponent_bias: Option<u32>,
    #[serde(default)]
    pub posit_n: Option<u32>,
    #[serde(default)]
    pub posit_es: Option<u32>,
    #[serde(default)]
    pub lookup_values: Option<Vec<f64>>,
}

#[derive(Deserialize, Serialize, Debug)]
pub struct ConformanceVectors {
    pub vectors: Vec<ConformanceVector>,
    #[serde(default)]
    pub canonicalization_vectors: Vec<serde_json::Value>,
}

#[derive(Deserialize, Serialize, Debug)]
pub struct ConformanceVector {
    pub format: String,
    pub op: String,
    pub a: serde_json::Value,
    pub b: serde_json::Value,
    pub expected: serde_json::Value,
}

// Resolve the canonical JSON path from the repository layout. Configuration is
// file-backed; the kernel does not take hidden environment fallbacks here.
pub fn canonical_json_path() -> PathBuf {
    // CARGO_MANIFEST_DIR points at form/form-kernel-rust at build time.
    let manifest = env!("CARGO_MANIFEST_DIR");
    let mut p = PathBuf::from(manifest);
    // …/form/form-kernel-rust → up twice → repo root → docs/...
    p.pop();
    p.pop();
    p.push("docs/coherence-substrate/numeric-formats.canonical.json");
    p
}

pub fn load_canonical_spec() -> CanonicalSpec {
    let path = canonical_json_path();
    let body = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("formats: cannot read {}: {}", path.display(), e));
    serde_json::from_str(&body).unwrap_or_else(|e| panic!("formats: invalid canonical JSON: {}", e))
}

// ---------------------------------------------------------------------------
// build_format_library — interns every canonical format-recipe in the
// listed order. Cross-kernel agreement requires the order + children layout
// to match every other kernel that reads the same JSON.
// ---------------------------------------------------------------------------

pub struct FormatLibrary {
    pub recipes: Vec<FormatRecipe>,
    pub by_name: HashMap<String, usize>,
}

impl FormatLibrary {
    pub fn get(&self, name: &str) -> &FormatRecipe {
        let idx = self
            .by_name
            .get(name)
            .copied()
            .unwrap_or_else(|| panic!("FormatLibrary: unknown format `{}`", name));
        &self.recipes[idx]
    }
}

pub fn build_format_library(k: &mut Kernel) -> FormatLibrary {
    let spec = load_canonical_spec();
    let mut recipes = Vec::with_capacity(spec.formats.len());
    let mut by_name = HashMap::new();
    for (i, cf) in spec.formats.iter().enumerate() {
        let recipe = intern_format(k, cf);
        by_name.insert(recipe.name.clone(), i);
        recipes.push(recipe);
    }
    FormatLibrary { recipes, by_name }
}

fn intern_format(k: &mut Kernel, cf: &CanonicalFormat) -> FormatRecipe {
    let sk = SemanticKind::from_str(&cf.semantic_kind)
        .unwrap_or_else(|| panic!("unknown semantic kind: {}", cf.semantic_kind));
    let enc = EncodingKind::from_str(&cf.encoding)
        .unwrap_or_else(|| panic!("unknown encoding: {}", cf.encoding));
    let hint = ArithHintCode::from_str(&cf.arithmetic_hint)
        .unwrap_or_else(|| panic!("unknown arithmetic-hint: {}", cf.arithmetic_hint));

    // Five required children, in canonical order.
    let mut children: Vec<NodeID> = vec![
        k.intern_trivial_int(sk as u32 as i64),
        k.intern_trivial_int(enc as u32 as i64),
        k.intern_trivial_int(cf.bits as i64),
        k.intern_string(&cf.storage_hint),
        k.intern_string(&cf.arithmetic_hint),
    ];

    // Optional extras, in the order spelled out in the canonical JSON's
    // `children_after_required` list.
    if let Some(m) = cf.mantissa_bits {
        children.push(k.intern_trivial_int(m as i64));
    }
    if let Some(e) = cf.exponent_bits {
        children.push(k.intern_trivial_int(e as i64));
    }
    if let Some(b) = cf.exponent_bias {
        children.push(k.intern_trivial_int(b as i64));
    }
    if let Some(n) = cf.posit_n {
        children.push(k.intern_trivial_int(n as i64));
    }
    if let Some(es) = cf.posit_es {
        children.push(k.intern_trivial_int(es as i64));
    }
    if let Some(values) = &cf.lookup_values {
        for v in values {
            // Each float contributes two i32 children: low 32 bits, then high.
            let bits = v.to_bits();
            let lo = (bits & 0xffff_ffff) as i32 as i64;
            let hi = ((bits >> 32) & 0xffff_ffff) as i32 as i64;
            children.push(k.intern_trivial_int(lo));
            children.push(k.intern_trivial_int(hi));
        }
    }

    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_FORMAT,
        inst: enc as u32,
    };
    let node_id = k.intern(category, children);

    FormatRecipe {
        node_id,
        name: cf.name.clone(),
        bits: cf.bits,
        #[cfg(test)]
        storage_hint: cf.storage_hint.clone(),
        #[cfg(test)]
        arithmetic_hint: cf.arithmetic_hint.clone(),
        arith_hint_code: hint as u32,
    }
}

// ---------------------------------------------------------------------------
// Value — unified across formats. Floats live in `f64`; 64-bit integers
// have to live in `i128` so u64::MAX can be represented losslessly.
// ---------------------------------------------------------------------------

#[derive(Copy, Clone, Debug)]
pub enum NumVal {
    Float(f64),
    Int(i128),
}

impl NumVal {
    pub fn to_f64(self) -> f64 {
        match self {
            NumVal::Float(f) => f,
            NumVal::Int(i) => i as f64,
        }
    }
    pub fn to_i128(self) -> i128 {
        match self {
            NumVal::Int(i) => i,
            NumVal::Float(f) => f as i128,
        }
    }
}

// ---------------------------------------------------------------------------
// Pass-0 dispatcher — applyArith reads the recipe's arith_hint_code and
// branches per call. No closure cache; the dispatcher does the work
// every operation. Mirrors the TS `applyArithCode`.
// ---------------------------------------------------------------------------

pub fn apply_arith(fmt: &FormatRecipe, op: u32, a: NumVal, b: NumVal) -> NumVal {
    match fmt.arith_hint_code {
        x if x == ArithHintCode::NativeFp as u32 => {
            let fa = a.to_f64();
            let fb = b.to_f64();
            NumVal::Float(match op {
                x if x == ArithOpCode::Add as u32 => fa + fb,
                x if x == ArithOpCode::Sub as u32 => fa - fb,
                x if x == ArithOpCode::Mul as u32 => fa * fb,
                x if x == ArithOpCode::Div as u32 => fa / fb,
                x if x == ArithOpCode::Mod as u32 => fa - (fa / fb).floor() * fb,
                _ => 0.0,
            })
        }
        x if x == ArithHintCode::NativeInt as u32 => {
            // The canonical contract is "JS Number | 0 chains" → i32 arithmetic
            // with wraparound. Native-int formats with bits >32 (i64, u64) use
            // the Bigint hint instead, so this arm is i32-shaped.
            let ia = a.to_i128() as i32;
            let ib = b.to_i128() as i32;
            NumVal::Int(match op {
                x if x == ArithOpCode::Add as u32 => ia.wrapping_add(ib) as i128,
                x if x == ArithOpCode::Sub as u32 => ia.wrapping_sub(ib) as i128,
                x if x == ArithOpCode::Mul as u32 => ia.wrapping_mul(ib) as i128,
                x if x == ArithOpCode::Div as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia.wrapping_div(ib) as i128
                    }
                }
                x if x == ArithOpCode::Mod as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia.wrapping_rem(ib) as i128
                    }
                }
                _ => 0,
            })
        }
        x if x == ArithHintCode::NativeIntNarrow as u32 => {
            let ia = a.to_i128() as i32;
            let ib = b.to_i128() as i32;
            let bits = fmt.bits;
            let raw = match op {
                x if x == ArithOpCode::Add as u32 => ia.wrapping_add(ib),
                x if x == ArithOpCode::Sub as u32 => ia.wrapping_sub(ib),
                x if x == ArithOpCode::Mul as u32 => ia.wrapping_mul(ib),
                x if x == ArithOpCode::Div as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia.wrapping_div(ib)
                    }
                }
                x if x == ArithOpCode::Mod as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia.wrapping_rem(ib)
                    }
                }
                _ => 0,
            };
            NumVal::Int(narrow_int(raw, bits) as i128)
        }
        x if x == ArithHintCode::Bigint as u32 => {
            // i64 / u64 — i128 carries them losslessly; signedness comes from the
            // semantic_kind (CARDINAL vs INTEGER). For the canonical vectors
            // we operate on the raw i128 with width-appropriate wrap.
            let ia = a.to_i128();
            let ib = b.to_i128();
            let raw = match op {
                x if x == ArithOpCode::Add as u32 => ia.wrapping_add(ib),
                x if x == ArithOpCode::Sub as u32 => ia.wrapping_sub(ib),
                x if x == ArithOpCode::Mul as u32 => ia.wrapping_mul(ib),
                x if x == ArithOpCode::Div as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia / ib
                    }
                }
                x if x == ArithOpCode::Mod as u32 => {
                    if ib == 0 {
                        0
                    } else {
                        ia % ib
                    }
                }
                _ => 0,
            };
            // No further narrowing — the JS BigInt is unbounded; our i128 covers
            // up to 128 bits which is enough for the i64/u64 contract.
            NumVal::Int(raw)
        }
        x if x == ArithHintCode::TableLookupViaFp32 as u32
            || x == ArithHintCode::DequantFp32ThenNative as u32
            || x == ArithHintCode::SoftwareFpViaFp32 as u32 =>
        {
            let fa = a.to_f64();
            let fb = b.to_f64();
            // Math.fround equivalent: round-trip through f32 to drop the bits
            // formats narrower than fp64 don't have.
            let round = |v: f64| -> f64 { (v as f32) as f64 };
            NumVal::Float(match op {
                x if x == ArithOpCode::Add as u32 => round(fa + fb),
                x if x == ArithOpCode::Sub as u32 => round(fa - fb),
                x if x == ArithOpCode::Mul as u32 => round(fa * fb),
                x if x == ArithOpCode::Div as u32 => round(fa / fb),
                x if x == ArithOpCode::Mod as u32 => round(fa - (fa / fb).floor() * fb),
                _ => 0.0,
            })
        }
        x if x == ArithHintCode::LogaddexpLogsubexp as u32 => {
            let la = a.to_f64();
            let lb = b.to_f64();
            NumVal::Float(match op {
                x if x == ArithOpCode::Add as u32 => {
                    let m = la.max(lb);
                    m + ((-(la - lb).abs()).exp()).ln_1p()
                }
                x if x == ArithOpCode::Sub as u32 => {
                    if lb >= la {
                        f64::NEG_INFINITY
                    } else {
                        la + ((-((lb - la).exp())).ln_1p())
                    }
                }
                x if x == ArithOpCode::Mul as u32 => la + lb,
                x if x == ArithOpCode::Div as u32 => la - lb,
                _ => 0.0,
            })
        }
        x if x == ArithHintCode::XorPopcount as u32 => {
            let ia = a.to_i128() as i32;
            let ib = b.to_i128() as i32;
            NumVal::Int(match op {
                x if x == ArithOpCode::Add as u32 => ((ia ^ ib) & 1) as i128,
                x if x == ArithOpCode::Sub as u32 => ((ia ^ ib) & 1) as i128,
                x if x == ArithOpCode::Mul as u32 => (ia & ib & 1) as i128,
                _ => 0,
            })
        }
        _ => panic!(
            "apply_arith: arithmetic-hint code {} not implemented",
            fmt.arith_hint_code
        ),
    }
}

fn narrow_int(v: i32, bits: u32) -> i32 {
    if bits >= 32 {
        return v;
    }
    let mask = (1i32 << bits) - 1;
    let sign_bit = 1i32 << (bits - 1);
    let u = v & mask;
    if u & sign_bit != 0 {
        u | !mask
    } else {
        u
    }
}

// ---------------------------------------------------------------------------
// FormatTable — handle assignment + per-(format, op) cached handlers.
// Pass 1: the first call for (format, op) compiles a specialized closure;
// subsequent calls hit the cache and skip the dispatcher's match-on-hint.
// ---------------------------------------------------------------------------

// Specialized handler: takes two NumVals, returns a NumVal. Rc<dyn Fn>
// is the Rust equivalent of the TS `new Function`-returned closure —
// shared so multiple borrowers can hold a reference to the same compiled
// handler without fighting the borrow checker.
pub type ArithHandler = Rc<dyn Fn(NumVal, NumVal) -> NumVal>;

pub struct FormatTable {
    by_handle: Vec<FormatRecipe>,
    by_nodeid: HashMap<NodeID, u32>,
    // handler cache: indexed by (handle, op) packed into a u64.
    handlers: HashMap<u64, ArithHandler>,
}

impl Default for FormatTable {
    fn default() -> Self {
        Self::new()
    }
}

impl FormatTable {
    pub fn new() -> Self {
        Self {
            by_handle: Vec::new(),
            by_nodeid: HashMap::new(),
            handlers: HashMap::new(),
        }
    }

    pub fn register(&mut self, fmt: &FormatRecipe) -> u32 {
        if let Some(&h) = self.by_nodeid.get(&fmt.node_id) {
            return h;
        }
        let h = self.by_handle.len() as u32;
        self.by_nodeid.insert(fmt.node_id, h);
        self.by_handle.push(fmt.clone());
        h
    }

    pub fn register_all(&mut self, lib: &FormatLibrary) {
        for r in &lib.recipes {
            self.register(r);
        }
    }

    // handler — Pass 1. Lazily compile a closure for (handle, op) and cache.
    // Returns a cloneable Rc; the clone is one refcount bump, no
    // recompilation. Subsequent calls hit the HashMap and clone the Rc.
    pub fn handler(&mut self, h: u32, op: u32) -> ArithHandler {
        let key = ((h as u64) << 32) | (op as u64);
        if !self.handlers.contains_key(&key) {
            let fmt = self.by_handle[h as usize].clone();
            let handler = compile_handler(&fmt, op);
            self.handlers.insert(key, handler);
        }
        self.handlers.get(&key).unwrap().clone()
    }

    // apply — Pass 1 hot-path entry. Same surface as apply_arith but routes
    // through the cached handler.
    #[cfg(test)]
    pub fn apply(&mut self, fmt: &FormatRecipe, op: u32, a: NumVal, b: NumVal) -> NumVal {
        let h = self.register(fmt);
        self.handler(h, op)(a, b)
    }
}

// compile_handler — emit a per-(format, op) specialized closure. Each branch
// captures only the constants relevant to that combination (e.g. the bit
// width for narrow ints); the resulting closure has no further dispatch.
fn compile_handler(fmt: &FormatRecipe, op: u32) -> ArithHandler {
    let opc = op;
    match fmt.arith_hint_code {
        x if x == ArithHintCode::NativeFp as u32 => {
            if opc == ArithOpCode::Add as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() + b.to_f64()))
            } else if opc == ArithOpCode::Sub as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() - b.to_f64()))
            } else if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() * b.to_f64()))
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() / b.to_f64()))
            } else {
                Rc::new(|a, b| {
                    let fa = a.to_f64();
                    let fb = b.to_f64();
                    NumVal::Float(fa - (fa / fb).floor() * fb)
                })
            }
        }
        x if x == ArithHintCode::NativeInt as u32 => {
            if opc == ArithOpCode::Add as u32 {
                Rc::new(|a, b| {
                    NumVal::Int((a.to_i128() as i32).wrapping_add(b.to_i128() as i32) as i128)
                })
            } else if opc == ArithOpCode::Sub as u32 {
                Rc::new(|a, b| {
                    NumVal::Int((a.to_i128() as i32).wrapping_sub(b.to_i128() as i32) as i128)
                })
            } else if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| {
                    NumVal::Int((a.to_i128() as i32).wrapping_mul(b.to_i128() as i32) as i128)
                })
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(|a, b| {
                    let ib = b.to_i128() as i32;
                    NumVal::Int(if ib == 0 {
                        0
                    } else {
                        (a.to_i128() as i32).wrapping_div(ib) as i128
                    })
                })
            } else {
                Rc::new(|a, b| {
                    let ib = b.to_i128() as i32;
                    NumVal::Int(if ib == 0 {
                        0
                    } else {
                        (a.to_i128() as i32).wrapping_rem(ib) as i128
                    })
                })
            }
        }
        x if x == ArithHintCode::NativeIntNarrow as u32 => {
            let bits = fmt.bits;
            if opc == ArithOpCode::Add as u32 {
                Rc::new(move |a, b| {
                    let raw = (a.to_i128() as i32).wrapping_add(b.to_i128() as i32);
                    NumVal::Int(narrow_int(raw, bits) as i128)
                })
            } else if opc == ArithOpCode::Sub as u32 {
                Rc::new(move |a, b| {
                    let raw = (a.to_i128() as i32).wrapping_sub(b.to_i128() as i32);
                    NumVal::Int(narrow_int(raw, bits) as i128)
                })
            } else if opc == ArithOpCode::Mul as u32 {
                Rc::new(move |a, b| {
                    let raw = (a.to_i128() as i32).wrapping_mul(b.to_i128() as i32);
                    NumVal::Int(narrow_int(raw, bits) as i128)
                })
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(move |a, b| {
                    let ib = b.to_i128() as i32;
                    let raw = if ib == 0 {
                        0
                    } else {
                        (a.to_i128() as i32).wrapping_div(ib)
                    };
                    NumVal::Int(narrow_int(raw, bits) as i128)
                })
            } else {
                Rc::new(move |a, b| {
                    let ib = b.to_i128() as i32;
                    let raw = if ib == 0 {
                        0
                    } else {
                        (a.to_i128() as i32).wrapping_rem(ib)
                    };
                    NumVal::Int(narrow_int(raw, bits) as i128)
                })
            }
        }
        x if x == ArithHintCode::Bigint as u32 => {
            if opc == ArithOpCode::Add as u32 {
                Rc::new(|a, b| NumVal::Int(a.to_i128().wrapping_add(b.to_i128())))
            } else if opc == ArithOpCode::Sub as u32 {
                Rc::new(|a, b| NumVal::Int(a.to_i128().wrapping_sub(b.to_i128())))
            } else if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| NumVal::Int(a.to_i128().wrapping_mul(b.to_i128())))
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(|a, b| {
                    let ib = b.to_i128();
                    NumVal::Int(if ib == 0 { 0 } else { a.to_i128() / ib })
                })
            } else {
                Rc::new(|a, b| {
                    let ib = b.to_i128();
                    NumVal::Int(if ib == 0 { 0 } else { a.to_i128() % ib })
                })
            }
        }
        x if x == ArithHintCode::TableLookupViaFp32 as u32
            || x == ArithHintCode::DequantFp32ThenNative as u32
            || x == ArithHintCode::SoftwareFpViaFp32 as u32 =>
        {
            if opc == ArithOpCode::Add as u32 {
                Rc::new(|a, b| NumVal::Float(((a.to_f64() + b.to_f64()) as f32) as f64))
            } else if opc == ArithOpCode::Sub as u32 {
                Rc::new(|a, b| NumVal::Float(((a.to_f64() - b.to_f64()) as f32) as f64))
            } else if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| NumVal::Float(((a.to_f64() * b.to_f64()) as f32) as f64))
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(|a, b| NumVal::Float(((a.to_f64() / b.to_f64()) as f32) as f64))
            } else {
                Rc::new(|a, b| {
                    let fa = a.to_f64();
                    let fb = b.to_f64();
                    NumVal::Float(((fa - (fa / fb).floor() * fb) as f32) as f64)
                })
            }
        }
        x if x == ArithHintCode::LogaddexpLogsubexp as u32 => {
            if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() + b.to_f64()))
            } else if opc == ArithOpCode::Div as u32 {
                Rc::new(|a, b| NumVal::Float(a.to_f64() - b.to_f64()))
            } else if opc == ArithOpCode::Add as u32 {
                Rc::new(|a, b| {
                    let la = a.to_f64();
                    let lb = b.to_f64();
                    let m = la.max(lb);
                    NumVal::Float(m + ((-(la - lb).abs()).exp()).ln_1p())
                })
            } else {
                Rc::new(|a, b| {
                    let la = a.to_f64();
                    let lb = b.to_f64();
                    if lb >= la {
                        NumVal::Float(f64::NEG_INFINITY)
                    } else {
                        NumVal::Float(la + ((-((lb - la).exp())).ln_1p()))
                    }
                })
            }
        }
        x if x == ArithHintCode::XorPopcount as u32 => {
            if opc == ArithOpCode::Mul as u32 {
                Rc::new(|a, b| {
                    NumVal::Int(((a.to_i128() as i32) & (b.to_i128() as i32) & 1) as i128)
                })
            } else if opc == ArithOpCode::Add as u32 || opc == ArithOpCode::Sub as u32 {
                Rc::new(|a, b| {
                    NumVal::Int((((a.to_i128() as i32) ^ (b.to_i128() as i32)) & 1) as i128)
                })
            } else {
                Rc::new(|_a, _b| NumVal::Int(0))
            }
        }
        _ => panic!(
            "compile_handler: arithmetic-hint code {} not implemented",
            fmt.arith_hint_code
        ),
    }
}

// ---------------------------------------------------------------------------
// canonicalize — fold +0/-0 to +0 and NaN bit patterns to canonical NaN
// before the value gets interned. Required for the canonicalization
// vectors in the canonical JSON.
// ---------------------------------------------------------------------------

pub fn canonicalize_float(v: f64) -> f64 {
    if v.is_nan() {
        return f64::NAN; // Rust's canonical NaN bit pattern
    }
    if v == 0.0 {
        return 0.0; // strips the sign of -0
    }
    v
}

// canonicalize — float-shaped formats fold to canonical bit pattern;
// integer-shaped formats pass through.
pub fn canonicalize(fmt: &FormatRecipe, v: NumVal) -> NumVal {
    let hint = fmt.arith_hint_code;
    let is_floatish = hint == ArithHintCode::NativeFp as u32
        || hint == ArithHintCode::TableLookupViaFp32 as u32
        || hint == ArithHintCode::DequantFp32ThenNative as u32
        || hint == ArithHintCode::SoftwareFpViaFp32 as u32
        || hint == ArithHintCode::LogaddexpLogsubexp as u32;
    if !is_floatish {
        return v;
    }
    match v {
        NumVal::Float(f) => NumVal::Float(canonicalize_float(f)),
        NumVal::Int(i) => NumVal::Float(canonicalize_float(i as f64)),
    }
}

// ---------------------------------------------------------------------------
// intern_numeric — Tier-1 numeric leaf. Encodes (format, value) into a
// substrate composite under RBASIC_NUMERIC.
//
// Inline path: small integer formats (bits ≤ 16) with native-int hint can
// pack value into the lower 16 bits of `inst`, handle into the upper 16.
// General path: composite recipe with one value-child encoding the bits.
// Values that exceed `inst`'s u32 are routed through the string table —
// stored as their canonical decimal repr, retrieved by parsing back.
// ---------------------------------------------------------------------------

#[allow(dead_code)]
pub fn intern_numeric(
    k: &mut Kernel,
    table: &mut FormatTable,
    fmt: &FormatRecipe,
    raw: NumVal,
) -> NodeID {
    let handle = table.register(fmt);
    let canonical = canonicalize(fmt, raw);

    // Inline-fit small integer formats.
    if fmt.bits <= 16 && fmt.arith_hint_code == ArithHintCode::NativeInt as u32 {
        if let NumVal::Int(i) = canonical {
            if (-32768..=32767).contains(&i) {
                let value16 = (i & 0xffff) as u32;
                let inst = ((handle & 0xffff) << 16) | (value16 & 0xffff);
                return NodeID {
                    pkg: 1,
                    level: LEVEL_BASIC,
                    ty: RBASIC_NUMERIC,
                    inst,
                };
            }
        }
    }

    // General path: composite carrying the encoded value as one child.
    let value_child = encode_overflow_value(k, canonical);
    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_NUMERIC,
        inst: handle,
    };
    k.intern(category, vec![value_child])
}

// Route an oversized value (full-width f64, i64/u64) through the string
// table so the substrate can carry it without losing precision. The
// canonical string repr is what content-addressing keys off.
fn encode_overflow_value(k: &mut Kernel, v: NumVal) -> NodeID {
    match v {
        NumVal::Float(f) => {
            let s = if f.is_nan() {
                "NaN".to_string()
            } else {
                // Use bit pattern so identity is exact (e.g. ensures +0 collapses
                // to a single key after canonicalize_float).
                let bits = f.to_bits();
                format!("f64:{:016x}", bits)
            };
            k.intern_string(&s)
        }
        NumVal::Int(i) => {
            // Try inline i32 first; otherwise stringify.
            if (-(1i128 << 31)..(1i128 << 31)).contains(&i) {
                k.intern_trivial_int(i as i64)
            } else {
                let s = format!("int:{}", i);
                k.intern_string(&s)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// run_numeric_bench — the three canonical workloads. Each measured in three
// modes: native Rust (no dispatch), Pass 0 (recipe-driven dispatcher per op),
// Pass 1 (cached specialized handler per (format, op)).
// ---------------------------------------------------------------------------

pub fn run_numeric_bench() {
    let mut k = Kernel::new();
    let lib = build_format_library(&mut k);
    let mut table = FormatTable::new();
    table.register_all(&lib);

    println!(
        "{:<22} {:<12} {:<16} {:<16} {:<16} {:>10} {:>10}",
        "workload", "result", "native", "pass-0", "pass-1", "p0/native", "p1/native"
    );

    bench_fp64_sum(&lib, &mut table);
    bench_fp8_sum(&lib, &mut table);
    bench_bitnet_dot(&lib, &mut table);
}

const FP64_N: usize = 100_000;
const FP8_N: usize = 100_000;
const BITNET_N: usize = 100_000;
const FP64_REPS: u32 = 50;
const FP8_REPS: u32 = 50;
const BITNET_REPS: u32 = 50;

fn bench_fp64_sum(lib: &FormatLibrary, table: &mut FormatTable) {
    let fp64 = lib.get("fp64");
    let xs: Vec<f64> = (0..FP64_N).map(|i| (i as f64) * 0.001).collect();

    // Native
    let start = Instant::now();
    let mut native_acc = 0.0;
    for _ in 0..FP64_REPS {
        let mut acc = 0.0;
        for &x in &xs {
            acc = std::hint::black_box(acc + x);
        }
        native_acc = acc;
    }
    let native_dur = start.elapsed() / FP64_REPS;

    // Pass 0
    let start = Instant::now();
    let mut p0_acc = NumVal::Float(0.0);
    for _ in 0..FP64_REPS {
        let mut acc = NumVal::Float(0.0);
        for &x in &xs {
            acc = apply_arith(
                fp64,
                ArithOpCode::Add as u32,
                std::hint::black_box(acc),
                NumVal::Float(x),
            );
        }
        p0_acc = acc;
    }
    let p0_dur = start.elapsed() / FP64_REPS;

    // Pass 1 — pull the handler out of the per-rep critical section once.
    // This is the realistic Pass-1 picture: cache hit is paid once, then the
    // hot loop is just an indirect call through the Box<dyn Fn>.
    let h = table.register(fp64);
    let _ = table.handler(h, ArithOpCode::Add as u32); // warm
    let handler = table.handler(h, ArithOpCode::Add as u32);
    let start = Instant::now();
    let mut p1_acc = NumVal::Float(0.0);
    for _ in 0..FP64_REPS {
        let mut acc = NumVal::Float(0.0);
        for &x in &xs {
            acc = handler(std::hint::black_box(acc), NumVal::Float(x));
        }
        p1_acc = acc;
    }
    let p1_dur = start.elapsed() / FP64_REPS;

    print_row(
        "fp64 sum",
        native_acc,
        p0_acc.to_f64(),
        p1_acc.to_f64(),
        native_dur,
        p0_dur,
        p1_dur,
    );
}

fn bench_fp8_sum(lib: &FormatLibrary, table: &mut FormatTable) {
    let fp8 = lib.get("fp8-e4m3");
    let xs: Vec<f64> = (0..FP8_N).map(|i| ((i % 7) as f64) * 0.0625).collect();

    // Native — f32 narrowing per op (the table-lookup-via-fp32 contract).
    let start = Instant::now();
    let mut native_acc = 0.0_f64;
    for _ in 0..FP8_REPS {
        let mut acc = 0.0_f64;
        for &x in &xs {
            acc = std::hint::black_box(((acc + x) as f32) as f64);
        }
        native_acc = acc;
    }
    let native_dur = start.elapsed() / FP8_REPS;

    // Pass 0
    let start = Instant::now();
    let mut p0_acc = NumVal::Float(0.0);
    for _ in 0..FP8_REPS {
        let mut acc = NumVal::Float(0.0);
        for &x in &xs {
            acc = apply_arith(
                fp8,
                ArithOpCode::Add as u32,
                std::hint::black_box(acc),
                NumVal::Float(x),
            );
        }
        p0_acc = acc;
    }
    let p0_dur = start.elapsed() / FP8_REPS;

    // Pass 1 — pull the handler out of the per-rep critical section.
    let h = table.register(fp8);
    let _ = table.handler(h, ArithOpCode::Add as u32);
    let handler = table.handler(h, ArithOpCode::Add as u32);
    let start = Instant::now();
    let mut p1_acc = NumVal::Float(0.0);
    for _ in 0..FP8_REPS {
        let mut acc = NumVal::Float(0.0);
        for &x in &xs {
            acc = handler(std::hint::black_box(acc), NumVal::Float(x));
        }
        p1_acc = acc;
    }
    let p1_dur = start.elapsed() / FP8_REPS;

    print_row(
        "fp8 sum (fround)",
        native_acc,
        p0_acc.to_f64(),
        p1_acc.to_f64(),
        native_dur,
        p0_dur,
        p1_dur,
    );
}

fn bench_bitnet_dot(lib: &FormatLibrary, table: &mut FormatTable) {
    let bitnet = lib.get("bitnet-158");
    // Ternary vectors {-1, 0, 1}.
    let xs: Vec<i32> = (0..BITNET_N).map(|i| ((i % 3) as i32) - 1).collect();
    let ys: Vec<i32> = (0..BITNET_N).map(|i| (((i + 1) % 3) as i32) - 1).collect();

    // Native
    let start = Instant::now();
    let mut native_acc: i32 = 0;
    for _ in 0..BITNET_REPS {
        let mut acc: i32 = 0;
        for i in 0..xs.len() {
            let p = xs[i].wrapping_mul(ys[i]);
            acc = std::hint::black_box(acc.wrapping_add(p));
        }
        native_acc = acc;
    }
    let native_dur = start.elapsed() / BITNET_REPS;

    // Pass 0 — multiply each pair, accumulate. Two ops per element.
    let start = Instant::now();
    let mut p0_acc = NumVal::Int(0);
    for _ in 0..BITNET_REPS {
        let mut acc = NumVal::Int(0);
        for i in 0..xs.len() {
            let p = apply_arith(
                bitnet,
                ArithOpCode::Mul as u32,
                NumVal::Int(xs[i] as i128),
                NumVal::Int(ys[i] as i128),
            );
            acc = apply_arith(
                bitnet,
                ArithOpCode::Add as u32,
                std::hint::black_box(acc),
                p,
            );
        }
        p0_acc = acc;
    }
    let p0_dur = start.elapsed() / BITNET_REPS;

    // Pass 1 — both handlers pulled out of the loop once.
    let h = table.register(bitnet);
    let mul_h = table.handler(h, ArithOpCode::Mul as u32);
    let add_h = table.handler(h, ArithOpCode::Add as u32);
    let start = Instant::now();
    let mut p1_acc = NumVal::Int(0);
    for _ in 0..BITNET_REPS {
        let mut acc = NumVal::Int(0);
        for i in 0..xs.len() {
            let p = mul_h(NumVal::Int(xs[i] as i128), NumVal::Int(ys[i] as i128));
            acc = add_h(std::hint::black_box(acc), p);
        }
        p1_acc = acc;
    }
    let p1_dur = start.elapsed() / BITNET_REPS;

    print_row(
        "bitnet ternary dot",
        native_acc as f64,
        p0_acc.to_i128() as f64,
        p1_acc.to_i128() as f64,
        native_dur,
        p0_dur,
        p1_dur,
    );
}

fn print_row(
    name: &str,
    native: f64,
    p0: f64,
    p1: f64,
    native_dur: std::time::Duration,
    p0_dur: std::time::Duration,
    p1_dur: std::time::Duration,
) {
    let n_ns = native_dur.as_nanos().max(1) as f64;
    let p0_ratio = p0_dur.as_nanos() as f64 / n_ns;
    let p1_ratio = p1_dur.as_nanos() as f64 / n_ns;
    println!(
        "{:<22} {:<12.4} {:<16} {:<16} {:<16} {:>9.1}× {:>9.1}×",
        name,
        native,
        format!("{:?}", native_dur),
        format!("{:?}", p0_dur),
        format!("{:?}", p1_dur),
        p0_ratio,
        p1_ratio
    );
    // Touch the kernel-side results so the compiler can't elide them.
    let _ = (p0, p1);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn approx_eq(a: f64, b: f64, eps: f64) -> bool {
        if a.is_nan() && b.is_nan() {
            return true;
        }
        (a - b).abs() <= eps
    }

    fn parse_int_value(v: &serde_json::Value) -> i128 {
        if let Some(n) = v.as_i64() {
            return n as i128;
        }
        if let Some(s) = v.as_str() {
            // Strip JS BigInt "n" suffix if present.
            let trimmed = s.trim_end_matches('n');
            return trimmed.parse::<i128>().unwrap();
        }
        if let Some(n) = v.as_u64() {
            return n as i128;
        }
        if let Some(f) = v.as_f64() {
            return f as i128;
        }
        panic!("not an int-shaped value: {:?}", v);
    }

    fn parse_num_arg(v: &serde_json::Value, is_floatish: bool) -> NumVal {
        if is_floatish {
            if let Some(f) = v.as_f64() {
                return NumVal::Float(f);
            }
            if let Some(s) = v.as_str() {
                if s == "NaN" {
                    return NumVal::Float(f64::NAN);
                }
            }
            NumVal::Float(parse_int_value(v) as f64)
        } else {
            NumVal::Int(parse_int_value(v))
        }
    }

    fn is_floatish_hint(hint: u32) -> bool {
        hint == ArithHintCode::NativeFp as u32
            || hint == ArithHintCode::TableLookupViaFp32 as u32
            || hint == ArithHintCode::DequantFp32ThenNative as u32
            || hint == ArithHintCode::SoftwareFpViaFp32 as u32
            || hint == ArithHintCode::LogaddexpLogsubexp as u32
    }

    fn epsilon_for(fmt: &FormatRecipe) -> f64 {
        match fmt.bits {
            64 => 1e-12,
            32 => 1e-6,
            _ => 1e-2,
        }
    }

    #[test]
    fn canonical_vectors_pass() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let spec = load_canonical_spec();
        let mut table = FormatTable::new();
        table.register_all(&lib);

        for v in &spec.conformance_vectors.vectors {
            let fmt = lib.get(&v.format);
            let op = ArithOpCode::from_str(&v.op).unwrap_or_else(|| panic!("unknown op {}", v.op))
                as u32;
            let floatish = is_floatish_hint(fmt.arith_hint_code);
            let a = parse_num_arg(&v.a, floatish);
            let b = parse_num_arg(&v.b, floatish);

            // Pass 0
            let p0 = apply_arith(fmt, op, a, b);
            // Pass 1
            let p1 = table.apply(fmt, op, a, b);

            if floatish {
                let expected = v
                    .expected
                    .as_f64()
                    .unwrap_or_else(|| parse_int_value(&v.expected) as f64);
                let eps = epsilon_for(fmt);
                assert!(
                    approx_eq(p0.to_f64(), expected, eps),
                    "{}/{} pass-0: got {} expected {}",
                    v.format,
                    v.op,
                    p0.to_f64(),
                    expected
                );
                assert!(
                    approx_eq(p1.to_f64(), expected, eps),
                    "{}/{} pass-1: got {} expected {}",
                    v.format,
                    v.op,
                    p1.to_f64(),
                    expected
                );
            } else {
                let expected_i = parse_int_value(&v.expected);
                // For native-int (i32 path) we sign-extend the i32 result.
                let (g0, g1) = if fmt.arith_hint_code == ArithHintCode::NativeInt as u32 {
                    // The i32 wrap was captured in apply_arith but as_i128
                    // already holds the sign-extended i128.
                    (p0.to_i128(), p1.to_i128())
                } else {
                    (p0.to_i128(), p1.to_i128())
                };
                // i32 vectors: compare modulo i32 width.
                let (g0c, g1c, expc) = if fmt.arith_hint_code == ArithHintCode::NativeInt as u32
                    && fmt.bits == 32
                {
                    (
                        g0 as i32 as i128,
                        g1 as i32 as i128,
                        expected_i as i32 as i128,
                    )
                } else if fmt.arith_hint_code == ArithHintCode::NativeIntNarrow as u32 {
                    (
                        narrow_int(g0 as i32, fmt.bits) as i128,
                        narrow_int(g1 as i32, fmt.bits) as i128,
                        narrow_int(expected_i as i32, fmt.bits) as i128,
                    )
                } else if fmt.arith_hint_code == ArithHintCode::NativeInt as u32 && fmt.bits == 8 {
                    // i8 wrap
                    let wrap = |x: i128| (x as i32 as i8) as i128;
                    (wrap(g0), wrap(g1), wrap(expected_i))
                } else {
                    (g0, g1, expected_i)
                };
                assert_eq!(
                    g0c, expc,
                    "{}/{} pass-0: got {} expected {}",
                    v.format, v.op, g0c, expc
                );
                assert_eq!(
                    g1c, expc,
                    "{}/{} pass-1: got {} expected {}",
                    v.format, v.op, g1c, expc
                );
            }
        }
    }

    #[test]
    fn content_addressing_same_value_same_nodeid() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let mut table = FormatTable::new();
        table.register_all(&lib);
        let fp64 = lib.get("fp64").clone();

        let n1 = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(3.14159));
        let n2 = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(3.14159));
        assert_eq!(n1, n2, "same float should share NodeID");
    }

    #[test]
    fn canonicalize_negative_zero_to_positive() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let mut table = FormatTable::new();
        table.register_all(&lib);
        let fp64 = lib.get("fp64").clone();

        let pz = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(0.0));
        let nz = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(-0.0));
        assert_eq!(pz, nz, "+0 and -0 should share NodeID after canonicalize");
    }

    #[test]
    fn canonicalize_nan_to_canonical() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let mut table = FormatTable::new();
        table.register_all(&lib);
        let fp64 = lib.get("fp64").clone();

        // Two different NaN bit patterns
        let nan_a = f64::from_bits(0x7ff8_0000_0000_0001);
        let nan_b = f64::from_bits(0xfff8_0000_0000_0042);
        let na = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(nan_a));
        let nb = intern_numeric(&mut k, &mut table, &fp64, NumVal::Float(nan_b));
        assert_eq!(
            na, nb,
            "all NaN bit patterns should canonicalize to one NodeID"
        );
    }

    #[test]
    fn format_library_loads_all_canonical_formats() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let spec = load_canonical_spec();
        assert_eq!(lib.recipes.len(), spec.formats.len());
        for cf in &spec.formats {
            let r = lib.get(&cf.name);
            assert_eq!(r.bits, cf.bits, "format {} bits", cf.name);
            assert_eq!(&r.storage_hint, &cf.storage_hint);
            assert_eq!(&r.arithmetic_hint, &cf.arithmetic_hint);
        }
    }

    #[test]
    fn same_format_twice_same_nodeid() {
        // Interning the canonical library twice (across two builds) should
        // produce identical NodeIDs for the same format — content-addressing.
        let mut k = Kernel::new();
        let lib1 = build_format_library(&mut k);
        // Re-interning in the same kernel: identical content → same NodeID.
        let lib2 = build_format_library(&mut k);
        for (a, b) in lib1.recipes.iter().zip(lib2.recipes.iter()) {
            assert_eq!(
                a.node_id, b.node_id,
                "format {} should round-trip to same NodeID",
                a.name
            );
        }
    }

    #[test]
    fn pass1_handler_matches_pass0() {
        let mut k = Kernel::new();
        let lib = build_format_library(&mut k);
        let mut table = FormatTable::new();
        table.register_all(&lib);

        let fp64 = lib.get("fp64").clone();
        for (a, b) in [(1.0, 2.0), (3.14, 2.71), (-1.5, 0.5)] {
            let p0 = apply_arith(
                &fp64,
                ArithOpCode::Add as u32,
                NumVal::Float(a),
                NumVal::Float(b),
            );
            let p1 = table.apply(
                &fp64,
                ArithOpCode::Add as u32,
                NumVal::Float(a),
                NumVal::Float(b),
            );
            assert!(approx_eq(p0.to_f64(), p1.to_f64(), 1e-12));
        }
    }
}
