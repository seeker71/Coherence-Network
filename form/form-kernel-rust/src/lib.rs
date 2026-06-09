// form-kernel-rust — PyO3 extension surface.
//
// The same kernel that ships as the CLI binary, made callable inline from
// Python. The subprocess seam in api/app/services/form_kernel_bridge.py
// becomes a fork-and-exec only on the cold fallback path; the hot path is
// a Python C call straight into Rust, no process spawn.
//
// What this exposes:
//   compile_and_run(src: str) -> int|float|str|bool|list|None
//   run_fk(path: str)         -> int|float|str|bool|list|None
//   Preloader                 — a warm Kernel+Arena that parses each route
//                               recipe ONCE and runs (handle, bindings) per
//                               request with no re-parse (the route-preload
//                               pair below).
//
// Both run the same `run_source` the CLI binary runs. The Value → PyAny
// conversion mirrors the kernel's display(): Int, Float, Bool, Str, List
// land as native Python types; Closure renders as "<closure #N>"; Nid
// renders as "@p.l.t.i"; Null becomes None.
//
// ──────────────────────────────────────────────────────────────────────────
// Route preload — drop the per-request parse.
// ──────────────────────────────────────────────────────────────────────────
//
// compile_and_run re-tokenizes + re-reads the WHOLE recipe source on every
// call (run_source → read_root_from_source → tokenize_sexp + read_sexp), then
// re-walks every `defn` to re-bind its closure before the trailing call. For a
// FastAPI endpoint whose recipe shape is fixed and whose only per-request
// change is the input values, that parse + defn-rebind is pure overhead paid
// on every request.
//
// `Preloader` mirrors cli_serve's pattern (main.rs ~5571): load the routes
// into a long-lived Kernel+Arena ONCE, then dispatch each request to a fresh
// child frame. Here the "load" is split into a `setup` recipe (the `defn`s,
// walked once into the root frame so the closures bind a single time) and a
// `body` recipe (the trailing call, parsed once into a held NodeID). Per
// request: a child frame of the root, bind the input names to the request's
// Values, walk the pre-parsed body NodeID — no tokenize, no read, no
// defn-rebind. ONE mechanism, routes as DATA (a Vec indexed by handle); no
// endpoint is special-cased.
//
// The whole module is gated on the `pyo3` feature so building the binary
// alone (cargo build --release) doesn't drag in PyO3 / libpython.

// This library surface is built for either non-bin host: the PyO3 Python
// extension (`--features pyo3`, via maturin) OR the C-ABI cdylib (`--features
// cabi`, for Android / any host without Python). The plain bin build pulls in
// neither, so main.rs compiles once (validate.sh / CI stay fast).
#![cfg(any(feature = "pyo3", feature = "cabi"))]

// Pull main.rs into the library as a sibling module. The bin target still
// uses main.rs as its own entry; we re-include it here as a module so its
// internal items (Value, run_source, sub-modules) are reachable from lib.rs
// without duplicating the kernel.
#[path = "main.rs"]
mod kernel;

// Re-export every public-within-crate item at the crate root. The sibling
// modules (formats, inductive, quotient) import paths like `crate::Kernel`
// and `crate::NodeID`. In the binary build those resolve because main.rs
// is the crate root; here the kernel lives one level down, so we surface
// its items back up.
#[allow(unused_imports)]
pub use kernel::*;

// ──────────────────────────────────────────────────────────────────────────
// C-ABI surface — the phone-native door. The SAME evaluator the CLI runs
// (kernel::run_source), reachable from any language that can call C: Android
// via JNI, embedded via FFI. No Python, no subprocess. This is the universal
// surface; the PyO3 block below is one specialization of it for the in-process
// Python hot path.
// ──────────────────────────────────────────────────────────────────────────
#[cfg(feature = "cabi")]
mod cabi {
    use crate::kernel;
    use std::ffi::{CStr, CString};
    use std::os::raw::c_char;
    use std::panic::{catch_unwind, AssertUnwindSafe};

    /// Evaluate a Form recipe source string; return the final value rendered as
    /// the kernel's `display()` text — the exact text the CLI prints. The
    /// returned heap C string MUST be freed with `form_eval_free`. A panic, a
    /// null pointer, or non-UTF-8 input comes back as a string starting "ERR:"
    /// (never a crash across the FFI boundary).
    #[no_mangle]
    pub extern "C" fn form_eval(src: *const c_char) -> *mut c_char {
        let out = catch_unwind(AssertUnwindSafe(|| {
            if src.is_null() {
                return "ERR: null source".to_string();
            }
            match unsafe { CStr::from_ptr(src) }.to_str() {
                Ok(s) => kernel::run_source(s).display(),
                Err(_) => "ERR: source not valid UTF-8".to_string(),
            }
        }))
        .unwrap_or_else(|_| "ERR: kernel panic".to_string());
        match CString::new(out) {
            Ok(c) => c.into_raw(),
            Err(_) => CString::new("ERR: nul byte in output").unwrap().into_raw(),
        }
    }

