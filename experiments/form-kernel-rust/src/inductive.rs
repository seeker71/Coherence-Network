#![allow(dead_code)]
// inductive.rs — INDUCTIVE / CONSTRUCTOR / CHOICE_MATCH RBasic arms.
//
// Algebraic datatypes as content-addressed substrate cells. Mirrors the
// TS reference (`experiments/form-kernel-ts/src/inductive.ts`) and the
// Python port (`api/app/services/substrate/inductive.py`). The shape:
//
//   INDUCTIVE
//     children:
//       type-name        : Triv.STRING        ; "Nat", "List", ...
//       type-params      : RB_LIST            ; parametric types (T, E, ...)
//       ctor0..ctorN     : RBASIC_CONSTRUCTOR ; constructors as type definitions
//
//   CONSTRUCTOR  (type definition, inside an INDUCTIVE)
//     children:
//       inductive-ref    : NodeID  ; self-name trivial during definition
//       ctor-name        : Triv.STRING
//       ctor-index       : Triv.INT
//       arg-type0..N     : NodeID  ; type-recipes (self-ref allowed)
//
//   CONSTRUCTOR  (value application, in code)
//     children:
//       inductive-ref    : NodeID  ; the inductive's NodeID (resolved)
//       ctor-name        : Triv.STRING
//       ctor-index       : Triv.INT
//       arg-recipe0..N   : NodeID  ; value-recipes
//
//   CHOICE_MATCH  (pattern match)
//     children:
//       scrutinee        : NodeID  ; value-recipe that walks to a ctor Value
//       arm0-name        : Triv.STRING
//       arm0-body        : NodeID
//       arm1-name        : Triv.STRING
//       arm1-body        : NodeID
//       ...
//
// Because the recipes are content-addressed, two inductives defined with
// identical name + identical params + identical constructor lists intern to
// the SAME substrate cell across kernels — that's the cross-kernel promise.
//
// Cross-kernel contract:
//   RBASIC_INDUCTIVE = 71
//   RBASIC_CONSTRUCTOR = 72
//   RBASIC_CHOICE_MATCH = 35
//   TRIV_CONSTRUCTOR_TAG = 15  (reserved; not yet exercised here)
//
// Built-in inductives installed by `install_builtin_inductives`:
//   Nat, Bool, Option, Result, List
// with constructors:
//   zero, succ, nil, cons, none, some, ok, err, true, false

use std::collections::HashMap;

use crate::{Kernel, NodeID, Value, LEVEL_BASIC, LEVEL_TRIVIAL, TRIV_INT, TRIV_STRING};

// ---------------------------------------------------------------------------
// Cross-kernel RBasic slot constants
// ---------------------------------------------------------------------------

pub const RBASIC_INDUCTIVE: u32 = 71;
pub const RBASIC_CONSTRUCTOR: u32 = 72;
pub const RBASIC_CHOICE_MATCH: u32 = 35;
pub const TRIV_CONSTRUCTOR_TAG: u32 = 15;

// RB_LIST matches the kernel's existing instance — used to build the
// type-parameters list child of an INDUCTIVE recipe. Locally re-declared
// here so this module doesn't depend on its numeric value being pub.
const RB_LIST_LOCAL: u32 = 34;

// ---------------------------------------------------------------------------
// Structural descriptions handed to the kernel at intern time
// ---------------------------------------------------------------------------

/// A constructor declaration on an inductive type.
#[derive(Clone, Debug)]
pub struct ConstructorDef {
    pub ctor_name: String,
    pub ctor_index: i64,
    /// `arg_types` are NodeIDs of type-recipes. Self-reference uses the
    /// inductive's type-name trivial as a sentinel (see `make_inductive`).
    pub arg_types: Vec<NodeID>,
}

impl ConstructorDef {
    pub fn new(name: &str, index: i64, args: Vec<NodeID>) -> Self {
        Self { ctor_name: name.to_string(), ctor_index: index, arg_types: args }
    }
}

