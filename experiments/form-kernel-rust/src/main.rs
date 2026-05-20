// form-kernel-rust — vertical-slice host for Form-on-top.
//
// Reads `.fk` S-expression source files, parses straight into recipe trees,
// walks them. Carries everything Form-on-top can't write itself:
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — all 22 RBasic dispatch arms
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, I/O, conversion
//   • Bootstrap reader   — S-expression text → recipe tree
//
// What Form-on-top will write (in follow-up breaths): the Form-surface-
// syntax parser (1 + 2 → recipe), the query layer (?equivalent, |>),
// the substrate persistence integration.
//
// Usage:  form-kernel-rust <file.fk>
//         form-kernel-rust --bench
//         form-kernel-rust --expr "(add 2 3)"

use std::collections::HashMap;
use std::env;
use std::fs;
use std::rc::Rc;
use std::time::Instant;

mod formats;
mod quotient;

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

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
const RB_BLOCK: u32 = 9;
const RB_COND: u32 = 11;
const RB_MATH: u32 = 12;
const RB_COMPARE: u32 = 13;
const RB_LOGIC: u32 = 14;
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

#[derive(Clone, Debug)]
struct Recipe {
    category: NodeID,
    children: Vec<NodeID>,
}

#[derive(PartialEq, Eq, Hash)]
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
    strs: Vec<String>,
    str_idx: HashMap<String, NameID>,
    next_inst: u32,
    natives: HashMap<NameID, NativeFn>,
}

// Arena — the mutable-during-walk runtime state. Held as `&mut Arena`
// by the walker; orthogonal to the kernel so reading recipes and
// writing frames don't fight the borrow checker.
struct Arena {
    frames: Vec<Frame>,
}

impl Arena {
    fn new() -> Self { Self { frames: Vec::with_capacity(256) } }

