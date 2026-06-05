#![allow(dead_code)]
// quotient.rs — QUOTIENT RBasic arm: canonicalization under equivalence.
//
// A recipe whose category is RBasic.QUOTIENT has the shape:
//
//   QUOTIENT[carrier-recipe, equivalence-recipe]
//
// Where `equivalence-recipe` is itself a substrate cell describing the
// equivalence relation. When a *value* of the quotient type is interned
// (via `intern_quotient_value`), the equivalence-recipe's canonicalize
// step runs first; the canonical form is what hits the intern table.
// Two values equivalent under the relation therefore receive the SAME
// NodeID — content-addressing IS the quotient.
//
// This generalizes the canonicalization the format library already
// performs (NaN → quiet, ±0 → +0). The shape: equivalence-recipes are
// SUBSTRATE CELLS, not hardcoded kernel logic. Adding a new equivalence
// is a substrate write — the kernel reads the cell and dispatches the
// canonicalize_fn through the handler-name registry. The body grows;
// the kernel stays small.
//
// Decidability + cost policy:
//   - DECIDABLE_CHEAP  → EAGER canonicalize at intern, fast equality
//   - DECIDABLE_HEAVY  → LAZY canonicalize on equality query
//   - UNDECIDABLE      → LAZY (no eager option)
// Honest default: EAGER unless the equivalence declares heavy/undecidable.
//
// Cross-kernel: handler names match the TS, Python, and Go arms exactly
// (integer-from-nat-pair, rational-from-int-pair, commutative-pair,
// associative-left-fold). A Form program ingested into any kernel
// canonicalizes identically. New built-in equivalences are a cross-
// kernel coordination breath; Form-program-local ones need no
// coordination.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use crate::{Kernel, NodeID, LEVEL_BASIC, LEVEL_TRIVIAL, TRIV_INT, TRIV_STRING};

// ---------------------------------------------------------------------------
// RBasic slot — QUOTIENT lives at type=70 across every kernel. The
// equivalence-cell sibling category uses slot 71. These constants are
// part of the cross-kernel contract; do not renumber without updating
// every kernel and the canonical JSON.
// ---------------------------------------------------------------------------

pub const RBASIC_QUOTIENT: u32 = 70;
pub const RBASIC_EQUIVALENCE: u32 = 71;

// ---------------------------------------------------------------------------
// Decidability + canonicalization-strategy metadata
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum Decidability {
    /// Effective algorithm, cheap to run — canonicalize eagerly.
    DecidableCheap = 1,
    /// Effective algorithm, expensive (e.g. Knuth-Bendix) — canonicalize lazily.
    DecidableHeavy = 2,
    /// No effective algorithm (e.g. function-equality, group iso in general).
    Undecidable = 3,
}

impl Decidability {
    pub fn from_code(c: u32) -> Option<Self> {
        Some(match c {
            1 => Decidability::DecidableCheap,
            2 => Decidability::DecidableHeavy,
            3 => Decidability::Undecidable,
            _ => return None,
        })
    }
}

#[allow(dead_code)]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum CanonStrategy {
    Eager = 1,
    Lazy = 2,
}

impl CanonStrategy {
    pub fn from_code(c: u32) -> Option<Self> {
        Some(match c {
            1 => CanonStrategy::Eager,
            2 => CanonStrategy::Lazy,
            _ => return None,
        })
    }
}

// Honest defaults: eager unless the equivalence declares heavy or undecidable.
fn strategy_for(d: Decidability) -> CanonStrategy {
    match d {
        Decidability::DecidableCheap => CanonStrategy::Eager,
        _ => CanonStrategy::Lazy,
    }
}

// Per-equivalence canonicalization. Operates on a value's children
// (the raw representative) and returns the canonical-children tuple.
// Returning the same tuple-shape for any two equivalent inputs is the
// canonicalize_fn's job; the kernel handles the content-addressing.
//
// Signature mirrors TS/Python/Go: `(kernel, raw_children) -> canonical`.
// Send + Sync so the registry can live in a OnceLock<Mutex<...>>; in
// practice the handlers we register are pure functions, so the bounds
// are trivially satisfied.
pub type CanonicalizeFn = Box<dyn Fn(&mut Kernel, &[NodeID]) -> Vec<NodeID> + Send + Sync>;

