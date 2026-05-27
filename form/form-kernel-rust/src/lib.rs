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
//
// Both run the same `run_source` the CLI binary runs. The Value → PyAny
// conversion mirrors the kernel's display(): Int, Float, Bool, Str, List
// land as native Python types; Closure renders as "<closure #N>"; Nid
// renders as "@p.l.t.i"; Null becomes None.
//
// The whole module is gated on the `pyo3` feature so building the binary
// alone (cargo build --release) doesn't drag in PyO3 / libpython.

#![cfg(feature = "pyo3")]

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
pub use kernel::*;

use kernel::Value;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyList;
use std::panic::{catch_unwind, AssertUnwindSafe};

/// Convert a kernel Value to a Python object — same surface as Value::display()
/// but typed: ints stay ints, floats stay floats, lists become PyList of the
/// same recursion. Closures and NodeIDs land as their display strings (the
/// callers expecting structured types parse from the strings just as they do
/// from the subprocess stdout).
fn value_to_py(py: Python<'_>, v: &Value) -> PyResult<PyObject> {
    let obj = match v {
        Value::Null => py.None(),
        Value::Int(n) => n.into_py(py),
        Value::Float(f) => f.into_py(py),
        Value::Str(s) => s.into_py(py),
        Value::Bool(b) => b.into_py(py),
        Value::List(xs) => {
            let list = PyList::empty_bound(py);
            for x in xs {
                list.append(value_to_py(py, x)?)?;
            }
            list.into_py(py)
        }
        // Closures land as their display string ("<closure #N>") via
        // Value::display(); avoids touching the private Closure fields.
        Value::Closure(_) => v.display().into_py(py),
        Value::Nid(n) => format!("@{}.{}.{}.{}", n.pkg, n.level, n.ty, n.inst).into_py(py),
    };
    Ok(obj)
}

/// Compile and run a Form recipe source string, return its value as a
/// native Python object. This is the inline-equivalent of running
/// `form-kernel-rust <file>` and reading the last stdout line.
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
#[pyfunction]
fn run_fk(py: Python<'_>, path: &str) -> PyResult<PyObject> {
    let src = std::fs::read_to_string(path).map_err(|e| {
        PyRuntimeError::new_err(format!("form-kernel: read {}: {}", path, e))
    })?;
    compile_and_run(py, &src)
}

#[pymodule]
fn form_kernel_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_and_run, m)?)?;
    m.add_function(wrap_pyfunction!(run_fk, m)?)?;
    m.add("__doc__", "form-kernel-rust inline runtime (PyO3 extension)")?;
    Ok(())
}