/// In-memory handle for an inductive type. The recipe interned into the
/// substrate is the source of truth; this struct is the runtime view.
#[derive(Clone, Debug)]
pub struct InductiveType {
    pub type_name: String,
    pub type_params: Vec<NodeID>,
    pub constructors: Vec<ConstructorDef>,
    pub node_id: NodeID,
}

// ---------------------------------------------------------------------------
// Category-NodeID helpers
// ---------------------------------------------------------------------------

fn cat(arm_type: u32, inst: u32) -> NodeID {
    NodeID { pkg: 1, level: LEVEL_BASIC, ty: arm_type, inst }
}

fn cat_inductive() -> NodeID {
    cat(RBASIC_INDUCTIVE, 1)
}

fn cat_constructor() -> NodeID {
    cat(RBASIC_CONSTRUCTOR, 1)
}

fn cat_choice_match() -> NodeID {
    cat(RBASIC_CHOICE_MATCH, 1)
}

fn cat_list() -> NodeID {
    cat(RB_LIST_LOCAL, 0)
}

// ---------------------------------------------------------------------------
// Trivial-leaf readers
// ---------------------------------------------------------------------------

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
    match k.trivial_value(n) {
        Value::Str(s) => Some(s),
        _ => None,
    }
}

fn node_category_type(k: &Kernel, n: NodeID) -> Option<u32> {
    if n.level == LEVEL_TRIVIAL {
        return Some(n.ty);
    }
    // composite — the NodeID's own ty IS the category type for the
    // simple flat encoding used by the kernel.
    if n.level == LEVEL_BASIC {
        return Some(n.ty);
    }
    let _ = k;
    None
}

// ---------------------------------------------------------------------------
// make_inductive — intern an INDUCTIVE recipe
// ---------------------------------------------------------------------------

pub fn make_inductive(
    k: &mut Kernel,
    name: &str,
    params: &[NodeID],
    ctors: &[ConstructorDef],
) -> NodeID {
    let type_name = k.intern_string(name);
    let params_list = k.intern(cat_list(), params.to_vec());

    let mut ctor_defs: Vec<NodeID> = Vec::with_capacity(ctors.len());
    for c in ctors {
        let ctor_name_nid = k.intern_string(&c.ctor_name);
        let ctor_index_nid = k.intern_trivial_int(c.ctor_index);
        let mut children = Vec::with_capacity(3 + c.arg_types.len());
        children.push(type_name); // self-ref sentinel (type-name trivial)
        children.push(ctor_name_nid);
        children.push(ctor_index_nid);
        children.extend_from_slice(&c.arg_types);
        ctor_defs.push(k.intern(cat_constructor(), children));
    }

    let mut top = Vec::with_capacity(2 + ctor_defs.len());
    top.push(type_name);
    top.push(params_list);
    top.extend(ctor_defs);
    k.intern(cat_inductive(), top)
}

// ---------------------------------------------------------------------------
// make_constructor — apply a constructor to value-recipe arguments
// ---------------------------------------------------------------------------

pub fn make_constructor(
    k: &mut Kernel,
    inductive: NodeID,
    ctor_name: &str,
    args: &[NodeID],
) -> NodeID {
    let idx = constructor_index(k, inductive, ctor_name);
    if idx < 0 {
        panic!(
            "make_constructor: '{}' is not a constructor of inductive @{}.{}.{}.{}",
            ctor_name, inductive.pkg, inductive.level, inductive.ty, inductive.inst
        );
    }
    let ctor_name_nid = k.intern_string(ctor_name);
    let ctor_index_nid = k.intern_trivial_int(idx);
    let mut children = Vec::with_capacity(3 + args.len());
    children.push(inductive);
    children.push(ctor_name_nid);
    children.push(ctor_index_nid);
    children.extend_from_slice(args);
    k.intern(cat_constructor(), children)
}