// ---------------------------------------------------------------------------
// EquivalenceRelation — the substrate-resident relation descriptor.
// In a Form program this is itself a recipe whose category is
// RBASIC_EQUIVALENCE (handler_name resolves to a registered fn).
// We hold the Rust side here as a thin wrapper; the substrate-cell
// projection (a recipe carrying name + decidability + strategy +
// handler_name as children) is interned in parallel for cross-kernel
// agreement.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct EquivalenceRelation {
    /// Human-readable identifier ("integer-from-nat-pair").
    pub equivalence_name: String,
    /// Substrate cell projection — NodeID of the equivalence-recipe.
    pub node_id: NodeID,
    /// Decidability + algorithm-cost classification.
    pub decidability: u32,
    /// Computed strategy honoring decidability + honest-defaults policy.
    pub strategy: u32,
    /// Cheap-flag is informational; strategy already folded it in.
    pub is_decidable: bool,
    /// Handler name — string-handle into the kernel's registered table.
    pub handler_name: String,
}

// ---------------------------------------------------------------------------
// Handler registry — name → CanonicalizeFn.
//
// Process-global so cross-Kernel testing (the QuotientLibrary builds
// against any Kernel) sees the same handlers. The same shape lives in
// the TS module-level Map and the Python module-level dict.
//
// New equivalences arrive in two halves: a substrate write (the recipe,
// produced by `make_equivalence`) and a handler registration (the
// runtime, here). For purely-Form equivalences (canonicalize_fn
// expressed AS a Form recipe), the handler would be a "walk-this-recipe"
// stub — that path is follow-up work.
// ---------------------------------------------------------------------------

fn handler_registry() -> &'static Mutex<HashMap<String, CanonicalizeFn>> {
    static REGISTRY: OnceLock<Mutex<HashMap<String, CanonicalizeFn>>> = OnceLock::new();
    REGISTRY.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Register a canonicalize handler under a stable name. Idempotent —
/// re-registering the same name replaces the existing handler (matches
/// TS Map.set semantics).
pub fn register_handler<F>(name: &str, f: F)
where
    F: Fn(&mut Kernel, &[NodeID]) -> Vec<NodeID> + Send + Sync + 'static,
{
    let mut reg = handler_registry()
        .lock()
        .expect("handler registry poisoned");
    reg.insert(name.to_string(), Box::new(f));
}

/// True if a handler is registered under this name.
pub fn has_handler(name: &str) -> bool {
    let reg = handler_registry()
        .lock()
        .expect("handler registry poisoned");
    reg.contains_key(name)
}

/// Invoke a registered handler. Returns `None` if unregistered.
/// We can't safely hand out the `Box<dyn Fn>` because the Mutex guard
/// would have to live as long as the caller; instead, the registry
/// owns the closure and we call through with a borrowed Kernel.
pub fn invoke_handler(name: &str, k: &mut Kernel, raw: &[NodeID]) -> Option<Vec<NodeID>> {
    let reg = handler_registry()
        .lock()
        .expect("handler registry poisoned");
    let f = reg.get(name)?;
    Some(f(k, raw))
}

// ---------------------------------------------------------------------------
// Substrate-cell projection: the equivalence-recipe.
//
// Stored shape (children, all substrate-resident):
//   [ name-trivial, decidability-int, strategy-int, handler-name-trivial ]
//
// The category instance is the decidability code so the NodeID inst
// already encodes the major axis without a child lookup. Two recipes
// with identical children intern to the SAME NodeID — equivalences are
// content-addressed like everything else.
// ---------------------------------------------------------------------------

fn make_equivalence_cell(
    k: &mut Kernel,
    equivalence_name: &str,
    decidability: u32,
    strategy: u32,
    handler_name: &str,
) -> NodeID {
    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_EQUIVALENCE,
        inst: decidability,
    };
    let name_nid = k.intern_string(equivalence_name);
    let dec_nid = k.intern_trivial_int(decidability as i64);
    let strat_nid = k.intern_trivial_int(strategy as i64);
    let hname_nid = k.intern_string(handler_name);
    k.intern(category, vec![name_nid, dec_nid, strat_nid, hname_nid])
}