    /// Free a string returned by `form_eval`. Calling with null is a no-op.
    #[no_mangle]
    pub extern "C" fn form_eval_free(p: *mut c_char) {
        if !p.is_null() {
            unsafe { drop(CString::from_raw(p)) };
        }
    }
}

#[cfg(feature = "pyo3")]
use kernel::{read_root_from_source, walk, Arena, Kernel, NodeID, Value};
#[cfg(feature = "pyo3")]
use pyo3::exceptions::{PyRuntimeError, PyValueError};
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;
#[cfg(feature = "pyo3")]
use pyo3::types::{PyDict, PyList};
#[cfg(feature = "pyo3")]
use std::panic::{catch_unwind, AssertUnwindSafe};

/// Convert a kernel Value to a Python object — same surface as Value::display()
/// but typed: ints stay ints, floats stay floats, lists become PyList of the
/// same recursion. Closures and NodeIDs land as their display strings (the
/// callers expecting structured types parse from the strings just as they do
/// from the subprocess stdout).
#[cfg(feature = "pyo3")]
fn value_to_py(py: Python<'_>, v: &Value) -> PyResult<PyObject> {
    let obj = match v {
        Value::Null => py.None(),
        Value::Int(n) => n.into_py(py),
        Value::Float(f) => f.into_py(py),
        Value::Str(s) => s.into_py(py),
        Value::Bool(b) => b.into_py(py),
        Value::List(xs) => {
            let list = PyList::empty_bound(py);
            // Value::List now wraps Arc<Vec<Value>> — iterate through the Arc.
            for x in xs.iter() {
                list.append(value_to_py(py, x)?)?;
            }
            list.into_py(py)
        }
        // Closures land as their display string ("<closure #N>") via
        // Value::display(); avoids touching the private Closure fields.
        Value::Closure(_) => v.display().into_py(py),
        Value::Nid(n) => format!("@{}.{}.{}.{}", n.pkg, n.level, n.ty, n.inst).into_py(py),
        // Records (structured cells) render as their display string — the
        // same surface the CLI prints. The transmuted endpoints return
        // scalars/lists; a Record reaching here means a recipe shape the
        // inline path doesn't structurally unwrap yet, so we hand back the
        // honest display text rather than fabricate a Python dict.
        Value::Record(_) => v.display().into_py(py),
    };
    Ok(obj)
}

/// Conventional blueprint NodeID for a record marshalled from a Python dict /
/// model — the structured-input tag the bridge's `_fk_literal` renders too
/// (`(make_nodeid 1 5 4 1)`), so a record marshalled inline and one injected as
/// a `record_new` literal on the subprocess path share the same blueprint. The
/// recipe reads fields by name (record_get), not by blueprint, so the exact
/// value only needs to be stable and consistent across the two carriers.
#[cfg(feature = "pyo3")]
const STRUCTURED_INPUT_BLUEPRINT: NodeID = NodeID {
    pkg: 1,
    level: 5,
    ty: 4,
    inst: 1,
};