pub fn constructor_index(k: &Kernel, inductive: NodeID, ctor_name: &str) -> i64 {
    if node_category_type(k, inductive) != Some(RBASIC_INDUCTIVE) {
        return -1;
    }
    let kids = k.children(inductive);
    // children: [type-name, params-list, ctor0, ctor1, ...]
    for ctor_nid in kids.iter().skip(2) {
        let ctor_kids = k.children(*ctor_nid);
        if ctor_kids.len() < 3 {
            continue;
        }
        let name_nid = ctor_kids[1];
        let idx_nid = ctor_kids[2];
        if let Some(n) = read_string_trivial(k, name_nid) {
            if n == ctor_name {
                if let Some(i) = read_int_trivial(idx_nid) {
                    return i;
                }
            }
        }
    }
    -1
}

pub fn constructor_names(k: &Kernel, inductive: NodeID) -> Vec<String> {
    if node_category_type(k, inductive) != Some(RBASIC_INDUCTIVE) {
        return Vec::new();
    }
    let kids = k.children(inductive);
    let mut out = Vec::new();
    for ctor_nid in kids.iter().skip(2) {
        let ctor_kids = k.children(*ctor_nid);
        if ctor_kids.len() < 2 {
            continue;
        }
        if let Some(n) = read_string_trivial(k, ctor_kids[1]) {
            out.push(n);
        }
    }
    out
}

pub fn is_total(k: &Kernel, inductive: NodeID, arm_names: &[&str]) -> bool {
    let declared = constructor_names(k, inductive);
    declared.iter().all(|n| arm_names.iter().any(|a| *a == n.as_str()))
}

// ---------------------------------------------------------------------------
// CtorValue — runtime tagged value
// ---------------------------------------------------------------------------

/// A constructor application result (the value-shape of an inductive).
#[derive(Clone, Debug)]
pub struct CtorValue {
    pub inductive: NodeID,
    pub ctor_name: String,
    pub ctor_index: i64,
    pub args: Vec<CtorOrNid>,
}

/// A walked value: either a constructor application or a raw NodeID
/// (trivial leaf or non-CONSTRUCTOR composite). The Rust kernel's
/// `Value` enum carries richer runtime semantics; this module only
/// needs the CONSTRUCTOR / CHOICE arms, so it stays narrow.
#[derive(Clone, Debug)]
pub enum CtorOrNid {
    Ctor(CtorValue),
    Nid(NodeID),
}

impl CtorOrNid {
    pub fn as_ctor(&self) -> Option<&CtorValue> {
        match self {
            CtorOrNid::Ctor(c) => Some(c),
            _ => None,
        }
    }

    pub fn as_nid(&self) -> Option<NodeID> {
        match self {
            CtorOrNid::Nid(n) => Some(*n),
            _ => None,
        }
    }
}

pub fn walk_value(k: &Kernel, node: NodeID) -> CtorOrNid {
    if node.level <= LEVEL_BASIC {
        // Trivial leaf or bare category — pass through as NodeID.
        // (For LEVEL_BASIC, only the bare-category-with-zero-children
        // form hits this; constructor recipes are LEVEL_BASIC too but
        // we dispatch on category type below.)
        if node.level == LEVEL_BASIC && node.ty == RBASIC_CONSTRUCTOR {
            return CtorOrNid::Ctor(walk_constructor(k, node));
        }
        return CtorOrNid::Nid(node);
    }
    CtorOrNid::Nid(node)
}

pub fn walk_constructor(k: &Kernel, node: NodeID) -> CtorValue {
    let kids = k.children(node);
    if kids.len() < 3 {
        panic!(
            "constructor: need 3+ children (inductive-ref, name, index), got {}",
            kids.len()
        );
    }
    let inductive = kids[0];
    let name_nid = kids[1];
    let idx_nid = kids[2];
    let ctor_name = read_string_trivial(k, name_nid)
        .expect("constructor: name must be a string trivial");
    let ctor_index = read_int_trivial(idx_nid)
        .expect("constructor: index must be an int trivial");
    let args: Vec<CtorOrNid> = kids[3..].iter().map(|c| walk_value(k, *c)).collect();
    CtorValue { inductive, ctor_name, ctor_index, args }
}