/// Register a new equivalence relation in the substrate. The handler
/// must already be registered under `handler_name` via
/// [`register_handler`]. Returns the [`EquivalenceRelation`] handle
/// (carrying the substrate cell NodeID).
pub fn make_equivalence(
    k: &mut Kernel,
    equivalence_name: &str,
    decidability: Decidability,
    handler_name: &str,
) -> EquivalenceRelation {
    if !has_handler(handler_name) {
        panic!("quotient: handler '{}' is not registered", handler_name);
    }
    let strategy = strategy_for(decidability);
    let node_id = make_equivalence_cell(
        k,
        equivalence_name,
        decidability as u32,
        strategy as u32,
        handler_name,
    );
    EquivalenceRelation {
        equivalence_name: equivalence_name.to_string(),
        node_id,
        decidability: decidability as u32,
        strategy: strategy as u32,
        is_decidable: decidability != Decidability::Undecidable,
        handler_name: handler_name.to_string(),
    }
}

// ---------------------------------------------------------------------------
// QUOTIENT recipe construction.
//
//   make_quotient_recipe(k, carrier, equivalence) — intern a
//   QUOTIENT[carrier, equivalence] recipe. The carrier is the underlying
//   recipe whose values get quotiented; the equivalence-recipe carries
//   canonicalization rules. Same (carrier, equivalence) pair always
//   interns to the same NodeID (content-addressing).
// ---------------------------------------------------------------------------

pub fn make_quotient_recipe(k: &mut Kernel, carrier: NodeID, equivalence: NodeID) -> NodeID {
    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_QUOTIENT,
        inst: 1, // recipe-form
    };
    k.intern(category, vec![carrier, equivalence])
}

/// Inspect a QUOTIENT recipe: extract (carrier, equivalence).
pub fn quotient_parts(k: &Kernel, quotient: NodeID) -> Result<(NodeID, NodeID), String> {
    if quotient.level != LEVEL_BASIC || quotient.ty != RBASIC_QUOTIENT {
        return Err(format!(
            "quotient_parts: @{}.{}.{}.{} is not a QUOTIENT recipe",
            quotient.pkg, quotient.level, quotient.ty, quotient.inst
        ));
    }
    let kids = k.children(quotient);
    if kids.len() != 2 {
        return Err(format!(
            "quotient_parts: malformed QUOTIENT recipe (children={})",
            kids.len()
        ));
    }
    Ok((kids[0], kids[1]))
}

/// Resolve the [`EquivalenceRelation`] handle from a substrate-cell
/// NodeID. The equivalence-cell's children carry [name, decidability,
/// strategy, handler-name]; we decode and look up the registered handler.
pub fn resolve_equivalence(k: &Kernel, equiv: NodeID) -> Option<EquivalenceRelation> {
    let kids = k.children(equiv);
    if kids.len() != 4 {
        return None;
    }
    let name = read_string_trivial(k, kids[0])?;
    let dec = read_int_trivial(kids[1])?;
    let strat = read_int_trivial(kids[2])?;
    let hname = read_string_trivial(k, kids[3])?;
    if !has_handler(&hname) {
        return None;
    }
    let dec_u = dec as u32;
    let strat_u = strat as u32;
    let dec_enum = Decidability::from_code(dec_u)?;
    Some(EquivalenceRelation {
        equivalence_name: name,
        node_id: equiv,
        decidability: dec_u,
        strategy: strat_u,
        is_decidable: dec_enum != Decidability::Undecidable,
        handler_name: hname,
    })
}

fn read_int_trivial(n: NodeID) -> Option<i64> {
    if n.level != LEVEL_TRIVIAL || n.ty != TRIV_INT {
        return None;
    }
    Some((n.inst as i32) as i64)
}