/// Convert a Python object into a kernel Value — the inverse of value_to_py,
/// restricted to the value model the kernel carries (the same surface
/// _fk_literal renders on the Python side). bool before int (Python bool is an
/// int subclass); lists recurse; a dict marshals to a kernel Record so a
/// transmuted recipe can read named fields via `record_get` (the structure-
/// access capability). Anything else is a ValueError so the caller's fallback
/// can take over rather than the kernel walking a fabricated value.
///
/// `kernel` is threaded so a dict's field names can intern to NameIDs exactly
/// as the `record_new` native does — the marshalling seam for structured input.
#[cfg(feature = "pyo3")]
fn py_to_value(kernel: &mut Kernel, obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if let Ok(b) = obj.downcast::<pyo3::types::PyBool>() {
        return Ok(Value::Bool(b.is_true()));
    }
    if let Ok(n) = obj.extract::<i64>() {
        return Ok(Value::Int(n));
    }
    if let Ok(f) = obj.extract::<f64>() {
        return Ok(Value::Float(f));
    }
    if let Ok(s) = obj.extract::<String>() {
        // Value::Str now wraps Arc<str> (String -> Arc<str> via From).
        return Ok(Value::Str(s.into()));
    }
    if let Ok(list) = obj.downcast::<PyList>() {
        let mut xs = Vec::with_capacity(list.len());
        for item in list.iter() {
            xs.push(py_to_value(kernel, &item)?);
        }
        // Value::List now wraps Arc<Vec<Value>> (Vec -> Arc<Vec> via From).
        return Ok(Value::List(xs.into()));
    }
    if let Ok(dict) = obj.downcast::<PyDict>() {
        // Marshal a flat dict (string keys → scalar/list/dict values) onto a
        // Record. Keys must be strings (a field name); the recipe reads them
        // back by name via record_get. Insertion order is preserved.
        let mut pairs: Vec<(String, Value)> = Vec::with_capacity(dict.len());
        for (key, val) in dict.iter() {
            let name: String = key.extract().map_err(|_| {
                PyValueError::new_err("form-kernel: record field name must be a string")
            })?;
            pairs.push((name, py_to_value(kernel, &val)?));
        }
        return Ok(kernel.make_record(STRUCTURED_INPUT_BLUEPRINT, pairs));
    }
    // A structured object that isn't a dict (a Pydantic model / dataclass) —
    // normalize to its field dict and recurse onto the Record marshalling. This
    // is the model→dict→record step that dissolves the object-OR-dict
    // polymorphism at the inline boundary, mirroring the Python bridge's
    // `_as_field_dict`: a recipe that folds over a list[model] sees the same
    // list-of-records a list[dict] produces. Pydantic v2 `model_dump()` first,
    // then v1 `.dict()`; if neither yields a dict the value is genuinely
    // unbindable and we surface the ValueError so the caller's fallback runs.
    for method in ["model_dump", "dict"] {
        if let Ok(m) = obj.getattr(method) {
            if m.is_callable() {
                if let Ok(res) = m.call0() {
                    if res.downcast::<PyDict>().is_ok() {
                        return py_to_value(kernel, &res);
                    }
                }
            }
        }
    }
    Err(PyValueError::new_err(format!(
        "form-kernel: cannot bind Python {} into a kernel Value",
        obj.get_type().name()?
    )))
}

/// A preloaded route — the trailing call expression of one endpoint recipe,
/// parsed once into a NodeID held against the warm Kernel. The `defn`s that
/// the body references were walked once into the Preloader's root frame at
/// load, so this NodeID needs only its input names bound to walk.
#[cfg(feature = "pyo3")]
struct PreloadedRoute {
    body: NodeID,
}

/// Preloader — a warm Kernel+Arena holding each endpoint recipe parsed ONCE.
///
/// The route-preload half of the inline path. Mirrors cli_serve: one long-lived
/// Kernel+Arena, routes loaded once, each request a fresh child frame. The
/// handle returned by `load_route` is an index into `routes`; `run` looks the
/// route up and walks its pre-parsed body with the request's bindings — no
/// tokenize, no read_sexp, no defn-rebind per call.
#[cfg(feature = "pyo3")]
#[pyclass]
struct Preloader {
    kernel: Kernel,
    arena: Arena,
    // FrameId / NameID are private `type X = u32` aliases in main.rs; use the
    // underlying u32 here so lib.rs needs no extra visibility change for them.
    root_env: u32,
    routes: Vec<PreloadedRoute>,
}

#[cfg(feature = "pyo3")]
#[pymethods]
impl Preloader {
    #[new]
    fn new() -> Self {
        let kernel = Kernel::new();
        let mut arena = Arena::new();
        let root_env = arena.new_frame(None);
        Preloader {
            kernel,
            arena,
            root_env,
            routes: Vec::new(),
        }
    }

    /// Parse a route recipe ONCE and return its handle.
    ///
    /// `setup_src` holds the recipe's `defn`s (and any constant lets the body
    /// depends on); it is walked once into the root frame so its closures bind
    /// a single time, shared by every subsequent `run`. `body_src` is the
    /// trailing call expression; it is parsed into a held NodeID. The split is
    /// the caller's responsibility (the Python bridge owns the recipe text and
    /// knows which `(let ...)` forms carry per-request inputs) — this side stays
    /// recipe-agnostic: ONE mechanism for all routes.
    fn load_route(&mut self, setup_src: &str, body_src: &str) -> PyResult<usize> {
        let res = catch_unwind(AssertUnwindSafe(|| {
            // Walk the setup (defns + constant lets) once into the root frame.
            if !setup_src.trim().is_empty() {
                let setup_root = read_root_from_source(&mut self.kernel, setup_src);
                let _ = walk(&mut self.kernel, &mut self.arena, setup_root, self.root_env);
            }
            // Parse the body once; hold its NodeID. No walk yet — that happens
            // per request against a child frame carrying the inputs.
            read_root_from_source(&mut self.kernel, body_src)
        }));
        match res {
            Ok(body) => {
                self.routes.push(PreloadedRoute { body });
                Ok(self.routes.len() - 1)
            }
            Err(p) => Err(PyRuntimeError::new_err(format!(
                "form-kernel: load_route panic: {}",
                panic_message(&p)
            ))),
        }
    }