// ---------------------------------------------------------------------------
// CHOICE_MATCH recipe
// ---------------------------------------------------------------------------

pub fn make_choice(
    k: &mut Kernel,
    scrutinee: NodeID,
    arms: &[(&str, NodeID)],
) -> NodeID {
    let mut children: Vec<NodeID> = Vec::with_capacity(1 + 2 * arms.len());
    children.push(scrutinee);
    for (name, body) in arms {
        children.push(k.intern_string(name));
        children.push(*body);
    }
    k.intern(cat_choice_match(), children)
}

pub fn walk_choice(k: &Kernel, node: NodeID) -> CtorOrNid {
    let kids = k.children(node);
    if kids.is_empty() {
        panic!("choice: need scrutinee");
    }
    if (kids.len() - 1) % 2 != 0 {
        panic!("choice: arms must be (name, body) pairs");
    }
    let scrutinee = walk_value(k, kids[0]);
    let ctor = match scrutinee {
        CtorOrNid::Ctor(c) => c,
        _ => panic!("choice: scrutinee must be a ctor value"),
    };

    let mut arm_names: Vec<String> = Vec::new();
    let mut arm_bodies: Vec<NodeID> = Vec::new();
    let mut i = 1;
    while i < kids.len() {
        let name_nid = kids[i];
        let n = read_string_trivial(k, name_nid)
            .expect("choice: arm name must be a string trivial");
        arm_names.push(n);
        arm_bodies.push(kids[i + 1]);
        i += 2;
    }

    // Totality check — read the scrutinee's inductive.
    let declared = constructor_names(k, ctor.inductive);
    if !declared.is_empty() {
        let missing: Vec<&String> = declared
            .iter()
            .filter(|n| !arm_names.iter().any(|a| a == *n))
            .collect();
        if !missing.is_empty() {
            let label = if missing.len() == 1 { "constructor" } else { "constructors" };
            let names: Vec<String> = missing.iter().map(|s| (*s).clone()).collect();
            panic!(
                "choice: non-total — missing {}: {}",
                label,
                names.join(", ")
            );
        }
    }

    // Dispatch on the scrutinee's constructor name.
    for (name, body) in arm_names.iter().zip(arm_bodies.iter()) {
        if *name == ctor.ctor_name {
            return walk_value(k, *body);
        }
    }
    panic!("choice: no arm matches constructor '{}'", ctor.ctor_name);
}

// ---------------------------------------------------------------------------
// Imperative pattern match — Rust-side entry point for tests + kernel-internal
// helpers
// ---------------------------------------------------------------------------

/// A pattern-match arm: ctor-name + handler closure receiving the
/// constructor's argument values, returning an arbitrary Rust value.
pub type ArmHandler<R> = Box<dyn Fn(&[CtorOrNid]) -> R>;

pub fn match_value<R>(
    k: &Kernel,
    value: &CtorOrNid,
    arms: &HashMap<String, ArmHandler<R>>,
) -> R {
    let ctor = match value {
        CtorOrNid::Ctor(c) => c,
        _ => panic!("match_value: expected ctor value"),
    };
    let arm_names: Vec<&str> = arms.keys().map(|s| s.as_str()).collect();
    let declared = constructor_names(k, ctor.inductive);
    let missing: Vec<&String> = declared
        .iter()
        .filter(|n| !arm_names.iter().any(|a| *a == n.as_str()))
        .collect();
    if !missing.is_empty() {
        let names: Vec<String> = missing.iter().map(|s| (*s).clone()).collect();
        panic!("match_value: non-total — missing: {}", names.join(", "));
    }
    if let Some(handler) = arms.get(&ctor.ctor_name) {
        return handler(&ctor.args);
    }
    panic!("match_value: no arm matched '{}'", ctor.ctor_name);
}