fn read_string_trivial(k: &Kernel, n: NodeID) -> Option<String> {
    if n.level != LEVEL_TRIVIAL || n.ty != TRIV_STRING {
        return None;
    }
    // Pull through the trivial_value path so we don't expose the strs
    // table directly; the clone is cheap relative to a canonicalize call.
    let v = k.trivial_value(n);
    match v {
        crate::Value::Str(s) => Some(s.to_string()),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Interning a value through a quotient.
//
//   intern_quotient_value(k, quotient_recipe, raw_children)
//
// `raw_children` are the carrier-shape children of the raw value (e.g.
// [int(3), int(1)] for an integer-from-nat-pair representative). The
// equivalence's canonicalize_fn reduces them to canonical-children; the
// kernel then interns a recipe whose category is the QUOTIENT cell and
// whose children are [quotient_recipe, ...canonical-children]. Two
// equivalent raw values therefore produce the SAME NodeID — that's the
// quotient.
//
// Strategy = EAGER: canonicalize NOW, then intern canonical form (inst=2).
// Strategy = LAZY:  intern raw form with a distinct inst=3 marker;
//                   `canonical_form` canonicalizes on demand and lands
//                   at the same inst=2 slot the eager path would have
//                   produced, so cross-strategy equality holds.
// ---------------------------------------------------------------------------

pub fn intern_quotient_value(
    k: &mut Kernel,
    quotient_recipe: NodeID,
    raw_children: &[NodeID],
) -> NodeID {
    let (_carrier, equiv_nid) =
        quotient_parts(k, quotient_recipe).expect("intern_quotient_value: bad quotient recipe");
    let eq = resolve_equivalence(k, equiv_nid)
        .expect("intern_quotient_value: cannot resolve equivalence");

    if eq.strategy == CanonStrategy::Eager as u32 {
        let canonical = invoke_handler(&eq.handler_name, k, raw_children)
            .expect("intern_quotient_value: handler vanished mid-call");
        let category = NodeID {
            pkg: 1,
            level: LEVEL_BASIC,
            ty: RBASIC_QUOTIENT,
            inst: 2, // canonical-value form
        };
        let mut children = Vec::with_capacity(canonical.len() + 1);
        children.push(quotient_recipe);
        children.extend(canonical);
        return k.intern(category, children);
    }

    // LAZY: intern the raw form with a distinct inst=3 marker so eager-
    // and lazy-shapes don't collide. The canonical form computed on
    // equality-query shares the inst=2 slot, so once forced both reach
    // the same NodeID.
    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_QUOTIENT,
        inst: 3, // lazy raw form
    };
    let mut children = Vec::with_capacity(raw_children.len() + 1);
    children.push(quotient_recipe);
    children.extend_from_slice(raw_children);
    k.intern(category, children)
}

/// Force-canonicalize a value (eager or lazy) and return its canonical
/// NodeID. Used by equality queries and by callers that want to merge
/// equivalent representatives explicitly.
pub fn canonical_form(k: &mut Kernel, value: NodeID) -> NodeID {
    if value.level != LEVEL_BASIC || value.ty != RBASIC_QUOTIENT {
        panic!(
            "canonical_form: @{}.{}.{}.{} is not a QUOTIENT value",
            value.pkg, value.level, value.ty, value.inst
        );
    }
    let kids = k.children(value);
    if kids.is_empty() {
        panic!("canonical_form: malformed quotient value (no children)");
    }
    if value.inst == 2 {
        // Already canonical.
        return value;
    }
    // Lazy (inst=3) — canonicalize and re-intern as inst=2 form.
    let quotient_recipe = kids[0];
    let rest: Vec<NodeID> = kids[1..].to_vec();
    let (_carrier, equiv_nid) =
        quotient_parts(k, quotient_recipe).expect("canonical_form: bad quotient recipe");
    let eq = resolve_equivalence(k, equiv_nid).expect("canonical_form: cannot resolve equivalence");
    let canonical = invoke_handler(&eq.handler_name, k, &rest)
        .expect("canonical_form: handler vanished mid-call");
    let category = NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RBASIC_QUOTIENT,
        inst: 2,
    };
    let mut children = Vec::with_capacity(canonical.len() + 1);
    children.push(quotient_recipe);
    children.extend(canonical);
    k.intern(category, children)
}