    fn new_frame(&mut self, parent: Option<FrameId>) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame { parent, bindings: Vec::new() });
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
            strs: Vec::new(),
            str_idx: HashMap::new(),
            next_inst: 1,
            natives: HashMap::new(),
        };
        k.register_natives();
        k
    }

    // intern — content-addressed insertion. Same shape ⇒ same NodeID.
    pub(crate) fn intern(&mut self, category: NodeID, children: Vec<NodeID>) -> NodeID {
        let key = ShapeKey { category, children: children.clone() };
        if let Some(&nid) = self.by_shape.get(&key) {
            return nid;
        }
        let nid = NodeID { pkg: 1, level: category.level, ty: category.ty, inst: self.next_inst };
        self.next_inst += 1;
        self.by_shape.insert(key, nid);
        self.by_id.insert(nid, Recipe { category, children });
        nid
    }

    pub(crate) fn intern_trivial_int(&self, n: i64) -> NodeID {
        NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_INT, inst: (n as i32) as u32 }
    }

    pub(crate) fn intern_string(&mut self, s: &str) -> NodeID {
        if let Some(&idx) = self.str_idx.get(s) {
            return NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_STRING, inst: idx };
        }
        let idx = self.strs.len() as u32;
        self.strs.push(s.to_string());
        self.str_idx.insert(s.to_string(), idx);
        NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_STRING, inst: idx }
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
        self.by_id.get(&n).map(|r| r.children.clone()).unwrap_or_default()
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
    fn ident_id(&self, n: NodeID) -> NameID {
        if n.level == LEVEL_TRIVIAL && n.ty == TRIV_STRING {
            return n.inst;
        }
        let kids = self.children(n);
        if kids.len() == 1 && kids[0].level == LEVEL_TRIVIAL && kids[0].ty == TRIV_STRING {
            return kids[0].inst;
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
    Closure(Rc<Closure>),
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
            Value::Bool(b) => if *b { "true".to_string() } else { "false".to_string() },
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
    fn register_native(&mut self, name: &str, f: NativeFn) {
        let id = self.intern_string(name).inst;
        self.natives.insert(id, f);
    }

    fn register_natives(&mut self) {
        self.register_native("print", |_, _, args| {
            for (i, a) in args.iter().enumerate() {
                if i > 0 { print!(" "); }
                print!("{}", a.display());
            }
            println!();
            Value::Null
        });
        self.register_native("str_len", |_, _, args| {
            Value::Int(args[0].as_str().len() as i64)
        });
        self.register_native("substring", |_, _, args| {
            let s = args[0].as_str();
            let a = args[1].as_int() as usize;
            let b = args[2].as_int() as usize;
            Value::Str(s[a..b].to_string())
        });
        self.register_native("char_at", |_, _, args| {
            let s = args[0].as_str();
            let i = args[1].as_int() as usize;
            Value::Str((s.as_bytes()[i] as char).to_string())
        });
        self.register_native("str_concat", |_, _, args| {
            let mut s = args[0].as_str().to_string();
            s.push_str(args[1].as_str());
            Value::Str(s)
        });
        self.register_native("str_eq", |_, _, args| {
            Value::Bool(args[0].as_str() == args[1].as_str())
        });
        self.register_native("int_to_str", |_, _, args| {
            Value::Str(args[0].as_int().to_string())
        });
        self.register_native("str_to_int", |_, _, args| {
            Value::Int(args[0].as_str().parse().unwrap_or(0))
        });
        self.register_native("ord", |_, _, args| {
            let s = args[0].as_str();
            if s.is_empty() { Value::Int(-1) } else { Value::Int(s.as_bytes()[0] as i64) }
        });
        self.register_native("list", |_, _, args| {
            Value::List(args.to_vec())
        });
        self.register_native("cons", |_, _, args| {
            let mut out = vec![args[0].clone()];
            if let Value::List(rest) = &args[1] {
                out.extend(rest.iter().cloned());
            }
            Value::List(out)
        });
        self.register_native("head", |_, _, args| {
            if let Value::List(xs) = &args[0] {
                xs.first().cloned().unwrap_or(Value::Null)
            } else { Value::Null }
        });
        self.register_native("tail", |_, _, args| {
            if let Value::List(xs) = &args[0] {
                Value::List(if xs.is_empty() { vec![] } else { xs[1..].to_vec() })
            } else { Value::Null }
        });
        self.register_native("len", |_, _, args| {
            match &args[0] {
                Value::List(xs) => Value::Int(xs.len() as i64),
                Value::Str(s) => Value::Int(s.len() as i64),
                _ => Value::Int(0),
            }
        });
        self.register_native("nth", |_, _, args| {
            if let Value::List(xs) = &args[0] {
                xs[args[1].as_int() as usize].clone()
            } else { Value::Null }
        });
        self.register_native("empty", |_, _, _| Value::List(vec![]));
        self.register_native("read_file", |_, _, args| {
            match fs::read_to_string(args[0].as_str()) {
                Ok(s) => Value::Str(s),
                Err(_) => Value::Null,
            }
        });

        // --- Substrate write surface ------------------------------------
        // Form code holds NodeIDs as values (Value::Nid) and uses these
        // natives to construct recipes. Closes form-runtime-in-form gaps
        // W1-W3. With these, templates (Breath 2) become expressible —
        // Form code can BUILD recipes from pattern matches, not just walk
        // pre-existing ones.

        self.register_native("make_nodeid", |_, _, args| {
            Value::Nid(NodeID {
                pkg: args[0].as_int() as u32,
                level: args[1].as_int() as u32,
                ty: args[2].as_int() as u32,
                inst: args[3].as_int() as u32,
            })
        });
        self.register_native("intern_trivial_int", |k, _, args| {
            Value::Nid(k.intern_trivial_int(args[0].as_int()))
        });
        self.register_native("intern_trivial_string", |k, _, args| {
            let s = args[0].as_str().to_string();
            Value::Nid(k.intern_string(&s))
        });
        self.register_native("intern_node", |k, _, args| {
            // args[0]: category as Nid; args[1]: children as List of Nids
            let cat = args[0].as_nid();
            let kids: Vec<NodeID> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
                _ => panic!("intern_node: children must be a list"),
            };
            Value::Nid(k.intern(cat, kids))
        });
        self.register_native("node_category", |k, _, args| {
            Value::Nid(k.category(args[0].as_nid()))
        });
        self.register_native("node_children", |k, _, args| {
            let kids = k.children(args[0].as_nid());
            Value::List(kids.into_iter().map(Value::Nid).collect())
        });
        self.register_native("node_value", |k, _, args| {
            k.trivial_value(args[0].as_nid())
        });
        // walk_recipe — evaluate a NodeID in a fresh root frame. Returns
        // the value the recipe produces. Use case: Form code builds a
        // recipe via intern_node, then walks it to get the runtime result.
        self.register_native("walk_recipe", |k, _, args| {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            walk(k, &mut sub_arena, args[0].as_nid(), env)
        });

        // --- Debug / inspection -----------------------------------------
        // `trace` — print-and-return. Drop into any Form expression to
        // inspect a value mid-computation without breaking control flow.
        // Output goes to stderr so it doesn't pollute the result on stdout.
        //   (let result (trace (filter even? xs)))
        //   (trace "label" value)   ; with a label prefix
        self.register_native("trace", |_, _, args| {
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
                if !walk(k, a, kids[0], env).as_bool() { Value::Bool(false) }
                else { Value::Bool(walk(k, a, kids[1], env).as_bool()) }
            }
            RLOG_OR => {
                if walk(k, a, kids[0], env).as_bool() { Value::Bool(true) }
                else { Value::Bool(walk(k, a, kids[1], env).as_bool()) }
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
            let cl = Rc::new(Closure { name, params, body: kids[2], env });
            a.bind(env, name, Value::Closure(cl.clone()));
            Value::Closure(cl)
        }
        RB_FNCALL => {
            let name = k.ident_id(kids[0]);
            // Native takes priority unless user shadowed. Copy the fn pointer
            // out so the natives-map borrow releases before we call &mut k.
            let nf_opt = k.natives.get(&name).copied();
            if let Some(nf) = nf_opt {
                if a.lookup(env, name).is_none() {
                    let mut args = Vec::with_capacity(kids.len() - 1);
                    for arg in &kids[1..] {
                        args.push(walk(k, a, *arg, env));
                    }
                    return nf(k, a, &args);
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
            let call_frame = a.new_frame(Some(cl.env));
            // Evaluate args in CALLER's env, then bind in call_frame.
            // The clone is Rc<Closure> — bump-the-refcount, not deep.
            let cl2 = cl.clone();
            for (i, p) in cl2.params.iter().enumerate() {
                let arg = walk(k, a, kids[i + 1], env);
                a.bind(call_frame, *p, arg);
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
        _ => panic!("walk: no arm for category {:?}", cat),
    }
}

// ---------------------------------------------------------------------------
// S-expression reader — bootstrap parser, text → recipe tree
// ---------------------------------------------------------------------------

// SexpTok — bootstrap-reader token. Carries 1-based line/col so parse
// errors can point at the source. Without this, every paren imbalance
// surfaces as an unhelpful "index out of bounds" panic.
#[derive(Debug, Clone)]
struct SexpTok { kind: &'static str, value: String, line: u32, col: u32 }

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
            b'\n' => { i += 1; line += 1; col = 1; }
            b' ' | b'\t' | b'\r' => { i += 1; col += 1; }
            b';' => {
                while i < bytes.len() && bytes[i] != b'\n' { i += 1; }
                // newline handled by outer loop
            }
            b'(' => {
                toks.push(SexpTok { kind: "LPAREN", value: "(".into(), line: sline, col: scol });
                i += 1; col += 1;
            }
            b')' => {
                toks.push(SexpTok { kind: "RPAREN", value: ")".into(), line: sline, col: scol });
                i += 1; col += 1;
            }
            b'"' => {
                i += 1; col += 1;
                let start = i;
                while i < bytes.len() && bytes[i] != b'"' {
                    if bytes[i] == b'\\' && i + 1 < bytes.len() { i += 2; col += 2; continue; }
                    if bytes[i] == b'\n' { line += 1; col = 1; } else { col += 1; }
                    i += 1;
                }
                let raw = &src[start..i];
                toks.push(SexpTok { kind: "STRING", value: unescape(raw), line: sline, col: scol });
                if i < bytes.len() { i += 1; col += 1; }
            }
            b'0'..=b'9' => {
                let start = i;
                while i < bytes.len() && bytes[i].is_ascii_digit() { i += 1; }
                toks.push(SexpTok { kind: "INT", value: src[start..i].to_string(), line: sline, col: scol });
                col += (i - start) as u32;
            }
            b'-' if i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit() => {
                let start = i;
                i += 1;
                while i < bytes.len() && bytes[i].is_ascii_digit() { i += 1; }
                toks.push(SexpTok { kind: "INT", value: src[start..i].to_string(), line: sline, col: scol });
                col += (i - start) as u32;
            }
            _ => {
                let start = i;
                while i < bytes.len() {
                    let cc = bytes[i];
                    if cc == b' ' || cc == b'\t' || cc == b'\n' || cc == b'\r'
                        || cc == b'(' || cc == b')' || cc == b'"' || cc == b';' { break; }
                    i += 1;
                }
                toks.push(SexpTok { kind: "IDENT", value: src[start..i].to_string(), line: sline, col: scol });
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
// at the source instead of dying with "index out of bounds." The bootstrap
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
                return (NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_BOOL, inst: 1 }, i + 1);
            }
            if t.value == "false" {
                return (NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_BOOL, inst: 0 }, i + 1);
            }
            let s = k.intern_string(&t.value);
            (k.intern(cat_ident(), vec![s]), i + 1)
        }
        "RPAREN" => {
            panic!("parse error at line {} col {}: unmatched `)` (no `(` to close)", t.line, t.col);
        }
        "LPAREN" => {
            let (open_line, open_col) = (t.line, t.col);
            let mut j = i + 1;
            if j >= toks.len() {
                panic!("parse error: unclosed `(` opened at line {} col {} (reached end of input)",
                    open_line, open_col);
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
        _ => panic!("parse error at line {} col {}: unexpected token {} {:?}",
            t.line, t.col, t.kind, t.value),
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
            let name_trivial = NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_STRING, inst: name_id };
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
            let name_trivial = NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_STRING, inst: name_id };
            let param_ids: Vec<NameID> = k.children(args[1]).iter().map(|p| k.ident_id(*p)).collect();
            let param_trivials: Vec<NodeID> = param_ids
                .into_iter()
                .map(|id| NodeID { pkg: 1, level: LEVEL_TRIVIAL, ty: TRIV_STRING, inst: id })
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

fn cat_math(inst: u32) -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_MATH, inst } }
fn cat_compare(inst: u32) -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_COMPARE, inst } }
fn cat_logic(inst: u32) -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_LOGIC, inst } }
fn cat_cond(inst: u32) -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_COND, inst } }
fn cat_block(inst: u32) -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_BLOCK, inst } }
fn cat_ident() -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_IDENT, inst: 1 } }
fn cat_fndef() -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_FNDEF, inst: 1 } }
fn cat_fncall() -> NodeID { NodeID { pkg: 1, level: LEVEL_BASIC, ty: RB_FNCALL, inst: 1 } }

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn count_top_level(toks: &[SexpTok]) -> usize {
    let mut depth = 0;
    let mut count = 0;
    for t in toks {
        match t.kind {
            "LPAREN" => { if depth == 0 { count += 1; } depth += 1; }
            "RPAREN" => { depth -= 1; }
            _ => { if depth == 0 { count += 1; } }
        }
    }
    count
}