// ---------------------------------------------------------------------------
// Built-in inductives — the standard library every body has
// ---------------------------------------------------------------------------

/// Install the standard library of inductives. Idempotent — same NodeIDs
/// across calls because the substrate is content-addressed.
pub fn install_builtin_inductives(k: &mut Kernel) -> HashMap<String, InductiveType> {
    let t_nid = k.intern_string("T");
    let e_nid = k.intern_string("E");

    // Nat ::= zero | succ Nat
    let nat_self = k.intern_string("Nat");
    let nat_ctors = vec![
        ConstructorDef::new("zero", 0, vec![]),
        ConstructorDef::new("succ", 1, vec![nat_self]),
    ];
    let nat_nid = make_inductive(k, "Nat", &[], &nat_ctors);

    // Bool ::= false | true
    let bool_ctors = vec![
        ConstructorDef::new("false", 0, vec![]),
        ConstructorDef::new("true", 1, vec![]),
    ];
    let bool_nid = make_inductive(k, "Bool", &[], &bool_ctors);

    // Option[T] ::= none | some T
    let option_ctors = vec![
        ConstructorDef::new("none", 0, vec![]),
        ConstructorDef::new("some", 1, vec![t_nid]),
    ];
    let option_nid = make_inductive(k, "Option", &[t_nid], &option_ctors);

    // Result[T, E] ::= ok T | err E
    let result_ctors = vec![
        ConstructorDef::new("ok", 0, vec![t_nid]),
        ConstructorDef::new("err", 1, vec![e_nid]),
    ];
    let result_nid = make_inductive(k, "Result", &[t_nid, e_nid], &result_ctors);

    // List[T] ::= nil | cons T (List T)
    let list_self = k.intern_string("List");
    let list_ctors = vec![
        ConstructorDef::new("nil", 0, vec![]),
        ConstructorDef::new("cons", 1, vec![t_nid, list_self]),
    ];
    let list_nid = make_inductive(k, "List", &[t_nid], &list_ctors);

    let mut out: HashMap<String, InductiveType> = HashMap::new();
    out.insert(
        "Nat".to_string(),
        InductiveType {
            type_name: "Nat".to_string(),
            type_params: vec![],
            constructors: nat_ctors,
            node_id: nat_nid,
        },
    );
    out.insert(
        "Bool".to_string(),
        InductiveType {
            type_name: "Bool".to_string(),
            type_params: vec![],
            constructors: bool_ctors,
            node_id: bool_nid,
        },
    );
    out.insert(
        "Option".to_string(),
        InductiveType {
            type_name: "Option".to_string(),
            type_params: vec![t_nid],
            constructors: option_ctors,
            node_id: option_nid,
        },
    );
    out.insert(
        "Result".to_string(),
        InductiveType {
            type_name: "Result".to_string(),
            type_params: vec![t_nid, e_nid],
            constructors: result_ctors,
            node_id: result_nid,
        },
    );
    out.insert(
        "List".to_string(),
        InductiveType {
            type_name: "List".to_string(),
            type_params: vec![t_nid],
            constructors: list_ctors,
            node_id: list_nid,
        },
    );
    out
}

// ---------------------------------------------------------------------------
// Convenience builders — common value-recipes
// ---------------------------------------------------------------------------

pub fn nat_zero(k: &mut Kernel, inductives: &HashMap<String, InductiveType>) -> NodeID {
    let nat = inductives.get("Nat").expect("nat_zero: Nat not installed").node_id;
    make_constructor(k, nat, "zero", &[])
}

pub fn nat_succ(
    k: &mut Kernel,
    inductives: &HashMap<String, InductiveType>,
    prev: NodeID,
) -> NodeID {
    let nat = inductives.get("Nat").expect("nat_succ: Nat not installed").node_id;
    make_constructor(k, nat, "succ", &[prev])
}