/// Equality under the quotient. Two values are equal iff their
/// canonical forms share a NodeID.
pub fn quotient_equal(k: &mut Kernel, a: NodeID, b: NodeID) -> bool {
    let ca = canonical_form(k, a);
    let cb = canonical_form(k, b);
    ca == cb
}

// ---------------------------------------------------------------------------
// Built-in equivalence relations.
//
// Each registers a handler under a stable name and constructs the
// substrate-resident equivalence-recipe. The names are part of the
// cross-kernel contract — TS / Python / Go register the same handler
// names so a Form program ingested into any kernel canonicalizes
// identically.
// ---------------------------------------------------------------------------

// ── EQUIV_INTEGER_FROM_NAT_PAIR ───────────────────────────────────────
// Integers as Z := (N × N) / ~ where (a,b) ~ (c,d) iff a+d = b+c.
// The canonical representative is (a-b, 0) — sign carried by the
// difference.
fn handler_integer_from_nat_pair(k: &mut Kernel, raw: &[NodeID]) -> Vec<NodeID> {
    if raw.len() != 2 {
        panic!(
            "integer-from-nat-pair: expected 2 children, got {}",
            raw.len()
        );
    }
    let av = read_int_trivial(raw[0]).expect("integer-from-nat-pair: child 0 must be int trivial");
    let bv = read_int_trivial(raw[1]).expect("integer-from-nat-pair: child 1 must be int trivial");
    if av < 0 || bv < 0 {
        panic!("integer-from-nat-pair: natural-number pair must be non-negative");
    }
    let diff = av - bv;
    vec![k.intern_trivial_int(diff), k.intern_trivial_int(0)]
}

// ── EQUIV_RATIONAL_FROM_INT_PAIR ──────────────────────────────────────
// Rationals as Q := (Z × Z*) / ~ where (p,q) ~ (r,s) iff p*s = q*r.
// Canonical form: (p/gcd, q/gcd) with sign normalized into numerator.
fn gcd(a: i64, b: i64) -> i64 {
    let mut a = a.unsigned_abs() as i64;
    let mut b = b.unsigned_abs() as i64;
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    if a == 0 {
        1
    } else {
        a
    }
}

fn handler_rational_from_int_pair(k: &mut Kernel, raw: &[NodeID]) -> Vec<NodeID> {
    if raw.len() != 2 {
        panic!(
            "rational-from-int-pair: expected 2 children, got {}",
            raw.len()
        );
    }
    let mut p =
        read_int_trivial(raw[0]).expect("rational-from-int-pair: child 0 must be int trivial");
    let mut q =
        read_int_trivial(raw[1]).expect("rational-from-int-pair: child 1 must be int trivial");
    if q == 0 {
        panic!("rational-from-int-pair: zero denominator");
    }
    if q < 0 {
        p = -p;
        q = -q;
    }
    let g = gcd(p, q);
    vec![k.intern_trivial_int(p / g), k.intern_trivial_int(q / g)]
}

// ── EQUIV_COMMUTATIVE_PAIR ────────────────────────────────────────────
// (a, b) ~ (b, a). Canonicalize by sorting on the NodeID's packed key.
fn node_order_key(n: NodeID) -> (u32, u32, u32, u32) {
    (n.pkg, n.level, n.ty, n.inst)
}

fn handler_commutative_pair(_k: &mut Kernel, raw: &[NodeID]) -> Vec<NodeID> {
    if raw.len() != 2 {
        panic!("commutative-pair: expected 2 children, got {}", raw.len());
    }
    let a = raw[0];
    let b = raw[1];
    if node_order_key(a) <= node_order_key(b) {
        vec![a, b]
    } else {
        vec![b, a]
    }
}