    /// Run a preloaded route with per-request bindings — no re-parse.
    ///
    /// `bindings` maps input names to Python values; each is converted to a
    /// kernel Value and bound into a fresh child frame of the root (where the
    /// `defn` closures live). The pre-parsed body NodeID is then walked in that
    /// frame. The result converts through the same value_to_py as the inline
    /// path, so value-parity with compile_and_run is exact.
    fn run(
        &mut self,
        py: Python<'_>,
        handle: usize,
        bindings: &Bound<'_, PyDict>,
    ) -> PyResult<PyObject> {
        if handle >= self.routes.len() {
            return Err(PyValueError::new_err(format!(
                "form-kernel: no preloaded route for handle {}",
                handle
            )));
        }
        // Convert the bindings outside the panic boundary so a bad value is a
        // clean ValueError, not a kernel panic.
        let mut pairs: Vec<(u32, Value)> = Vec::with_capacity(bindings.len());
        for (key, val) in bindings.iter() {
            let name: String = key.extract()?;
            let value = py_to_value(&mut self.kernel, &val)?;
            let name_id = self.kernel.intern_string(&name).inst;
            pairs.push((name_id, value));
        }
        let body = self.routes[handle].body;
        let res = catch_unwind(AssertUnwindSafe(|| {
            let frame = self
                .arena
                .new_frame_with_capacity(Some(self.root_env), pairs.len());
            for (name_id, value) in &pairs {
                self.arena.bind(frame, *name_id, value.clone());
            }
            walk(&mut self.kernel, &mut self.arena, body, frame)
        }));
        match res {
            Ok(v) => value_to_py(py, &v),
            Err(p) => Err(PyRuntimeError::new_err(format!(
                "form-kernel: run panic: {}",
                panic_message(&p)
            ))),
        }
    }

    /// Number of routes loaded — for the bridge to sanity-check its handle map.
    fn route_count(&self) -> usize {
        self.routes.len()
    }
}

/// Pull a human string out of a panic payload (used by both Preloader methods).
#[cfg(feature = "pyo3")]
fn panic_message(p: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = p.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = p.downcast_ref::<String>() {
        s.clone()
    } else {
        "(no message)".to_string()
    }
}

/// Compile and run a Form recipe source string, return its value as a
/// native Python object. This is the inline-equivalent of running
/// `form-kernel-rust <file>` and reading the last stdout line.
#[cfg(feature = "pyo3")]
#[pyfunction]
fn compile_and_run(py: Python<'_>, src: &str) -> PyResult<PyObject> {
    // The kernel may panic on malformed input; turn the panic into a
    // Python RuntimeError so the caller's fallback can take over.
    let res = catch_unwind(AssertUnwindSafe(|| kernel::run_source(src)));
    match res {
        Ok(v) => value_to_py(py, &v),
        Err(panic_payload) => {
            let msg = if let Some(s) = panic_payload.downcast_ref::<&str>() {
                (*s).to_string()
            } else if let Some(s) = panic_payload.downcast_ref::<String>() {
                s.clone()
            } else {
                "form-kernel panic (no message)".to_string()
            };
            Err(PyRuntimeError::new_err(format!("form-kernel: {}", msg)))
        }
    }
}

/// Read a .fk file from disk and run it. Convenience for parity with
/// `form-kernel-rust <file.fk>`.
#[cfg(feature = "pyo3")]
#[pyfunction]
fn run_fk(py: Python<'_>, path: &str) -> PyResult<PyObject> {
    let src = std::fs::read_to_string(path)
        .map_err(|e| PyRuntimeError::new_err(format!("form-kernel: read {}: {}", path, e)))?;
    compile_and_run(py, &src)
}

#[cfg(feature = "pyo3")]
#[pymodule]
fn form_kernel_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_and_run, m)?)?;
    m.add_function(wrap_pyfunction!(run_fk, m)?)?;
    m.add_class::<Preloader>()?;
    m.add(
        "__doc__",
        "form-kernel-rust inline runtime (PyO3 extension)",
    )?;
    Ok(())
}