pub fn nat_of(k: &mut Kernel, inductives: &HashMap<String, InductiveType>, n: u64) -> NodeID {
    let mut out = nat_zero(k, inductives);
    for _ in 0..n {
        out = nat_succ(k, inductives, out);
    }
    out
}

pub fn list_nil(k: &mut Kernel, inductives: &HashMap<String, InductiveType>) -> NodeID {
    let list = inductives.get("List").expect("list_nil: List not installed").node_id;
    make_constructor(k, list, "nil", &[])
}

pub fn list_cons(
    k: &mut Kernel,
    inductives: &HashMap<String, InductiveType>,
    head: NodeID,
    tail: NodeID,
) -> NodeID {
    let list = inductives.get("List").expect("list_cons: List not installed").node_id;
    make_constructor(k, list, "cons", &[head, tail])
}

// ---------------------------------------------------------------------------
// Decoders — CtorValue → primitive
// ---------------------------------------------------------------------------

pub fn nat_to_int(v: &CtorOrNid) -> i64 {
    let mut n: i64 = 0;
    let mut cur = v.clone();
    loop {
        let c = match &cur {
            CtorOrNid::Ctor(c) => c.clone(),
            _ => panic!("nat_to_int: not a Nat"),
        };
        if c.ctor_name == "succ" {
            n += 1;
            if c.args.is_empty() {
                panic!("nat_to_int: succ with no args");
            }
            cur = c.args[0].clone();
            continue;
        }
        if c.ctor_name == "zero" {
            return n;
        }
        panic!("nat_to_int: unexpected ctor '{}'", c.ctor_name);
    }
}

pub fn list_length(v: &CtorOrNid) -> i64 {
    let mut n: i64 = 0;
    let mut cur = v.clone();
    loop {
        let c = match &cur {
            CtorOrNid::Ctor(c) => c.clone(),
            _ => panic!("list_length: not a List"),
        };
        if c.ctor_name == "cons" {
            n += 1;
            if c.args.len() < 2 {
                panic!("list_length: cons with insufficient args");
            }
            cur = c.args[1].clone();
            continue;
        }
        if c.ctor_name == "nil" {
            return n;
        }
        panic!("list_length: unexpected ctor '{}'", c.ctor_name);
    }
}