// ── EQUIV_ASSOCIATIVE_LEFT_FOLD ───────────────────────────────────────
// No-op flattening at the children-tuple layer for this proof-of-shape.
// Real left-fold canonicalization needs recipe-tree access; deferred to
// the symmetry-aware arm. We still return the children unchanged so
// structurally-equal inputs share a NodeID — the minimum the
// equivalence promises at this layer.
fn handler_associative_left_fold(_k: &mut Kernel, raw: &[NodeID]) -> Vec<NodeID> {
    raw.to_vec()
}

// ---------------------------------------------------------------------------
// Bootstrap registration — runs once per process; returns the library
// of built-in EquivalenceRelations. Form code can register more via the
// handler-registry + make_equivalence path.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct QuotientLibrary {
    pub equiv_integer_from_nat_pair: EquivalenceRelation,
    pub equiv_rational_from_int_pair: EquivalenceRelation,
    pub equiv_commutative_pair: EquivalenceRelation,
    pub equiv_associative_left_fold: EquivalenceRelation,
}

fn bootstrap_handlers() {
    static ONCE: OnceLock<()> = OnceLock::new();
    ONCE.get_or_init(|| {
        register_handler("integer-from-nat-pair", handler_integer_from_nat_pair);
        register_handler("rational-from-int-pair", handler_rational_from_int_pair);
        register_handler("commutative-pair", handler_commutative_pair);
        register_handler("associative-left-fold", handler_associative_left_fold);
    });
}

pub fn build_quotient_library(k: &mut Kernel) -> QuotientLibrary {
    bootstrap_handlers();
    QuotientLibrary {
        equiv_integer_from_nat_pair: make_equivalence(
            k,
            "integer-from-nat-pair",
            Decidability::DecidableCheap,
            "integer-from-nat-pair",
        ),
        equiv_rational_from_int_pair: make_equivalence(
            k,
            "rational-from-int-pair",
            Decidability::DecidableCheap,
            "rational-from-int-pair",
        ),
        equiv_commutative_pair: make_equivalence(
            k,
            "commutative-pair",
            Decidability::DecidableCheap,
            "commutative-pair",
        ),
        equiv_associative_left_fold: make_equivalence(
            k,
            "associative-left-fold",
            Decidability::DecidableCheap,
            "associative-left-fold",
        ),
    }
}