fn run_source(src: &str) -> Value {
    let toks = tokenize_sexp(src);
    let wrapped: String;
    let toks = if count_top_level(&toks) == 1 {
        toks
    } else {
        wrapped = format!("(do {})", src);
        tokenize_sexp(&wrapped)
    };
    let mut k = Kernel::new();
    let (root, _) = read_sexp(&mut k, &toks, 0);
    let mut a = Arena::new();
    let env = a.new_frame(None);
    walk(&mut k, &mut a, root, env)
}

// --- Native implementations — same recursive shape as the Form versions.
// `black_box` on the recursive call's argument prevents LLVM from analyzing
// the recursion and constant-folding the whole computation. Without it,
// pure functions with eventually-constant inputs collapse to a register
// load and the "native" column becomes a measurement of nothing. With it,
// the actual instructions get executed.

fn native_fib(n: i64) -> i64 {
    if n <= 1 { n } else {
        native_fib(std::hint::black_box(n - 1)) + native_fib(std::hint::black_box(n - 2))
    }
}

fn native_fact(n: i64) -> i64 {
    if n <= 1 { 1 } else { n * native_fact(std::hint::black_box(n - 1)) }
}

fn native_sum(n: i64, acc: i64) -> i64 {
    if n == 0 { acc } else {
        native_sum(std::hint::black_box(n - 1), std::hint::black_box(acc + n))
    }
}