// ---------------------------------------------------------------------------
// Tests — mirror the TS inductive.test.ts assertions one-for-one. Cross-
// kernel: the same shape of assertions runs in TS, Python, Go, and Rust;
// `cargo test --release` here is the Rust leg of the conformance.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Kernel;

    #[test]
    fn cross_kernel_slots() {
        assert_eq!(RBASIC_INDUCTIVE, 71);
        assert_eq!(RBASIC_CONSTRUCTOR, 72);
        assert_eq!(RBASIC_CHOICE_MATCH, 35);
        assert_eq!(TRIV_CONSTRUCTOR_TAG, 15);
    }

    #[test]
    fn nat_round_trip_0_to_5() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        for i in 0..=5u64 {
            let node = nat_of(&mut k, &inds, i);
            let v = walk_value(&k, node);
            assert_eq!(
                nat_to_int(&v),
                i as i64,
                "nat_to_int(nat_of({})) should be {}",
                i,
                i
            );
        }
    }

    #[test]
    fn list_length_two() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let one = k.intern_trivial_int(1);
        let two = k.intern_trivial_int(2);
        let nil = list_nil(&mut k, &inds);
        let tail = list_cons(&mut k, &inds, two, nil);
        let lst = list_cons(&mut k, &inds, one, tail);
        let v = walk_value(&k, lst);
        assert!(matches!(v, CtorOrNid::Ctor(_)));
        assert_eq!(list_length(&v), 2);
    }

    #[test]
    fn option_match_covers() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let option = inds.get("Option").unwrap().node_id;
        let five = k.intern_trivial_int(5);
        let some_five = make_constructor(&mut k, option, "some", &[five]);
        let v = walk_value(&k, some_five);

        let mut arms: HashMap<String, ArmHandler<i64>> = HashMap::new();
        arms.insert("none".to_string(), Box::new(|_args| -1));
        arms.insert(
            "some".to_string(),
            Box::new(|args| {
                let arg0 = &args[0];
                match arg0 {
                    CtorOrNid::Nid(n) => (n.inst as i32) as i64,
                    _ => -2,
                }
            }),
        );
        let r = match_value(&k, &v, &arms);
        assert_eq!(r, 5, "matched some(5)");

        // None branch
        let none = make_constructor(&mut k, option, "none", &[]);
        let vn = walk_value(&k, none);
        let mut arms2: HashMap<String, ArmHandler<i64>> = HashMap::new();
        arms2.insert("none".to_string(), Box::new(|_| -1));
        arms2.insert("some".to_string(), Box::new(|_| 0));
        let rn = match_value(&k, &vn, &arms2);
        assert_eq!(rn, -1, "matched none");
    }

    #[test]
    #[should_panic(expected = "missing: none")]
    fn option_match_missing_arm_panics() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let option = inds.get("Option").unwrap().node_id;
        let five = k.intern_trivial_int(5);
        let some_five = make_constructor(&mut k, option, "some", &[five]);
        let v = walk_value(&k, some_five);

        let mut arms: HashMap<String, ArmHandler<i64>> = HashMap::new();
        arms.insert("some".to_string(), Box::new(|_| 1));
        let _ = match_value(&k, &v, &arms);
    }

    #[test]
    fn choice_recipe_totality_check_rejects_missing_arm() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let option = inds.get("Option").unwrap().node_id;
        let five = k.intern_trivial_int(5);
        let some_five = make_constructor(&mut k, option, "some", &[five]);

        let ninety_nine = k.intern_trivial_int(99);
        // Build a CHOICE_MATCH recipe covering only 'some'.
        let choice = make_choice(&mut k, some_five, &[("some", ninety_nine)]);

        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            walk_choice(&k, choice)
        }));
        assert!(r.is_err(), "walk_choice should reject non-total match");
    }

    #[test]
    fn choice_recipe_total_match_returns_arm_body() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let option = inds.get("Option").unwrap().node_id;
        let five = k.intern_trivial_int(5);
        let some_five = make_constructor(&mut k, option, "some", &[five]);

        let ninety_nine = k.intern_trivial_int(99);
        let zero = k.intern_trivial_int(0);
        let choice = make_choice(
            &mut k,
            some_five,
            &[("some", ninety_nine), ("none", zero)],
        );

        let v = walk_choice(&k, choice);
        // The 'some' arm body is the int-99 trivial; walk_value returns it as Nid.
        match v {
            CtorOrNid::Nid(n) => {
                assert_eq!(n, ninety_nine, "CHOICE returned the some-arm body");
            }
            _ => panic!("expected raw Nid"),
        }
    }

    #[test]
    fn custom_color_inductive_content_addressed() {
        let mut k = Kernel::new();
        let ctors = vec![
            ConstructorDef::new("red", 0, vec![]),
            ConstructorDef::new("green", 1, vec![]),
            ConstructorDef::new("blue", 2, vec![]),
        ];
        let color1 = make_inductive(&mut k, "Color", &[], &ctors);

        assert_eq!(
            constructor_names(&k, color1),
            vec!["red".to_string(), "green".to_string(), "blue".to_string()],
        );
        assert!(is_total(&k, color1, &["red", "green", "blue"]));
        assert!(!is_total(&k, color1, &["red", "green"]));

        // Same shape → same NodeID (content-addressing).
        let color2 = make_inductive(&mut k, "Color", &[], &ctors);
        assert_eq!(color1, color2, "structurally identical Color → same NodeID");
    }

    #[test]
    fn constructor_index_lookup() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let nat = inds.get("Nat").unwrap().node_id;
        assert_eq!(constructor_index(&k, nat, "zero"), 0);
        assert_eq!(constructor_index(&k, nat, "succ"), 1);
        assert_eq!(constructor_index(&k, nat, "no-such"), -1);
    }

    #[test]
    fn builtin_inductives_have_expected_ctors() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let nat = inds.get("Nat").unwrap().node_id;
        assert_eq!(constructor_names(&k, nat), vec!["zero".to_string(), "succ".to_string()]);
        let bool_t = inds.get("Bool").unwrap().node_id;
        assert_eq!(constructor_names(&k, bool_t), vec!["false".to_string(), "true".to_string()]);
        let option = inds.get("Option").unwrap().node_id;
        assert_eq!(constructor_names(&k, option), vec!["none".to_string(), "some".to_string()]);
        let result = inds.get("Result").unwrap().node_id;
        assert_eq!(constructor_names(&k, result), vec!["ok".to_string(), "err".to_string()]);
        let list = inds.get("List").unwrap().node_id;
        assert_eq!(constructor_names(&k, list), vec!["nil".to_string(), "cons".to_string()]);
    }

    #[test]
    fn install_builtin_inductives_idempotent() {
        let mut k = Kernel::new();
        let a = install_builtin_inductives(&mut k);
        let b = install_builtin_inductives(&mut k);
        // Content-addressing: re-installing yields the same NodeIDs.
        for name in ["Nat", "Bool", "Option", "Result", "List"] {
            assert_eq!(
                a.get(name).unwrap().node_id,
                b.get(name).unwrap().node_id,
                "{} should be idempotent",
                name
            );
        }
    }

    #[test]
    fn ctor_value_carries_inductive_and_index() {
        let mut k = Kernel::new();
        let inds = install_builtin_inductives(&mut k);
        let nat = inds.get("Nat").unwrap().node_id;
        let two = nat_of(&mut k, &inds, 2);
        let v = walk_value(&k, two);
        let c = v.as_ctor().expect("walked value is a ctor");
        assert_eq!(c.inductive, nat);
        assert_eq!(c.ctor_name, "succ");
        assert_eq!(c.ctor_index, 1);
        assert_eq!(c.args.len(), 1, "succ has one arg");
    }

    // ── Compose with QUOTIENT — the cross-arm contract ──────────────────
    //
    // The QUOTIENT module is the sibling Rust port (#35). When both arms
    // are linked into the same crate, Z := (Nat × Nat) / equiv expresses
    // integers as a quotient of nat-pairs. We don't link quotient.rs from
    // this branch — it lands in a separate breath — so this test stays
    // behind a feature gate. The Python ref test (api/tests/test_inductive.py)
    // covers the cross-arm composition end-to-end.
    //
    // When quotient.rs is present, uncomment:
    //
    //   #[test]
    //   fn z_quotient_of_nat_pairs() {
    //       use crate::quotient::*;
    //       let mut k = Kernel::new();
    //       let inds = install_builtin_inductives(&mut k);
    //       let lib = build_quotient_library(&mut k);
    //       // Pair Nat Nat carrier — placeholder; canonicalization runs
    //       // on the raw int-pair children.
    //       let nat = inds.get("Nat").unwrap().node_id;
    //       let q = make_quotient_recipe(&mut k, nat, lib.equiv_integer_from_nat_pair.node_id);
    //       let v31 = intern_quotient_value(&mut k, q, &[k.intern_trivial_int(3), k.intern_trivial_int(1)]);
    //       let v53 = intern_quotient_value(&mut k, q, &[k.intern_trivial_int(5), k.intern_trivial_int(3)]);
    //       assert_eq!(v31, v53, "Z = (Nat × Nat) / equiv canonicalizes (3,1) ≡ (5,3)");
    //   }
}