// ---------------------------------------------------------------------------
// Tests — mirror the TS quotient.test.ts assertions one-for-one.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Kernel;

    // Helper: a placeholder list-recipe to stand in as the carrier. The
    // carrier's content doesn't drive canonicalization in any of the
    // built-in equivalences; it's a structural placeholder.
    fn placeholder_carrier(k: &mut Kernel) -> NodeID {
        // RB_LIST = 34 in main.rs — use the constant indirectly to avoid
        // re-exporting it. Any well-formed cell will do; we just want a
        // distinct NodeID for the carrier slot.
        let category = NodeID {
            pkg: 1,
            level: LEVEL_BASIC,
            ty: 34, // RB_LIST
            inst: 0,
        };
        k.intern(category, vec![])
    }

    #[test]
    fn rbasic_quotient_is_slot_70() {
        assert_eq!(RBASIC_QUOTIENT, 70);
    }

    #[test]
    fn integer_from_nat_pair_shares_nodeid() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lib.equiv_integer_from_nat_pair.node_id);

        let i3 = k.intern_trivial_int(3);
        let i1 = k.intern_trivial_int(1);
        let i5 = k.intern_trivial_int(5);
        let i3b = k.intern_trivial_int(3);
        let i9 = k.intern_trivial_int(9);
        let i7 = k.intern_trivial_int(7);

        let v31 = intern_quotient_value(&mut k, q, &[i3, i1]);
        let v53 = intern_quotient_value(&mut k, q, &[i5, i3b]);
        let v97 = intern_quotient_value(&mut k, q, &[i9, i7]);

        assert_eq!(v31, v53, "(3,1) ≡ (5,3) [both represent +2]");
        assert_eq!(v31, v97, "(3,1) ≡ (9,7) [transitivity]");

        // Negative integers
        let i1b = k.intern_trivial_int(1);
        let i3c = k.intern_trivial_int(3);
        let i2 = k.intern_trivial_int(2);
        let i4 = k.intern_trivial_int(4);
        let vn13 = intern_quotient_value(&mut k, q, &[i1b, i3c]);
        let vn24 = intern_quotient_value(&mut k, q, &[i2, i4]);
        assert_eq!(vn13, vn24, "(1,3) ≡ (2,4) [both represent -2]");

        assert_ne!(v31, vn13, "+2 ≠ -2 NodeID");

        // quotient_equal helper
        assert!(
            quotient_equal(&mut k, v31, v53),
            "quotient_equal: (3,1) == (5,3)"
        );
    }

    #[test]
    fn rational_from_int_pair_canonicalizes() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lib.equiv_rational_from_int_pair.node_id);

        let pos2 = k.intern_trivial_int(2);
        let pos4 = k.intern_trivial_int(4);
        let pos1 = k.intern_trivial_int(1);
        let pos2b = k.intern_trivial_int(2);
        let pos3 = k.intern_trivial_int(3);
        let pos6 = k.intern_trivial_int(6);
        let neg2 = k.intern_trivial_int(-2);
        let pos4b = k.intern_trivial_int(4);
        let pos2c = k.intern_trivial_int(2);
        let neg4 = k.intern_trivial_int(-4);

        let v24 = intern_quotient_value(&mut k, q, &[pos2, pos4]);
        let v12 = intern_quotient_value(&mut k, q, &[pos1, pos2b]);
        let v36 = intern_quotient_value(&mut k, q, &[pos3, pos6]);
        let v_neg2_4 = intern_quotient_value(&mut k, q, &[neg2, pos4b]);
        let v_2_neg4 = intern_quotient_value(&mut k, q, &[pos2c, neg4]);

        assert_eq!(v24, v12, "2/4 ≡ 1/2");
        assert_eq!(v36, v12, "3/6 ≡ 1/2 [reduce]");
        assert_eq!(v_neg2_4, v_2_neg4, "-2/4 ≡ 2/-4 [sign normalization]");
        assert_ne!(v12, v_neg2_4, "1/2 ≠ -1/2");
    }

    #[test]
    fn commutative_pair_swaps() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lib.equiv_commutative_pair.node_id);

        let a = k.intern_trivial_int(7);
        let b = k.intern_trivial_int(42);

        let vab = intern_quotient_value(&mut k, q, &[a, b]);
        let vba = intern_quotient_value(&mut k, q, &[b, a]);
        assert_eq!(vab, vba, "(7,42) ≡ (42,7)");

        let c = k.intern_trivial_int(99);
        let vac = intern_quotient_value(&mut k, q, &[a, c]);
        assert_ne!(vab, vac, "(7,42) ≠ (7,99)");
    }

    #[test]
    fn canonical_round_trip_shape() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lib.equiv_integer_from_nat_pair.node_id);

        let i7 = k.intern_trivial_int(7);
        let i2 = k.intern_trivial_int(2);
        let v = intern_quotient_value(&mut k, q, &[i7, i2]);

        // Eager strategy already canonicalized at intern; canonical_form
        // is a no-op for inst=2 values.
        let canon = canonical_form(&mut k, v);
        let kids = k.children(canon);
        assert_eq!(kids.len(), 3, "[quotient, canon-a, canon-b]");

        let ca = read_int_trivial(kids[1]).expect("canon-a is int");
        let cb = read_int_trivial(kids[2]).expect("canon-b is int");
        assert_eq!(ca, 5, "canon-a == 7-2");
        assert_eq!(cb, 0, "canon-b == 0");

        // Re-intern from canonical children lands at same NodeID
        let v2 = intern_quotient_value(&mut k, q, &[kids[1], kids[2]]);
        assert_eq!(v, v2, "canonical re-intern is idempotent");
    }

    #[test]
    fn equivalence_cells_are_content_addressed() {
        let mut k = Kernel::new();
        let a = build_quotient_library(&mut k);
        let b = build_quotient_library(&mut k);
        assert_eq!(
            a.equiv_integer_from_nat_pair.node_id, b.equiv_integer_from_nat_pair.node_id,
            "same kernel, same bootstrap → same NodeID"
        );

        let resolved = resolve_equivalence(&k, a.equiv_integer_from_nat_pair.node_id)
            .expect("resolve_equivalence: known cell");
        assert_eq!(resolved.equivalence_name, "integer-from-nat-pair");
        assert_eq!(resolved.decidability, Decidability::DecidableCheap as u32);
    }

    #[test]
    fn quotient_recipes_are_content_addressed() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q1 = make_quotient_recipe(&mut k, carrier, lib.equiv_integer_from_nat_pair.node_id);
        let q2 = make_quotient_recipe(&mut k, carrier, lib.equiv_integer_from_nat_pair.node_id);
        assert_eq!(q1, q2, "same (carrier, equiv) → same QUOTIENT NodeID");
    }

    #[test]
    fn decidability_policy_routes_strategy() {
        let mut k = Kernel::new();
        register_handler("test-heavy-r", |_k, raw| raw.to_vec());
        register_handler("test-undec-r", |_k, raw| raw.to_vec());

        let heavy = make_equivalence(
            &mut k,
            "test-heavy-r",
            Decidability::DecidableHeavy,
            "test-heavy-r",
        );
        let undec = make_equivalence(
            &mut k,
            "test-undec-r",
            Decidability::Undecidable,
            "test-undec-r",
        );

        assert_eq!(heavy.strategy, CanonStrategy::Lazy as u32);
        assert_eq!(undec.strategy, CanonStrategy::Lazy as u32);
        assert!(!undec.is_decidable);
    }

    #[test]
    fn lazy_strategy_merges_on_demand() {
        let mut k = Kernel::new();
        register_handler("lazy-int-r", |kk, raw| {
            // Same logic as the eager integer handler — registered as heavy.
            let av = match raw[0] {
                n if n.level == LEVEL_TRIVIAL && n.ty == TRIV_INT => (n.inst as i32) as i64,
                _ => panic!("bad child 0"),
            };
            let bv = match raw[1] {
                n if n.level == LEVEL_TRIVIAL && n.ty == TRIV_INT => (n.inst as i32) as i64,
                _ => panic!("bad child 1"),
            };
            vec![kk.intern_trivial_int(av - bv), kk.intern_trivial_int(0)]
        });
        let lazy_eq = make_equivalence(
            &mut k,
            "lazy-int-r",
            Decidability::DecidableHeavy,
            "lazy-int-r",
        );

        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lazy_eq.node_id);

        let i3 = k.intern_trivial_int(3);
        let i1 = k.intern_trivial_int(1);
        let i5 = k.intern_trivial_int(5);
        let i3b = k.intern_trivial_int(3);

        let v31 = intern_quotient_value(&mut k, q, &[i3, i1]);
        let v53 = intern_quotient_value(&mut k, q, &[i5, i3b]);

        // Lazy: raw NodeIDs differ (inst=3 entries with different children).
        assert_ne!(v31, v53, "lazy: raw NodeIDs differ pre-canonicalization");

        // canonical_form merges them
        let c31 = canonical_form(&mut k, v31);
        let c53 = canonical_form(&mut k, v53);
        assert_eq!(c31, c53, "lazy: canonical_form merges (3,1) and (5,3)");

        // quotient_equal works regardless of strategy
        assert!(quotient_equal(&mut k, v31, v53));
    }

    #[test]
    fn quotient_parts_inspection() {
        let mut k = Kernel::new();
        let lib = build_quotient_library(&mut k);
        let carrier = placeholder_carrier(&mut k);
        let q = make_quotient_recipe(&mut k, carrier, lib.equiv_commutative_pair.node_id);

        let (c, e) = quotient_parts(&k, q).expect("parts extract");
        assert_eq!(c, carrier);
        assert_eq!(e, lib.equiv_commutative_pair.node_id);
    }

    #[test]
    fn handler_registry_is_queryable() {
        let mut k = Kernel::new();
        let _ = build_quotient_library(&mut k);
        assert!(has_handler("integer-from-nat-pair"));
        assert!(!has_handler("does-not-exist-handler-name"));
    }
}