fn native_ack(m: i64, n: i64) -> i64 {
    if m == 0 { n + 1 }
    else if n == 0 { native_ack(std::hint::black_box(m - 1), 1) }
    else {
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

    println!("{:<12} {:<12} {:<14} {:<14} {}", "workload", "result", "native", "kernel", "overhead");
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

fn main() {
    // Override Rust's default panic handler so Form authors see a clean
    // "parse error at line X col Y: ..." message instead of Rust's internal
    // backtrace. Kernel devs can set RUST_BACKTRACE=1 to get the full
    // story when debugging the kernel itself.
    std::panic::set_hook(Box::new(|info| {
        let msg = info.payload().downcast_ref::<String>()
            .map(|s| s.as_str())
            .or_else(|| info.payload().downcast_ref::<&str>().copied())
            .unwrap_or("unknown error");
        eprintln!("form-kernel-rust: {}", msg);
    }));

    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust <file.fk> [more.fk ...] | --expr \"...\" | --bench | --numeric-bench");
        std::process::exit(2);
    }

    if args[0] == "--bench" {
        run_bench();
        return;
    }

    if args[0] == "--numeric-bench" {
        formats::run_numeric_bench();
        return;
    }

    let src = if args[0] == "--expr" {
        if args.len() < 2 { eprintln!("--expr requires an argument"); std::process::exit(2); }
        args[1].clone()
    } else {
        // Multiple files load sequentially into a shared top-level scope.
        // Concatenation works because the kernel wraps multi-form input in
        // an implicit do-block — definitions from earlier files become
        // visible to later ones.
        let mut parts = Vec::with_capacity(args.len());
        for path in &args {
            parts.push(fs::read_to_string(path).unwrap_or_else(|e| {
                eprintln!("read {}: {}", path, e);
                std::process::exit(1);
            }));
        }
        parts.join("\n")
    };
    let result = run_source(&src);
    println!("{}", result.display());
}
